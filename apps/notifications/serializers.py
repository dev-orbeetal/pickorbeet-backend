"""Shapes clients see for the inbox and device registration."""
from rest_framework import serializers

from .models import Device, Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'kind', 'title', 'body', 'data', 'read_at', 'created_at']
        read_only_fields = fields


class DeviceRegisterSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=4096, trim_whitespace=True)
    platform = serializers.ChoiceField(choices=Device.PLATFORM_CHOICES)
    device_id = serializers.RegexField(r'^[-A-Za-z0-9_.]{1,128}$')


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ['id', 'platform', 'device_id', 'is_active', 'last_seen']
        read_only_fields = fields
