import re

from rest_framework import serializers

from apps.accounts.serializers import _normalize_bd_mobile

from .models import CareerApplication

MAX_CV_BYTES = 5 * 1024 * 1024
MAX_PICTURE_BYTES = 2 * 1024 * 1024
_STUDENT_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9 \-]{2,30}[A-Za-z0-9]$')


def _required_text(value, message):
    cleaned = ' '.join((value or '').split())
    if not cleaned:
        raise serializers.ValidationError(message)
    return cleaned


def _looks_like_photo(header):
    if header.startswith(b'\xff\xd8\xff'):
        return True
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return True
    return len(header) >= 12 and header.startswith(b'RIFF') and header[8:12] == b'WEBP'


class CareerCvField(serializers.FileField):
    """PDF only, read from the file bytes, up to 5 MB."""

    default_error_messages = {
        'invalid_type': 'Upload your CV as a PDF.',
        'max_size': 'CV must be 5 MB or smaller.',
        'empty': 'Choose a CV to upload.',
    }

    def to_internal_value(self, data):
        size = getattr(data, 'size', None)
        if size == 0:
            self.fail('empty')
        if size is not None and size > MAX_CV_BYTES:
            self.fail('max_size')
        if hasattr(data, 'read'):
            header = data.read(8)
            if hasattr(data, 'seek'):
                data.seek(0)
            if not header.startswith(b'%PDF'):
                self.fail('invalid_type')
        return super().to_internal_value(data)


class CareerPictureField(serializers.ImageField):
    """JPEG, PNG, or WebP, confirmed with Pillow, up to 2 MB."""

    default_error_messages = {
        'invalid_type': 'Upload a JPEG, PNG, or WebP photo.',
        'max_size': 'Photos must be 2 MB or smaller.',
        'empty': 'Choose a photo to upload.',
    }

    def to_internal_value(self, data):
        size = getattr(data, 'size', None)
        if size == 0:
            self.fail('empty')
        if size is not None and size > MAX_PICTURE_BYTES:
            self.fail('max_size')
        if hasattr(data, 'read'):
            header = data.read(16)
            if hasattr(data, 'seek'):
                data.seek(0)
            if not _looks_like_photo(header):
                self.fail('invalid_type')
        return super().to_internal_value(data)


class CareerApplicationSubmitSerializer(serializers.ModelSerializer):
    cv = CareerCvField()
    picture = CareerPictureField()

    class Meta:
        model = CareerApplication
        fields = [
            'name', 'email', 'phone', 'university', 'session',
            'department', 'student_id', 'cv', 'picture',
        ]

    def validate_name(self, value):
        return _required_text(value, 'Enter your name.')

    def validate_email(self, value):
        return value.strip().lower()

    def validate_phone(self, value):
        return _normalize_bd_mobile(value)

    def validate_university(self, value):
        return _required_text(value, 'Enter your university.')

    def validate_session(self, value):
        return _required_text(value, 'Enter your session.')

    def validate_department(self, value):
        return _required_text(value, 'Enter your department.')

    def validate_student_id(self, value):
        cleaned = ' '.join((value or '').split())
        if not _STUDENT_ID.fullmatch(cleaned):
            raise serializers.ValidationError(
                'Enter a student ID of 4 to 32 letters, numbers, spaces, or hyphens.'
            )
        return cleaned


class CareerApplicationSerializer(serializers.ModelSerializer):
    """Staff view. File paths stay off the payload; downloads use a separate route."""

    has_cv = serializers.SerializerMethodField()
    has_picture = serializers.SerializerMethodField()

    class Meta:
        model = CareerApplication
        fields = [
            'id', 'name', 'email', 'phone', 'university', 'session', 'department',
            'student_id', 'has_cv', 'has_picture', 'status', 'admin_notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'name', 'email', 'phone', 'university', 'session', 'department',
            'student_id', 'created_at', 'updated_at',
        ]

    def get_has_cv(self, obj):
        return bool(obj.cv)

    def get_has_picture(self, obj):
        return bool(obj.picture)
