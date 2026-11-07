"""Persisted inbox rows and the phones that can receive them as push."""
import uuid

from django.conf import settings
from django.db import models


class Device(models.Model):
    """One FCM registration for a signed-in phone."""

    PLATFORM_CHOICES = [
        ('android', 'Android'),
        ('ios', 'iOS'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_devices',
    )
    token = models.TextField(blank=True)
    platform = models.CharField(max_length=16, choices=PLATFORM_CHOICES)
    device_id = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Device'
        verbose_name_plural = 'Devices'
        constraints = [
            models.UniqueConstraint(fields=['user', 'device_id'], name='unique_user_device'),
        ]

    def __str__(self):
        return f'{self.platform}:{self.device_id}'


class Notification(models.Model):
    """One inbox row for one recipient. The same event is stored once per person."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    kind = models.CharField(max_length=64)
    title = models.CharField(max_length=200)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    dedupe_key = models.CharField(max_length=200)
    read_at = models.DateTimeField(blank=True, null=True)
    push_sent_at = models.DateTimeField(blank=True, null=True)
    campaign = models.ForeignKey(
        'campaigns.Campaign',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['recipient', 'dedupe_key'],
                name='unique_recipient_dedupe',
            ),
        ]
        indexes = [
            models.Index(fields=['recipient', '-created_at'], name='notif_recipient_created'),
            models.Index(fields=['recipient', 'read_at'], name='notif_recipient_read'),
        ]

    def __str__(self):
        return f'{self.kind} → {self.recipient_id}'


class NotificationPreference(models.Model):
    """What a customer agreed to receive beyond their own orders and chats."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='notification_preference',
    )
    offers = models.BooleanField(default=True, help_text='New arrivals, stock alerts, price drops and sales.')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'preferences:{self.user_id}'
