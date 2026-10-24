"""One support profile, one thread per customer, and the messages in it."""
import uuid

from django.conf import settings
from django.db import models


class SupportProfile(models.Model):
    """The person the app shows on every staff reply."""

    display_name = models.CharField(max_length=80, default='Nadia Rahman')
    reply_line = models.CharField(max_length=120, default='Usually replies in 2 min')
    avatar = models.ImageField(upload_to='support/', blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)

    class Meta:
        verbose_name = 'Support profile'
        verbose_name_plural = 'Support profile'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name


class Conversation(models.Model):
    """The customer's open thread. A second one is not created."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='support_conversation',
    )
    topic = models.CharField(max_length=32, blank=True)
    last_message_at = models.DateTimeField(blank=True, null=True)
    customer_unread = models.PositiveIntegerField(default=0)
    staff_unread = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Support conversation'
        verbose_name_plural = 'Support conversations'
        ordering = ['-last_message_at']

    def __str__(self):
        return f'Support · {self.customer_id}'


class Message(models.Model):
    """Text, a topic chip, a photo, or an order card."""

    CUSTOMER = 'customer'
    AGENT = 'agent'
    AUTHOR_CHOICES = [
        (CUSTOMER, 'Customer'),
        (AGENT, 'Agent'),
    ]

    TRACK_ORDER = 'track_order'
    PAYMENT = 'payment'
    RETURN = 'return'
    PRODUCT = 'product'
    TOPIC_CHOICES = [
        (TRACK_ORDER, 'Track my order'),
        (PAYMENT, 'Payment issue'),
        (RETURN, 'Return or refund'),
        (PRODUCT, 'Product question'),
    ]
    TOPIC_LABELS = dict(TOPIC_CHOICES)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    author = models.CharField(max_length=16, choices=AUTHOR_CHOICES)
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='support_replies',
    )
    body = models.TextField(blank=True)
    topic = models.CharField(max_length=32, blank=True, choices=TOPIC_CHOICES)
    image = models.ImageField(upload_to='support/messages/', blank=True)
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='support_messages',
    )
    read_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Support message'
        verbose_name_plural = 'Support messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at'], name='support_msg_thread'),
        ]

    def __str__(self):
        return f'{self.author} · {self.created_at:%Y-%m-%d %H:%M}'
