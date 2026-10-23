"""
Courier shipments for orders.
"""
import uuid

from django.conf import settings
from django.db import models


class Shipment(models.Model):
    """A parcel booked with a courier for one order."""

    COURIER_STEADFAST = 'steadfast'
    COURIER_CHOICES = [
        (COURIER_STEADFAST, 'Steadfast Courier'),
    ]

    # Delivery statuses reported by Steadfast.
    STATUS_CHOICES = [
        ('in_review', 'In review'),
        ('pending', 'Pending'),
        ('hold', 'On hold'),
        ('delivered_approval_pending', 'Delivered (approval pending)'),
        ('partial_delivered_approval_pending', 'Partially delivered (approval pending)'),
        ('cancelled_approval_pending', 'Cancelled (approval pending)'),
        ('unknown_approval_pending', 'Unknown (approval pending)'),
        ('delivered', 'Delivered'),
        ('partial_delivered', 'Partially delivered'),
        ('cancelled', 'Cancelled'),
        ('unknown', 'Unknown'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='shipment')
    courier = models.CharField(max_length=30, choices=COURIER_CHOICES, default=COURIER_STEADFAST)

    invoice = models.CharField(max_length=100, help_text='Invoice sent to the courier (the order number)')
    consignment_id = models.CharField(max_length=50, blank=True, default='', db_index=True)
    tracking_code = models.CharField(max_length=64, blank=True, default='', db_index=True)
    tracking_url = models.URLField(max_length=500, blank=True, default='')

    # Free-form so a status Steadfast adds later is stored rather than rejected.
    status = models.CharField(max_length=64, default='in_review', db_index=True)
    status_message = models.TextField(blank=True, default='')

    recipient_name = models.CharField(max_length=100, blank=True, default='')
    recipient_phone = models.CharField(max_length=20, blank=True, default='')
    recipient_address = models.CharField(max_length=250, blank=True, default='')
    cod_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_charge = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Courier charge reported by Steadfast',
    )
    note = models.CharField(max_length=500, blank=True, default='')

    booked_at = models.DateTimeField(null=True, blank=True)
    booked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='booked_shipments',
    )
    status_updated_at = models.DateTimeField(null=True, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Shipment'
        verbose_name_plural = 'Shipments'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_courier_display()} {self.tracking_code or self.consignment_id or self.invoice}'

    @property
    def status_label(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status.replace('_', ' ').capitalize())


class ShipmentEvent(models.Model):
    """One status report about a shipment: the booking, a poll, or a webhook."""

    SOURCE_CHOICES = [
        ('booking', 'Booking'),
        ('poll', 'Status check'),
        ('webhook', 'Webhook'),
        ('manual', 'Manual'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='events')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    status = models.CharField(max_length=64, blank=True, default='')
    message = models.TextField(blank=True, default='')
    idempotency_key = models.CharField(max_length=128, unique=True, null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Shipment Event'
        verbose_name_plural = 'Shipment Events'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.shipment} · {self.get_source_display()} · {self.status or "message"}'
