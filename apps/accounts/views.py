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
from .emails import (
    send_otp_email, send_welcome_email, send_google_welcome_email,
    send_password_reset_email, send_password_changed_email
)
from django.conf import settings

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom JWT token obtain view."""
    serializer_class = CustomTokenObtainPairSerializer


class UserRegistrationView(generics.CreateAPIView):
    """User registration endpoint with OTP verification."""
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Create OTP and send verification email
        try:
            otp = EmailVerificationToken.create_otp(user)
            send_otp_email(user, otp.otp_code)
        except Exception as e:
            pass  # Log error but don't fail registration
        
        return Response({
            'message': 'Registration successful. Please check your email for verification code.',
            'user': {
                'id': str(user.id),
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
            'requires_verification': True
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
        
        # Send password changed confirmation email
        try:
            send_password_changed_email(user)
        except Exception:
            pass  # Log error but don't fail
        
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
        from django.db.models import Count, Sum, Q
        queryset = User.objects.filter(
            role='customer'
        ).annotate(
            order_count=Count('orders'),
            total_spent=Sum('orders__total')
        ).filter(
            order_count__gt=0
        ).order_by('-date_joined')
        
        search = self.request.query_params.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search)
            )
        return queryset


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

            # Send welcome email for new Google OAuth users
            if created:
                try:
                    send_google_welcome_email(user)
                except Exception:
                    pass  # Log error but don't fail auth

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
                    'is_verified': user.is_verified,
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
            
            # Build reset URL and send beautiful email
            reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token_obj.token}"
            send_password_reset_email(user, reset_url)
            
        except User.DoesNotExist:
            pass  # Don't reveal if email exists
        except Exception as e:
            pass  # Log error but don't reveal to user
        
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
            
            # Send password changed confirmation email
            try:
                send_password_changed_email(user)
            except Exception:
                pass
            
            return Response({'message': 'Password has been reset successfully.'})
            
        except PasswordResetToken.DoesNotExist:
            return Response(
                {'error': 'Invalid reset link.'},
                status=status.HTTP_400_BAD_REQUEST
            )


class VerifyEmailView(APIView):
    """Verify email with 6-digit OTP code."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp_code = request.data.get('otp_code') or request.data.get('token')
        
        if not email or not otp_code:
            return Response(
                {'error': 'Email and OTP code are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=email)
            
            # Find valid OTP for this user
            otp_obj = EmailVerificationToken.objects.filter(
                user=user,
                otp_code=otp_code,
                is_used=False
            ).first()
            
            if not otp_obj:
                return Response(
                    {'error': 'Invalid verification code.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not otp_obj.is_valid():
                return Response(
                    {'error': 'Verification code has expired. Please request a new one.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Verify user
            user.is_verified = True
            user.save()
            
            # Mark OTP as used
            otp_obj.is_used = True
            otp_obj.save()
            
            # Send welcome email
            try:
                send_welcome_email(user)
            except Exception:
                pass
            
            # Generate JWT tokens for auto-login
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'message': 'Email verified successfully! Welcome to Pickorbeet!',
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': user.role,
                    'is_verified': True,
                }
            })
            
        except User.DoesNotExist:
            return Response(
                {'error': 'Invalid email address.'},
                status=status.HTTP_400_BAD_REQUEST
            )


class ResendVerificationView(APIView):
    """Resend OTP verification code."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            
            if user.is_verified:
                return Response({'message': 'Email is already verified.'})
            
            # Create new OTP and send email
            otp = EmailVerificationToken.create_otp(user)
            send_otp_email(user, otp.otp_code)
            
        except User.DoesNotExist:
            pass  # Don't reveal if email exists
        except Exception as e:
            pass  # Log error but don't reveal to user
        
        return Response({
            'message': 'If an account with this email exists and is not verified, you will receive a new verification code.'
        })
