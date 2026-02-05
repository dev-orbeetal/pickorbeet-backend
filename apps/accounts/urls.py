"""
URL patterns for accounts app.
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    CustomTokenObtainPairView, UserRegistrationView, UserProfileView,
    ChangePasswordView, LogoutView, AddressListCreateView, AddressDetailView,
    StaffUserListCreateView, StaffUserDetailView, CustomerListView, GoogleAuthView,
    ForgotPasswordView, ResetPasswordView, VerifyEmailView, ResendVerificationView
)

urlpatterns = [
    # Authentication
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('google/', GoogleAuthView.as_view(), name='google_auth'),
    
    # Password Reset
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset_password'),
    
    # Email Verification
    path('verify-email/', VerifyEmailView.as_view(), name='verify_email'),
    path('resend-verification/', ResendVerificationView.as_view(), name='resend_verification'),
    
    # Profile
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    
    # Addresses
    path('addresses/', AddressListCreateView.as_view(), name='address_list'),
    path('addresses/<uuid:pk>/', AddressDetailView.as_view(), name='address_detail'),
    
    # Staff Management (Admin)
    path('staff/', StaffUserListCreateView.as_view(), name='staff_list'),
    path('staff/<uuid:pk>/', StaffUserDetailView.as_view(), name='staff_detail'),
    path('customers/', CustomerListView.as_view(), name='customer_list'),
]
