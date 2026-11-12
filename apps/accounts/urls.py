"""
URL patterns for accounts app.
"""
from django.urls import path
from .views import (
    CustomTokenObtainPairView, UserRegistrationView, UserProfileView,
    ChangePasswordView, LogoutView, AddressListCreateView, AddressDetailView,
    StaffUserListCreateView, StaffUserDetailView, CustomerListView, CustomerSummaryView,
    CustomerDetailView, CustomerAddressListCreateView, CustomerAddressDetailView,
    GoogleAuthView, ForgotPasswordView, ResetPasswordView, VerifyEmailView,
    ResendVerificationView,
)
from .security_views import (
    SessionTokenRefreshView, TwoFactorVerifyView, TwoFactorResendView,
    TwoFactorEnableView, TwoFactorEnableConfirmView, TwoFactorDisableView,
    SessionListView, SessionRevokeView, SessionRevokeOthersView, LoginActivityView,
    RecoveryEmailView, RecoveryEmailConfirmView,
)

urlpatterns = [
    # Authentication
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', SessionTokenRefreshView.as_view(), name='token_refresh'),
    path('2fa/verify/', TwoFactorVerifyView.as_view(), name='two_factor_verify'),
    path('2fa/resend/', TwoFactorResendView.as_view(), name='two_factor_resend'),
    path('2fa/enable/', TwoFactorEnableView.as_view(), name='two_factor_enable'),
    path('2fa/enable/confirm/', TwoFactorEnableConfirmView.as_view(), name='two_factor_enable_confirm'),
    path('2fa/disable/', TwoFactorDisableView.as_view(), name='two_factor_disable'),
    path('sessions/', SessionListView.as_view(), name='session_list'),
    path('sessions/revoke-others/', SessionRevokeOthersView.as_view(), name='session_revoke_others'),
    path('sessions/<uuid:pk>/revoke/', SessionRevokeView.as_view(), name='session_revoke'),
    path('login-activity/', LoginActivityView.as_view(), name='login_activity'),
    path('recovery-email/', RecoveryEmailView.as_view(), name='recovery_email'),
    path('recovery-email/confirm/', RecoveryEmailConfirmView.as_view(), name='recovery_email_confirm'),
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
    path('customers/summary/', CustomerSummaryView.as_view(), name='customer_summary'),
    path('customers/<uuid:pk>/', CustomerDetailView.as_view(), name='customer_detail'),
    path('customers/<uuid:pk>/addresses/', CustomerAddressListCreateView.as_view(), name='customer_addresses'),
    path(
        'customers/<uuid:pk>/addresses/<uuid:address_id>/',
        CustomerAddressDetailView.as_view(),
        name='customer_address_detail',
    ),
]
