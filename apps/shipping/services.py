"""
Booking and tracking Steadfast shipments.

Views, the Django admin, the webhook and ``manage.py sync_shipments`` all go
through these functions so the rules live in one place.
"""
import logging
import re
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.orders.models import Order
from apps.orders.services import change_order_status

from .models import Shipment, ShipmentEvent
from .steadfast import (
    SteadfastAuthError,
    SteadfastClient,
    SteadfastConfigError,
    SteadfastDuplicateError,
    SteadfastError,
    SteadfastNetworkError,
    SteadfastValidationError,
)

logger = logging.getLogger(__name__)

REFRESH_COOLDOWN = timedelta(seconds=60)  # Steadfast caches status for 60 s

# Courier status -> the group clients colour and label by.
STATUS_GROUPS = {
    'in_review': 'in_review',
    'pending': 'pending',
    'hold': 'hold',
    'delivered': 'delivered',
    'delivered_approval_pending': 'delivered',
    'partial_delivered': 'partial_delivered',
    'partial_delivered_approval_pending': 'partial_delivered',
    'cancelled': 'cancelled',
    'cancelled_approval_pending': 'cancelled',
    'unknown': 'unknown',
    'unknown_approval_pending': 'unknown',
}
STATUS_GROUP_ORDER = ['in_review', 'pending', 'hold', 'delivered', 'partial_delivered', 'cancelled', 'unknown']
FINAL_STATUSES = {'delivered', 'partial_delivered', 'cancelled'}
BOOKABLE_ORDER_STATUSES = {'pending', 'confirmed', 'processing', 'shipped', 'out_for_delivery'}

_STATUS_ALIASES = {
    'canceled': 'cancelled',
    'canceled_approval_pending': 'cancelled_approval_pending',
    'partially_delivered': 'partial_delivered',
    'partially_delivered_approval_pending': 'partial_delivered_approval_pending',
    'on_hold': 'hold',
    'review': 'in_review',
}


class ShipmentError(Exception):
    """A booking or tracking request that cannot be completed."""

    def __init__(self, code, message, http_status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


class ShipmentCooldown(ShipmentError):
    def __init__(self, retry_after):
        super().__init__(
            'refresh_cooldown',
            f'Status was checked moments ago. Try again in {retry_after} seconds.',
            http_status=429,
        )
        self.retry_after = retry_after


# -- small helpers ---------------------------------------------------------------------

def normalize_status(raw):
    value = re.sub(r'[\s\-]+', '_', str(raw or '').strip().lower())
    return _STATUS_ALIASES.get(value, value)


def status_group(status):
    return STATUS_GROUPS.get(normalize_status(status), 'unknown')


def is_final(status):
    return normalize_status(status) in FINAL_STATUSES


def normalize_phone(raw):
    """Return an 11-digit Bangladeshi mobile number (01XXXXXXXXX)."""
    digits = re.sub(r'\D', '', raw or '')
    if digits.startswith('880'):
        digits = digits[2:]
    elif digits.startswith('88') and len(digits) == 13:
        digits = digits[2:]
    if len(digits) == 10 and digits.startswith('1'):
        digits = f'0{digits}'
    if not re.fullmatch(r'01[3-9]\d{8}', digits):
        raise ShipmentError(
            'invalid_phone',
            'The shipping phone must be a Bangladeshi mobile number such as 01712345678.',
        )
    return digits


def cod_amount_for(order):
    """Cash to collect: nothing when already paid, otherwise the total in whole taka."""
    if order.payment_status == 'paid':
        return 0
    return int(Decimal(order.total).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def recipient_address_for(order):
    parts = [order.shipping_address_line1, order.shipping_address_line2, order.shipping_city]
    if order.shipping_district and order.shipping_district.lower() != (order.shipping_city or '').lower():
        parts.append(order.shipping_district)
    if order.shipping_postal_code:
        parts.append(order.shipping_postal_code)
    address = ', '.join(part.strip() for part in parts if part and part.strip())
    return address[:250]


def item_description_for(order):
    lines = [f'{item.product_name} x{item.quantity}' for item in order.items.all()]
    return ', '.join(lines)[:250]


def tracking_url_for(tracking_code):
    if not tracking_code:
        return ''
    return settings.STEADFAST_TRACKING_URL.format(code=tracking_code)


def seconds_until_refresh(shipment, now=None):
    if not shipment.last_checked_at:
        return 0
    now = now or timezone.now()
    remaining = REFRESH_COOLDOWN - (now - shipment.last_checked_at)
    return max(0, int(remaining.total_seconds() + 0.999))


def _courier_failure(exc):
    """Translate a client error into a ShipmentError with a sensible HTTP status."""
    if isinstance(exc, SteadfastConfigError):
        return ShipmentError(exc.code, exc.message, 503)
    if isinstance(exc, SteadfastDuplicateError):
        return ShipmentError(
            exc.code,
            'Steadfast already has a parcel for this invoice. Check the Steadfast portal and '
            'record the tracking code on the shipment in Django admin.',
            409,
        )
    if isinstance(exc, SteadfastValidationError):
        return ShipmentError(exc.code, f'Steadfast rejected the parcel: {exc.message}', 400)
    if isinstance(exc, SteadfastAuthError):
        return ShipmentError(exc.code, exc.message, 502)
    if isinstance(exc, SteadfastNetworkError):
        return ShipmentError(exc.code, exc.message, 503)
    return ShipmentError(exc.code, exc.message, 502)


# -- booking ---------------------------------------------------------------------------

def book_shipment(order, user=None, *, note='', client=None):
    """Create a Steadfast consignment for ``order`` and move the order to shipped."""
    client = client or SteadfastClient()

    with transaction.atomic():
        # The row lock stops two staff members booking the same order at once.
        order = Order.objects.select_for_update().get(pk=order.pk)
        existing = Shipment.objects.filter(order=order).first()
        if existing and existing.consignment_id:
            raise ShipmentError('already_booked', 'This order is already booked with Steadfast.', 409)
        if order.order_type != 'online':
            raise ShipmentError('not_bookable', 'In-shop orders are not sent by courier.')
        if order.order_status not in BOOKABLE_ORDER_STATUSES:
            raise ShipmentError(
                'not_bookable',
                f'A {order.get_order_status_display().lower()} order cannot be sent to Steadfast.',
            )

        recipient_phone = normalize_phone(order.shipping_phone)
        recipient_name = (order.shipping_name or '').strip()[:100]
        recipient_address = recipient_address_for(order)
        if not recipient_name or not recipient_address:
            raise ShipmentError('incomplete_address', 'The order needs a recipient name and address.')
        cod_amount = cod_amount_for(order)
        note = (note or '').strip()[:500]

        try:
            consignment = client.create_order(
                invoice=order.order_number,
                recipient_name=recipient_name,
                recipient_phone=recipient_phone,
                recipient_address=recipient_address,
                cod_amount=cod_amount,
                note=note,
                recipient_email=order.customer_email or None,
                item_description=item_description_for(order) or None,
            )
        except SteadfastError as exc:
            logger.warning('Steadfast booking failed for %s: %s', order.order_number, exc.message)
            raise _courier_failure(exc) from exc

        logger.info('Steadfast consignment %s created for %s',
                    consignment.get('consignment_id'), order.order_number)
        message = consignment.pop('_message', '') or 'Parcel booked with Steadfast Courier.'
        now = timezone.now()
        tracking_code = str(consignment.get('tracking_code') or '')

        shipment = existing or Shipment(order=order)
        shipment.courier = Shipment.COURIER_STEADFAST
        shipment.invoice = order.order_number
        shipment.consignment_id = str(consignment.get('consignment_id'))
        shipment.tracking_code = tracking_code
        shipment.tracking_url = tracking_url_for(tracking_code)
        shipment.status = normalize_status(consignment.get('status') or 'in_review')
        shipment.status_message = ''
        shipment.recipient_name = recipient_name
        shipment.recipient_phone = recipient_phone
        shipment.recipient_address = recipient_address
        shipment.cod_amount = cod_amount
        shipment.note = note
        shipment.booked_at = now
        shipment.booked_by = user if user is not None and user.is_authenticated else None
        shipment.status_updated_at = now
        shipment.last_checked_at = now
        shipment.raw_response = consignment
        shipment.save()

        ShipmentEvent.objects.create(
            shipment=shipment,
            source='booking',
            status=shipment.status,
            message=message,
            payload=consignment,
            occurred_at=now,
        )

        if settings.STEADFAST_SYNC_ORDER_STATUS and order.order_status in {'pending', 'confirmed', 'processing'}:
            change_order_status(
                order,
                'shipped',
                note=f'Booked with Steadfast Courier. Tracking code {tracking_code}.',
                changed_by=shipment.booked_by,
            )

    return shipment


# -- tracking --------------------------------------------------------------------------

def apply_courier_status(shipment, raw_status, *, source, message='', payload=None,
                         idempotency_key=None, occurred_at=None, checked_at=None, delivery_charge=None):
    """Record a status report. Returns ``(shipment, changed)``.

    Reports with an ``idempotency_key`` that was already stored are ignored.
    """
    status = normalize_status(raw_status) if raw_status else ''
    occurred_at = occurred_at or timezone.now()

    with transaction.atomic():
        locked = Shipment.objects.select_for_update().select_related('order').get(pk=shipment.pk)
        if idempotency_key and ShipmentEvent.objects.filter(idempotency_key=idempotency_key).exists():
            return locked, False

        changed = bool(status) and status != locked.status
        if changed or message or source in {'webhook', 'manual'}:
            ShipmentEvent.objects.create(
                shipment=locked,
                source=source,
                status=status,
                message=message or '',
                idempotency_key=idempotency_key or None,
                payload=payload or {},
                occurred_at=occurred_at,
            )

        if changed:
            locked.status = status
            locked.status_updated_at = occurred_at
        if message:
            locked.status_message = message
        if checked_at:
            locked.last_checked_at = checked_at
        if delivery_charge is not None:
            locked.delivery_charge = delivery_charge
        locked.save()

        if changed:
            _sync_order_status(locked)

    return locked, changed


def _sync_order_status(shipment):
    if not settings.STEADFAST_SYNC_ORDER_STATUS:
        return
    order = shipment.order
    if shipment.status == 'delivered' and order.order_status not in {'delivered', 'cancelled', 'refunded'}:
        change_order_status(order, 'delivered', note='Delivered by Steadfast Courier.')


def refresh_shipment(shipment, *, force=False, client=None, source='poll'):
    """Ask Steadfast for the current status. Returns ``(shipment, changed)``.

    Without ``force`` a 60 second cooldown applies, matching Steadfast's own cache.
    """
    now = timezone.now()
    if not force:
        wait = seconds_until_refresh(shipment, now)
        if wait:
            raise ShipmentCooldown(wait)
    if not shipment.consignment_id and not shipment.tracking_code:
        raise ShipmentError('not_booked', 'This shipment has not been booked with Steadfast yet.')

    client = client or SteadfastClient()
    try:
        if shipment.consignment_id:
            raw_status = client.status_by_cid(shipment.consignment_id)
        else:
            raw_status = client.status_by_tracking_code(shipment.tracking_code)
    except SteadfastError as exc:
        # Failed checks count toward the cooldown so a struggling API is not hammered.
        Shipment.objects.filter(pk=shipment.pk).update(last_checked_at=now)
        shipment.last_checked_at = now
        raise _courier_failure(exc) from exc

    return apply_courier_status(
        shipment,
        raw_status,
        source=source,
        payload={'delivery_status': raw_status},
        occurred_at=now,
        checked_at=now,
    )
