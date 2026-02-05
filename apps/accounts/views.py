"""
Views for accounts app.
"""
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from .serializers import (
    CustomTokenObtainPairSerializer, UserSerializer, UserRegistrationSerializer,
    StaffUserSerializer, AddressSerializer, ChangePasswordSerializer,
    ForgotPasswordSerializer, ResetPasswordSerializer, EmailVerificationSerializer,
    ResendVerificationSerializer
)
from .models import Address, EmailVerificationToken, PasswordResetToken
from .permissions import IsSuperAdmin, IsStaffUser
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom JWT token obtain view."""
    serializer_class = CustomTokenObtainPairSerializer


class UserRegistrationView(generics.CreateAPIView):
    """User registration endpoint."""
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'Registration successful',
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """User profile view and update."""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    """Change password endpoint."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {'old_password': 'Wrong password.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({'message': 'Password changed successfully'})


class LogoutView(APIView):
    """Logout endpoint - blacklist refresh token."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({'message': 'Logout successful'})
        except Exception:
            return Response({'message': 'Logout successful'})


class AddressListCreateView(generics.ListCreateAPIView):
    """List and create addresses for authenticated user."""
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, delete address."""
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)


# Staff Management Views (Admin Panel)
class StaffUserListCreateView(generics.ListCreateAPIView):
    """List and create staff users (sellers, accountants)."""
    serializer_class = StaffUserSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    def get_queryset(self):
        return User.objects.filter(role__in=['seller', 'accountant', 'super_admin'])


class StaffUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, delete staff user."""
    serializer_class = StaffUserSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    def get_queryset(self):
        return User.objects.filter(role__in=['seller', 'accountant', 'super_admin'])


class CustomerListView(generics.ListAPIView):
    """List all customers with order statistics."""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]

    def get_queryset(self):
        from django.db.models import Count, Sum
        return User.objects.filter(role='customer').annotate(
            order_count=Count('orders'),
            total_spent=Sum('orders__total_amount')
        )


class GoogleAuthView(APIView):
    """
    Google OAuth authentication endpoint.
    Verifies Google ID token and creates/logs in user.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
        from django.conf import settings

        credential = request.data.get('credential')

        if not credential:
            return Response(
                {'error': 'Google credential is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not settings.GOOGLE_CLIENT_ID:
            return Response(
                {'error': 'Google OAuth is not configured'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        try:
            # Verify the Google ID token
            idinfo = id_token.verify_oauth2_token(
                credential,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )

            # Extract user info from token
            email = idinfo.get('email')
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '')
            google_id = idinfo.get('sub')

            if not email:
                return Response(
                    {'error': 'Email not provided by Google'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get or create user
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'is_verified': True,
                    'role': 'customer',
                }
            )

            # Update user info if already exists but missing data
            if not created:
                updated = False
                if not user.first_name and first_name:
                    user.first_name = first_name
                    updated = True
                if not user.last_name and last_name:
                    user.last_name = last_name
                    updated = True
                if not user.is_verified:
                    user.is_verified = True
                    updated = True
                if updated:
                    user.save()

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': user.role,
                }
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response(
                {'error': 'Invalid Google credential'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Authentication failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ForgotPasswordView(APIView):
    """Send password reset email."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            
            # Invalidate existing tokens
            PasswordResetToken.objects.filter(user=user, is_used=False).update(is_used=True)
            
            # Create new token
            token_obj = PasswordResetToken.create_token(user)
            
            # Build reset URL
            reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token_obj.token}"
            
            # Send email
            subject = 'Reset Your Password - Zzuhana'
            html_message = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #8B0000;">Password Reset Request</h2>
                    <p>Hi {user.first_name},</p>
                    <p>We received a request to reset your password. Click the button below to create a new password:</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_url}" style="background-color: #8B0000; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">Reset Password</a>
                    </div>
                    <p>This link will expire in 1 hour.</p>
                    <p>If you didn't request this, you can safely ignore this email.</p>
                    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                    <p style="color: #666; font-size: 12px;">This email was sent by Zzuhana. Please do not reply.</p>
                </div>
            </body>
            </html>
            """
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                html_message=html_message,
                fail_silently=False,
            )
            
        except User.DoesNotExist:
            pass  # Don't reveal if email exists
        except Exception as e:
            # Log error but don't reveal to user
            pass
        
        return Response({
            'message': 'If an account with this email exists, you will receive a password reset link.'
        })


class ResetPasswordView(APIView):
    """Reset password with token."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']
        
        try:
            token_obj = PasswordResetToken.objects.get(token=token)
            
            if not token_obj.is_valid():
                return Response(
                    {'error': 'This reset link has expired or already been used.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Reset password
            user = token_obj.user
            user.set_password(new_password)
            user.save()
            
            # Mark token as used
            token_obj.is_used = True
            token_obj.save()
            
            return Response({'message': 'Password has been reset successfully.'})
            
        except PasswordResetToken.DoesNotExist:
            return Response(
                {'error': 'Invalid reset link.'},
                status=status.HTTP_400_BAD_REQUEST
            )


class VerifyEmailView(APIView):
    """Verify email with token."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token = serializer.validated_data['token']
        
        try:
            token_obj = EmailVerificationToken.objects.get(token=token)
            
            if not token_obj.is_valid():
                return Response(
                    {'error': 'This verification link has expired or already been used.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Verify user
            user = token_obj.user
            user.is_verified = True
            user.save()
            
            # Mark token as used
            token_obj.is_used = True
            token_obj.save()
            
            return Response({'message': 'Email verified successfully.'})
            
        except EmailVerificationToken.DoesNotExist:
            return Response(
                {'error': 'Invalid verification link.'},
                status=status.HTTP_400_BAD_REQUEST
            )


class ResendVerificationView(APIView):
    """Resend email verification."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            
            if user.is_verified:
                return Response({'message': 'Email is already verified.'})
            
            # Invalidate existing tokens
            EmailVerificationToken.objects.filter(user=user, is_used=False).update(is_used=True)
            
            # Create new token
            token_obj = EmailVerificationToken.create_token(user)
            
            # Build verification URL
            verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token_obj.token}"
            
            # Send email
            subject = 'Verify Your Email - Zzuhana'
            html_message = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #8B0000;">Welcome to Zzuhana!</h2>
                    <p>Hi {user.first_name},</p>
                    <p>Thank you for creating an account. Please verify your email address by clicking the button below:</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{verify_url}" style="background-color: #8B0000; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">Verify Email</a>
                    </div>
                    <p>This link will expire in 24 hours.</p>
                    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                    <p style="color: #666; font-size: 12px;">This email was sent by Zzuhana. Please do not reply.</p>
                </div>
            </body>
            </html>
            """
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                html_message=html_message,
                fail_silently=False,
            )
            
        except User.DoesNotExist:
            pass  # Don't reveal if email exists
        except Exception as e:
            pass  # Log error but don't reveal to user
        
        return Response({
            'message': 'If an account with this email exists and is not verified, you will receive a verification link.'
        })
