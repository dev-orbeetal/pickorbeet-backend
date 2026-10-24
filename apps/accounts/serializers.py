"""
Serializers for accounts app.
"""
import re

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import Address

MAX_AVATAR_BYTES = 2 * 1024 * 1024
_BD_MOBILE = re.compile(r'^01[3-9]\d{8}$')


def _normalize_bd_mobile(raw):
    """11-digit Bangladeshi mobile, matching the number stored on delivery addresses."""
    digits = re.sub(r'\D', '', raw or '')
    if digits.startswith('880'):
        digits = digits[2:]
    elif digits.startswith('88') and len(digits) == 13:
        digits = digits[2:]
    if len(digits) == 10 and digits.startswith('1'):
        digits = f'0{digits}'
    if not _BD_MOBILE.fullmatch(digits):
        raise serializers.ValidationError('Enter a Bangladeshi mobile number, such as 01712345678.')
    return digits


def _looks_like_photo(header):
    if header.startswith(b'\xff\xd8\xff'):
        return True
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return True
    return len(header) >= 12 and header.startswith(b'RIFF') and header[8:12] == b'WEBP'


class ProfileAvatarField(serializers.ImageField):
    """JPEG, PNG, or WebP, at most 2 MB. The type is read from the file, not its name."""

    default_error_messages = {
        'invalid_type': 'Upload a JPEG, PNG, or WebP photo.',
        'max_size': 'Profile photos must be 2 MB or smaller.',
        'empty': 'Choose a photo to upload.',
    }

    def to_internal_value(self, data):
        size = getattr(data, 'size', None)
        if size == 0:
            self.fail('empty')
        if size is not None and size > MAX_AVATAR_BYTES:
            self.fail('max_size')
        if hasattr(data, 'read'):
            header = data.read(16)
            if hasattr(data, 'seek'):
                data.seek(0)
            if not _looks_like_photo(header):
                self.fail('invalid_type')
        return super().to_internal_value(data)

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT token serializer with additional user data."""
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['role'] = user.role
        token['full_name'] = user.full_name
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = {
            'id': str(self.user.id),
            'email': self.user.email,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'role': self.user.role,
            'full_name': self.user.full_name,
        }
        return data


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""

    full_name = serializers.ReadOnlyField()
    order_count = serializers.IntegerField(read_only=True, default=0)
    total_spent = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, default=0)
    avatar = ProfileAvatarField(required=False, allow_null=True)
    clear_avatar = serializers.BooleanField(required=False, default=False, write_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'phone', 'first_name', 'last_name', 'role',
                  'full_name', 'is_active', 'is_verified', 'date_joined',
                  'order_count', 'total_spent', 'address', 'city', 'postal_code',
                  'avatar', 'clear_avatar']
        read_only_fields = ['id', 'email', 'is_active', 'is_verified', 'date_joined', 'role']

    def validate_first_name(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Enter your first name.')
        return value

    def validate_last_name(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Enter your last name.')
        return value

    def validate_phone(self, value):
        if value is None or not str(value).strip():
            return ''
        return _normalize_bd_mobile(value)

    def update(self, instance, validated_data):
        clear = bool(validated_data.pop('clear_avatar', False))
        uploaded = validated_data.pop('avatar', serializers.empty)
        previous = instance.avatar.name if instance.avatar else ''
        storage = instance.avatar.storage
        if uploaded is not serializers.empty:
            validated_data['avatar'] = uploaded
        elif clear:
            validated_data['avatar'] = None
        user = super().update(instance, validated_data)
        current = user.avatar.name if user.avatar else ''
        if previous and previous != current:
            storage.delete(previous)
        return user


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""
    
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'phone', 'first_name', 'last_name', 'password', 'password_confirm']

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Passwords don't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class StaffUserSerializer(serializers.ModelSerializer):
    """Serializer for staff users (admin panel)."""
    
    password = serializers.CharField(write_only=True, required=False)
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = ['id', 'email', 'phone', 'first_name', 'last_name', 'role', 
                  'full_name', 'is_active', 'is_staff', 'password', 'date_joined']
        read_only_fields = ['id', 'date_joined']

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        user.is_staff = validated_data.get('role') in ['seller', 'accountant', 'super_admin']
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class AddressSerializer(serializers.ModelSerializer):
    """Serializer for Address model."""

    class Meta:
        model = Address
        fields = ['id', 'user', 'address_type', 'label', 'full_name', 'phone',
                  'address_line1', 'address_line2', 'city', 'district',
                  'postal_code', 'country', 'is_default', 'is_inside_dhaka']
        read_only_fields = ['id', 'user', 'is_inside_dhaka']


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change."""
    
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "New passwords don't match."})
        return attrs


class ForgotPasswordSerializer(serializers.Serializer):
    """Serializer for forgot password request."""
    email = serializers.EmailField(required=True)


class ResetPasswordSerializer(serializers.Serializer):
    """Serializer for password reset."""
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "Passwords don't match."})
        return attrs


class EmailVerificationSerializer(serializers.Serializer):
    """Serializer for email verification."""
    token = serializers.CharField(required=True)


class ResendVerificationSerializer(serializers.Serializer):
    """Serializer for resending verification email."""
    email = serializers.EmailField(required=True)
