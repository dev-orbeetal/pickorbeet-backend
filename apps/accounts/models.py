"""
Custom User Model and Account related models for Pickorbeet E-commerce.
"""
import os
import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


def avatar_upload_path(instance, filename):
    """Store each photo under its owner with a new name so replacements are not cached."""
    extension = os.path.splitext(filename or '')[1].lower()
    if extension not in {'.jpg', '.jpeg', '.png', '.webp'}:
        extension = '.jpg'
    owner = instance.pk or 'new'
    return f'avatars/{owner}/{uuid.uuid4().hex}{extension}'


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication."""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'super_admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom User model with role-based access control."""
    
    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('seller', 'Seller'),
        ('accountant', 'Accountant'),
        ('super_admin', 'Super Admin'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    avatar = models.ImageField(upload_to=avatar_upload_path, blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    two_factor_enabled = models.BooleanField(default=False)
    recovery_email = models.EmailField(blank=True, null=True, unique=True)
    recovery_email_verified = models.BooleanField(default=False)
    
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(blank=True, null=True)
    
    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def is_seller(self):
        return self.role == 'seller'

    def is_accountant(self):
        return self.role == 'accountant'

    def is_super_admin(self):
        return self.role == 'super_admin'


class BdDivision(models.Model):
    """Bangladesh administrative division (catalog for address cascade)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = 'BD Division'
        verbose_name_plural = 'BD Divisions'

    def __str__(self):
        return self.name


class BdDistrict(models.Model):
    """District under a Bangladesh division."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    division = models.ForeignKey(BdDivision, on_delete=models.CASCADE, related_name='districts')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)

    class Meta:
        ordering = ['name']
        unique_together = [('division', 'slug')]
        verbose_name = 'BD District'
        verbose_name_plural = 'BD Districts'

    def __str__(self):
        return f'{self.name} ({self.division.name})'


class BdPostOffice(models.Model):
    """Post office + postal code under a district."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    district = models.ForeignKey(BdDistrict, on_delete=models.CASCADE, related_name='post_offices')
    name = models.CharField(max_length=150)
    postal_code = models.CharField(max_length=20, db_index=True)

    class Meta:
        ordering = ['name', 'postal_code']
        unique_together = [('district', 'name', 'postal_code')]
        verbose_name = 'BD Post Office'
        verbose_name_plural = 'BD Post Offices'

    def __str__(self):
        return f'{self.name} ({self.postal_code})'


class Address(models.Model):
    """Address model for shipping and billing."""
    
    ADDRESS_TYPE_CHOICES = [
        ('shipping', 'Shipping'),
        ('billing', 'Billing'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses', null=True, blank=True)
    address_type = models.CharField(max_length=20, choices=ADDRESS_TYPE_CHOICES, default='shipping')
    # What the customer calls this place: Home, Office, or a short custom name.
    label = models.CharField(max_length=40, blank=True, default='')

    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    division = models.CharField(max_length=100, blank=True, default='')
    city = models.CharField(max_length=100)
    district = models.CharField(max_length=100)
    post_office = models.CharField(max_length=150, blank=True, default='')
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, default='Bangladesh')
    
    is_default = models.BooleanField(default=False)
    is_inside_dhaka = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Address'
        verbose_name_plural = 'Addresses'
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.full_name} - {self.address_line1}, {self.city}"

    def save(self, *args, **kwargs):
        from apps.accounts.bd_geo import is_inside_dhaka as detect_dhaka
        self.is_inside_dhaka = detect_dhaka(
            city=self.city,
            district=self.district,
            division=self.division,
        )
        super().save(*args, **kwargs)
        if self.is_default and self.user_id:
            Address.objects.filter(user_id=self.user_id).exclude(pk=self.pk).update(is_default=False)


class EmailVerificationToken(models.Model):
    """Token for email verification using 6-digit OTP."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_tokens')
    otp_code = models.CharField(max_length=6, default='000000')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Email Verification Token'
        verbose_name_plural = 'Email Verification Tokens'

    def __str__(self):
        return f"OTP for {self.user.email}"

    def is_valid(self):
        return not self.is_used and self.expires_at > timezone.now() and self.attempts < 5

    def increment_attempts(self):
        self.attempts += 1
        self.save()

    @classmethod
    def create_otp(cls, user):
        import random
        from datetime import timedelta
        # Invalidate existing OTPs
        cls.objects.filter(user=user, is_used=False).update(is_used=True)
        # Generate 6-digit OTP
        otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        expires_at = timezone.now() + timedelta(minutes=10)
        return cls.objects.create(user=user, otp_code=otp_code, expires_at=expires_at)


class PasswordResetToken(models.Model):
    """Token for password reset."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_tokens')
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Password Reset Token'
        verbose_name_plural = 'Password Reset Tokens'

    def __str__(self):
        return f"Password reset token for {self.user.email}"

    def is_valid(self):
        return not self.is_used and self.expires_at > timezone.now()

    @classmethod
    def create_token(cls, user):
        import secrets
        from datetime import timedelta
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(hours=1)
        return cls.objects.create(user=user, token=token, expires_at=expires_at)


class AuthSession(models.Model):
    """A signed-in device. Access and refresh tokens carry this row's id as `sid`."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='auth_sessions')
    device_id = models.CharField(max_length=128, blank=True, default='')
    device_name = models.CharField(max_length=120, blank=True, default='')
    platform = models.CharField(max_length=20, blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    refresh_jti = models.CharField(max_length=255, blank=True, default='', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Auth session'
        verbose_name_plural = 'Auth sessions'
        ordering = ['-last_seen']
        indexes = [
            models.Index(fields=['user', 'revoked_at']),
        ]

    def __str__(self):
        return f'{self.device_name or self.platform or "Device"} · {self.user.email}'


class LoginEvent(models.Model):
    """One attempt to sign in. Kept after the session is gone."""

    PASSWORD = 'password'
    GOOGLE = 'google'
    TWO_FACTOR = 'two_factor'
    VERIFICATION = 'verification'
    METHOD_CHOICES = [
        (PASSWORD, 'Password'),
        (GOOGLE, 'Google'),
        (TWO_FACTOR, 'Two-factor'),
        (VERIFICATION, 'Email verification'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_events', null=True, blank=True)
    email = models.EmailField(blank=True, default='')
    success = models.BooleanField(default=False)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    device_id = models.CharField(max_length=128, blank=True, default='')
    device_name = models.CharField(max_length=120, blank=True, default='')
    platform = models.CharField(max_length=20, blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Login event'
        verbose_name_plural = 'Login events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        outcome = 'ok' if self.success else 'failed'
        return f'{self.email or self.user_id} {self.method} {outcome}'


class SecurityCode(models.Model):
    """Short-lived emailed code. The code and the challenge are stored as hashes."""

    LOGIN = 'login_2fa'
    ENABLE = 'enable_2fa'
    DISABLE = 'disable_2fa'
    RECOVERY = 'recovery_email'
    PURPOSE_CHOICES = [
        (LOGIN, 'Login'),
        (ENABLE, 'Enable two-factor'),
        (DISABLE, 'Disable two-factor'),
        (RECOVERY, 'Recovery email'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='security_codes')
    purpose = models.CharField(max_length=32, choices=PURPOSE_CHOICES)
    code_hash = models.CharField(max_length=64)
    challenge_hash = models.CharField(max_length=64, unique=True)
    target_email = models.EmailField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    last_sent_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'Security code'
        verbose_name_plural = 'Security codes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'purpose']),
        ]

    def __str__(self):
        return f'{self.purpose} for {self.user.email}'
