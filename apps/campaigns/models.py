"""Product notifications: templates, campaigns, automation rules, and what the catalog watcher last saw."""
import uuid
from datetime import time

from django.conf import settings
from django.db import models

KIND_NEW_ARRIVAL = 'new_arrival'
KIND_LOW_STOCK = 'low_stock'
KIND_BACK_IN_STOCK = 'back_in_stock'
KIND_PRICE_DROP = 'price_drop'
KIND_FLASH_SALE = 'flash_sale'
KIND_CUSTOM = 'custom'

KIND_CHOICES = [
    (KIND_NEW_ARRIVAL, 'New arrival'),
    (KIND_LOW_STOCK, 'Almost gone'),
    (KIND_BACK_IN_STOCK, 'Back in stock'),
    (KIND_PRICE_DROP, 'Price drop'),
    (KIND_FLASH_SALE, 'Flash sale'),
    (KIND_CUSTOM, 'Custom'),
]

AUDIENCE_ALL = 'all'
AUDIENCE_INTERESTED = 'interested'
AUDIENCE_WISHLIST = 'wishlist'
AUDIENCE_CART = 'cart'
AUDIENCE_BUYERS = 'buyers'
AUDIENCE_CUSTOMERS = 'customers'

AUDIENCE_CHOICES = [
    (AUDIENCE_ALL, 'All customers'),
    (AUDIENCE_INTERESTED, 'Saved it or have it in the cart'),
    (AUDIENCE_WISHLIST, 'Saved it in the wishlist'),
    (AUDIENCE_CART, 'Have it in the cart'),
    (AUDIENCE_BUYERS, 'Bought from the category'),
    (AUDIENCE_CUSTOMERS, 'Chosen customers'),
]

# Audiences that need a product to know who is interested.
PRODUCT_AUDIENCES = {AUDIENCE_INTERESTED, AUDIENCE_WISHLIST, AUDIENCE_CART}


class CampaignTemplate(models.Model):
    """Ready-made wording an admin starts a campaign from. ``{{placeholders}}`` fill in per product."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=24, choices=KIND_CHOICES)
    name = models.CharField(max_length=80)
    title = models.CharField(max_length=80)
    body = models.CharField(max_length=240)
    cta_label = models.CharField(max_length=40, default='Tap to explore')
    is_recommended = models.BooleanField(default=False)
    is_system = models.BooleanField(default=False, help_text='Shipped with the store. Can be edited, not deleted.')
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name


class Campaign(models.Model):
    """One send to many customers, written by an admin or started by an automation."""

    STATUS_DRAFT = 'draft'
    STATUS_SCHEDULED = 'scheduled'
    STATUS_SENDING = 'sending'
    STATUS_SENT = 'sent'
    STATUS_CANCELLED = 'cancelled'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_SENDING, 'Sending'),
        (STATUS_SENT, 'Sent'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_FAILED, 'Failed'),
    ]
    EDITABLE_STATUSES = {STATUS_DRAFT, STATUS_SCHEDULED}

    SOURCE_MANUAL = 'manual'
    SOURCE_AUTOMATION = 'automation'
    SOURCE_CHOICES = [(SOURCE_MANUAL, 'Manual'), (SOURCE_AUTOMATION, 'Automation')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, blank=True)
    kind = models.CharField(max_length=24, choices=KIND_CHOICES, default=KIND_CUSTOM)
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    trigger = models.CharField(max_length=24, blank=True)
    title = models.CharField(max_length=80)
    body = models.CharField(max_length=240)
    cta_label = models.CharField(max_length=40, blank=True, default='Tap to explore')
    product = models.ForeignKey(
        'products.Product', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    # A new-arrival digest announces several products; the first is ``product``.
    product_ids = models.JSONField(default=list, blank=True)
    category = models.ForeignKey(
        'products.Category', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    image = models.ImageField(upload_to='notifications/campaigns/', blank=True, null=True)
    # Placeholder values fixed when the campaign was made, such as the price before a drop.
    context = models.JSONField(default=dict, blank=True)
    audience = models.CharField(max_length=16, choices=AUDIENCE_CHOICES, default=AUDIENCE_ALL)
    customer_ids = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    recipients = models.PositiveIntegerField(default=0)
    pushed = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status', 'scheduled_for'], name='campaign_status_due')]

    def __str__(self):
        return self.name or self.title


class AutomationRule(models.Model):
    """What the catalog watcher sends on its own, and to whom."""

    TRIGGER_CHOICES = [
        (KIND_NEW_ARRIVAL, 'New product published'),
        (KIND_LOW_STOCK, 'Stock is running out'),
        (KIND_BACK_IN_STOCK, 'Back in stock'),
        (KIND_PRICE_DROP, 'Price dropped'),
    ]

    trigger = models.CharField(max_length=24, choices=TRIGGER_CHOICES, primary_key=True)
    enabled = models.BooleanField(default=True)
    title = models.CharField(max_length=80)
    body = models.CharField(max_length=240)
    # New arrivals only: the wording when several products went live together.
    digest_title = models.CharField(max_length=80, blank=True)
    digest_body = models.CharField(max_length=240, blank=True)
    cta_label = models.CharField(max_length=40, blank=True, default='Tap to explore')
    audience = models.CharField(max_length=16, choices=AUDIENCE_CHOICES, default=AUDIENCE_INTERESTED)
    threshold = models.PositiveIntegerField(
        default=0, help_text='Almost gone: units left or fewer. Price drop: percent off or more.',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['trigger']

    def __str__(self):
        return self.get_trigger_display()


class CampaignSettings(models.Model):
    """Store-wide limits for automated product notifications. One row."""

    quiet_start = models.TimeField(default=time(22, 0))
    quiet_end = models.TimeField(default=time(9, 0))
    daily_cap = models.PositiveSmallIntegerField(
        default=3, help_text='Most automated product notifications one customer gets in 24 hours.',
    )
    arrival_settle_minutes = models.PositiveSmallIntegerField(
        default=10, help_text='Wait after a product goes live, so its photos are in and close uploads go out together.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Campaign settings'

    @classmethod
    def load(cls):
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance


class ProductWatch(models.Model):
    """What the catalog watcher last saw for a product, so it alerts on changes only."""

    product = models.OneToOneField(
        'products.Product', on_delete=models.CASCADE, primary_key=True, related_name='notification_watch',
    )
    announced_at = models.DateTimeField(null=True, blank=True)
    # Rows made for products that existed before the watcher record state on first look and alert on nothing.
    primed = models.BooleanField(default=True)
    units = models.IntegerField(default=0)
    available = models.BooleanField(default=False)
    low_alerted = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    checked_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'watch:{self.product_id}'
