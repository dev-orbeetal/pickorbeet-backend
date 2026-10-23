from django.contrib import admin

from .models import Device, Notification


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['user', 'platform', 'device_id', 'is_active', 'last_seen']
    list_filter = ['platform', 'is_active']
    search_fields = ['user__email', 'device_id']
    readonly_fields = ['created_at', 'updated_at', 'last_seen']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'kind', 'title', 'read_at', 'created_at']
    list_filter = ['kind']
    search_fields = ['recipient__email', 'title', 'dedupe_key']
    readonly_fields = ['created_at', 'push_sent_at']
