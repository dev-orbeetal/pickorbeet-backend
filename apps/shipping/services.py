"""
Booking and tracking Steadfast shipments.

Views, the Django admin, the webhook and ``manage.py sync_shipments`` all go
through these functions so the rules live in one place.
"""
import base64
import hashlib
import hmac
import logging
import re
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.orders.models import Order
from apps.orders.services import change_order_status

from .models import Shipment, ShipmentEvent, SteadfastPoliceStation
from .thanas import district_key, match_police_station, stations_for_district, text_key
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
    # Portal-only labels (not returned by create_order).
    'unassigned': 'unknown',
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


ADDRESS_LIMIT = 250


def _unique_parts(parts, taken=()):
    seen = {part.lower() for part in taken}
    kept = []
    for part in parts:
        text = (part or '').strip().strip(',').strip()
        if text and text.lower() not in seen:
            seen.add(text.lower())
            kept.append(text)
    return kept


def recipient_address_for(order, station=None):
    """Street, area, post office, thana, district, postcode.

    Steadfast reads the thana and district from this text, so only the street is
    shortened to fit the 250 characters.
    """
    district = (order.shipping_district or '').strip()
    thana = station.name if station else ''
    place = _unique_parts([order.shipping_city, order.shipping_post_office, thana], taken=[district] if district else [])
    place += _unique_parts([district, order.shipping_postal_code], taken=place)
    tail = ', '.join(place)
    street = ', '.join(_unique_parts([order.shipping_address_line1, order.shipping_address_line2], taken=place))
    if not street:
        return tail[:ADDRESS_LIMIT]
    if not tail:
        return street[:ADDRESS_LIMIT]
    room = ADDRESS_LIMIT - len(tail) - 2
    if room <= 0:
        return tail[:ADDRESS_LIMIT]
    street = street[:room].rstrip(' ,')
    return f'{street}, {tail}' if street else tail


def item_description_for(order):
    lines = [f'{item.product_name} x{item.quantity}' for item in order.items.all()]
    return ', '.join(lines)[:250]


PORTAL_CONSIGNMENT_URL = 'https://steadfast.com.bd/user/consignment/{id}'


def portal_url_for(shipment):
    """The parcel in the Steadfast merchant portal. Staff need to be signed in there."""
    return PORTAL_CONSIGNMENT_URL.format(id=shipment.consignment_id) if shipment.consignment_id else ''


def official_tracking_link(consignment):
    """The public tracking page Steadfast returns at booking. It cannot be built from the code."""
    link = str((consignment or {}).get('tracking_link') or '').strip()
    return link if link.startswith('https://') and len(link) <= 500 else ''


def parse_courier_time(value):
    """Steadfast sends local (Asia/Dhaka) times such as ``2025-03-02 12:45:30``."""
    if not value:
        return None
    text = str(value).strip().replace('T', ' ').rstrip('Z')
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M'):
        try:
            parsed = datetime.strptime(text[:26], fmt)
        except ValueError:
            continue
        return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
    return None


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


# -- thanas ----------------------------------------------------------------------------

def _pick(row, *keys):
    for key in keys:
        if row.get(key) not in (None, ''):
            return row[key]
    return None


def _positive_int(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(number, 0)


def refresh_police_stations(*, client=None):
    """Replace the cached thana list with Steadfast's. Returns ``{'districts', 'stations'}``."""
    client = client or SteadfastClient()
    try:
        districts = client.police_stations()
    except SteadfastError as exc:
        raise _courier_failure(exc) from exc

    now = timezone.now()
    rows = {}
    for district in districts:
        if not isinstance(district, dict):
            continue
        district_name = str(_pick(district, 'Name', 'name') or '').strip()
        district_id = _positive_int(_pick(district, 'Id', 'id'))
        for station in _pick(district, 'PoliceStations', 'police_stations', 'policeStations') or []:
            if not isinstance(station, dict):
                continue
            station_id = _positive_int(_pick(station, 'Id', 'id'))
            name = str(_pick(station, 'Name', 'name') or '').strip()
            if not station_id or not name or not district_name:
                continue
            rows[station_id] = SteadfastPoliceStation(
                id=station_id,
                name=name[:120],
                district_id=district_id or _positive_int(_pick(station, 'DistrictId', 'district_id')),
                district_name=district_name[:120],
                name_key=text_key(name)[:120],
                district_key=district_key(district_name)[:120],
                is_active=True,
                raw=station,
                refreshed_at=now,
            )
    if not rows:
        raise ShipmentError('courier_error', 'Steadfast returned no police stations.', 502)

    with transaction.atomic():
        SteadfastPoliceStation.objects.bulk_create(
            rows.values(),
            update_conflicts=True,
            unique_fields=['id'],
            update_fields=['name', 'district_id', 'district_name', 'name_key', 'district_key',
                           'is_active', 'raw', 'refreshed_at'],
        )
        SteadfastPoliceStation.objects.exclude(id__in=rows.keys()).update(is_active=False)
    return {'districts': len({row.district_key for row in rows.values()}), 'stations': len(rows)}


def ensure_police_stations(*, client=None):
    """Load the thana list once if it has never been fetched. Never raises."""
    if SteadfastPoliceStation.objects.exists():
        return
    client = client or SteadfastClient()
    if not client.is_configured:
        return
    try:
        refresh_police_stations(client=client)
    except ShipmentError as exc:
        logger.warning('Could not load Steadfast police stations: %s', exc.message)


def _station_payload(station):
    if station is None:
        return None
    return {'id': station.id, 'name': station.name, 'district_name': station.district_name}


def _chosen_station(order, police_station_id=None):
    if police_station_id:
        station = SteadfastPoliceStation.objects.filter(pk=police_station_id, is_active=True).first()
        if station is None:
            raise ShipmentError('unknown_police_station', 'Choose a thana from the list.')
        return station, 'chosen'
    return match_police_station(order)


def booking_preview(order, *, police_station_id=None):
    """What a booking would send: the address text, the thana and the cash to collect."""
    station, how = _chosen_station(order, police_station_id)
    try:
        phone, phone_error = normalize_phone(order.shipping_phone), ''
    except ShipmentError as exc:
        phone, phone_error = '', exc.message
    return {
        'recipient_name': (order.shipping_name or '').strip()[:100],
        'recipient_phone': phone,
        'phone_error': phone_error,
        'recipient_address': recipient_address_for(order, station),
        'address_limit': ADDRESS_LIMIT,
        'district': order.shipping_district,
        'police_station': _station_payload(station),
        'police_station_match': how,
        'police_stations': [
            {'id': item.id, 'name': item.name} for item in stations_for_district(order.shipping_district)
        ],
        'cod_amount': cod_amount_for(order),
    }


# -- booking ---------------------------------------------------------------------------

def book_shipment(order, user=None, *, note='', client=None, recipient_address='', police_station_id=None):
    """Create a Steadfast consignment for ``order`` and move the order to shipped.

    Staff may override the thana, or the whole address text, after checking the preview.
    """
    client = client or SteadfastClient()

    with transaction.atomic():
        # The row lock stops two staff members booking the same order at once.
        order = Order.objects.select_for_update().get(pk=order.pk)
        existing = Shipment.objects.filter(order=order).first()
        if existing and existing.consignment_id:
            raise ShipmentError('already_booked', 'This order is already booked with Steadfast.', 409)
        if order.order_type not in ('online', 'external'):
            raise ShipmentError('not_bookable', 'Only online and external orders can be sent by courier.')
        if order.order_status not in BOOKABLE_ORDER_STATUSES:
            raise ShipmentError(
                'not_bookable',
                f'A {order.get_order_status_display().lower()} order cannot be sent to Steadfast.',
            )

        recipient_phone = normalize_phone(order.shipping_phone)
        recipient_name = (order.shipping_name or '').strip()[:100]
        station, _ = _chosen_station(order, police_station_id)
        recipient_address = (
            ' '.join((recipient_address or '').split())[:ADDRESS_LIMIT]
            or recipient_address_for(order, station)
        )
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
        shipment.tracking_url = official_tracking_link(consignment)
        shipment.status = normalize_status(consignment.get('status') or 'in_review')
        shipment.status_message = ''
        shipment.recipient_name = recipient_name
        shipment.recipient_phone = recipient_phone
        shipment.recipient_address = recipient_address
        shipment.police_station = station
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


# -- import (portal-only parcels) ------------------------------------------------------

def _lookup_courier_status(client, *, consignment_id='', tracking_code=''):
    consignment_id = str(consignment_id or '').strip()
    tracking_code = str(tracking_code or '').strip()
    if not consignment_id and not tracking_code:
        raise ShipmentError(
            'missing_identifier',
            'Provide a Steadfast consignment ID or tracking code.',
        )
    try:
        if consignment_id:
            raw_status = client.status_by_cid(consignment_id)
        else:
            raw_status = client.status_by_tracking_code(tracking_code)
    except SteadfastError as exc:
        raise _courier_failure(exc) from exc
    status = normalize_status(raw_status)
    return {
        'consignment_id': consignment_id,
        'tracking_code': tracking_code,
        'status': status,
        'status_group': status_group(status),
        'raw_status': str(raw_status),
    }


def preview_import(*, consignment_id='', tracking_code='', client=None):
    """Look up a Steadfast parcel without writing a local shipment."""
    client = client or SteadfastClient()
    if not client.is_configured:
        raise ShipmentError(
            'courier_not_configured',
            'Steadfast API keys are not configured.',
            http_status=503,
        )
    return _lookup_courier_status(client, consignment_id=consignment_id, tracking_code=tracking_code)


def import_shipment(order, user=None, *, consignment_id='', tracking_code='', client=None):
    """Attach an existing Steadfast consignment to a PickOrbeet order."""
    client = client or SteadfastClient()
    if not client.is_configured:
        raise ShipmentError(
            'courier_not_configured',
            'Steadfast API keys are not configured.',
            http_status=503,
        )

    consignment_id = str(consignment_id or '').strip()
    tracking_code = str(tracking_code or '').strip()
    preview = _lookup_courier_status(client, consignment_id=consignment_id, tracking_code=tracking_code)

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        existing = Shipment.objects.filter(order=order).first()
        if existing and (existing.consignment_id or existing.tracking_code):
            raise ShipmentError('already_booked', 'This order already has a Steadfast shipment.', 409)
        if order.order_type not in ('online', 'external'):
            raise ShipmentError('not_bookable', 'Only online and external orders can be linked to a courier parcel.')
        if order.order_status not in BOOKABLE_ORDER_STATUSES:
            raise ShipmentError(
                'not_bookable',
                f'A {order.get_order_status_display().lower()} order cannot be linked to Steadfast.',
            )

        if consignment_id and Shipment.objects.filter(consignment_id=consignment_id).exists():
            raise ShipmentError(
                'already_imported',
                'This consignment is already linked to another PickOrbeet order.',
                409,
            )
        if tracking_code and Shipment.objects.filter(tracking_code__iexact=tracking_code).exists():
            raise ShipmentError(
                'already_imported',
                'This tracking code is already linked to another PickOrbeet order.',
                409,
            )

        recipient_phone = normalize_phone(order.shipping_phone)
        recipient_name = (order.shipping_name or '').strip()[:100]
        recipient_address = recipient_address_for(order)
        if not recipient_name or not recipient_address:
            raise ShipmentError('incomplete_address', 'The order needs a recipient name and address.')
        cod_amount = cod_amount_for(order)
        now = timezone.now()
        tracking = tracking_code or ''

        shipment = existing or Shipment(order=order)
        shipment.courier = Shipment.COURIER_STEADFAST
        shipment.invoice = order.order_number
        shipment.consignment_id = consignment_id
        shipment.tracking_code = tracking
        shipment.tracking_url = ''
        shipment.status = preview['status'] or 'unknown'
        shipment.status_message = 'Imported from Steadfast portal.'
        shipment.recipient_name = recipient_name
        shipment.recipient_phone = recipient_phone
        shipment.recipient_address = recipient_address
        shipment.cod_amount = cod_amount
        shipment.note = ''
        shipment.booked_at = now
        shipment.booked_by = user if user is not None and getattr(user, 'is_authenticated', False) else None
        shipment.status_updated_at = now
        shipment.last_checked_at = now
        shipment.raw_response = {
            'imported': True,
            'delivery_status': preview.get('raw_status'),
            'consignment_id': consignment_id,
            'tracking_code': tracking,
        }
        shipment.save()

        ShipmentEvent.objects.create(
            shipment=shipment,
            source='manual',
            status=shipment.status,
            message='Imported existing Steadfast consignment.',
            payload=shipment.raw_response,
            occurred_at=now,
        )

        if settings.STEADFAST_SYNC_ORDER_STATUS and order.order_status in {'pending', 'confirmed', 'processing'}:
            change_order_status(
                order,
                'shipped',
                note=(
                    f'Linked Steadfast consignment {consignment_id or tracking}.'
                ),
                changed_by=shipment.booked_by,
            )

    return shipment


# -- tracking --------------------------------------------------------------------------

def webhook_signature_state(body, signature, secret):
    """``valid``, ``missing`` or ``invalid`` for an ``X-Signature`` header.

    The signature is an HMAC-SHA256 of the raw body keyed with the webhook token, as hex or base64.
    """
    signature = (signature or '').strip()
    if not signature:
        return 'missing'
    if signature.lower().startswith('sha256='):
        signature = signature[7:]
    digest = hmac.new((secret or '').encode(), body or b'', hashlib.sha256)
    if hmac.compare_digest(signature.lower().encode(), digest.hexdigest().encode()):
        return 'valid'
    if hmac.compare_digest(signature.encode(), base64.b64encode(digest.digest())):
        return 'valid'
    return 'invalid'


def cod_mismatch(shipment):
    """True when Steadfast will collect a different amount from the one the order needs."""
    reported = shipment.courier_cod_amount
    return reported is not None and Decimal(reported) != Decimal(shipment.cod_amount or 0)


def apply_courier_status(shipment, raw_status, *, source, message='', payload=None,
                         idempotency_key=None, occurred_at=None, checked_at=None, delivery_charge=None,
                         courier_cod_amount=None):
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
        if courier_cod_amount is not None:
            if locked.courier_cod_amount != courier_cod_amount and courier_cod_amount != locked.cod_amount:
                logger.warning(
                    'Steadfast will collect %s for %s but the order needs %s',
                    courier_cod_amount, locked.invoice, locked.cod_amount,
                )
            locked.courier_cod_amount = courier_cod_amount
        locked.save()

        if changed:
            _sync_order_status(locked)

    return locked, changed


def _sync_order_status(shipment):
    """What a final courier status does to the order.

    ``delivered`` marks the order delivered, which marks it paid. ``*_approval_pending``
    changes nothing until Steadfast approves it. A partial delivery or a cancellation
    only alerts staff: what came back and what was collected needs a person to check.
    """
    from apps.notifications.services import notify_courier_alert

    order = shipment.order
    number = order.order_number
    if shipment.status == 'partial_delivered':
        collected = shipment.courier_cod_amount
        amount = f'collected ৳{collected:,.2f}' if collected is not None else 'did not report the amount collected'
        notify_courier_alert(
            shipment,
            title='Parcel partly delivered',
            body=f'Steadfast partly delivered order {number} and {amount}. Check the returned items and the payment.',
        )
    elif shipment.status == 'cancelled':
        notify_courier_alert(
            shipment,
            title='Parcel cancelled',
            body=f'Steadfast cancelled the parcel for order {number}. It will come back; decide what to do with the order.',
        )

    if not settings.STEADFAST_SYNC_ORDER_STATUS:
        return
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

    shipment, changed = apply_courier_status(
        shipment,
        raw_status,
        source=source,
        payload={'delivery_status': raw_status},
        occurred_at=now,
        checked_at=now,
    )
    if shipment.invoice and (changed or not is_final(shipment.status)):
        fetch_tracking_steps(shipment, client=client)
    return shipment, changed


def _step_message(step):
    for key in ('tracking_message', 'message', 'text', 'note', 'details'):
        value = step.get(key)
        if isinstance(value, str) and value.strip():
            return ' '.join(value.split())[:1000]
    return ''


def record_tracking_steps(shipment, steps):
    """Save Steadfast's step-by-step updates as events. Steps already saved are skipped.

    A step matches an earlier event, including a webhook, when its text and time are the same.
    Returns the number of new events.
    """
    rows = []
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        message = _step_message(step)
        if message:
            rows.append((parse_courier_time(_pick(step, 'updated_at', 'created_at', 'time', 'date')), message, step))
    rows.sort(key=lambda row: row[0] or datetime.min.replace(tzinfo=timezone.get_current_timezone()))

    created = 0
    for occurred_at, message, step in rows:
        raw_status = str(_pick(step, 'delivery_status', 'status') or '')
        status = normalize_status(raw_status) if raw_status else ''
        if status not in STATUS_GROUPS:
            status = ''
        if ShipmentEvent.objects.filter(shipment=shipment, message=message, occurred_at=occurred_at).exists():
            continue
        stamp = occurred_at.isoformat() if occurred_at else ''
        digest = hashlib.sha256(f'{shipment.pk}|{message}|{stamp}'.encode()).hexdigest()
        try:
            with transaction.atomic():
                ShipmentEvent.objects.create(
                    shipment=shipment,
                    source='poll',
                    status=status,
                    message=message,
                    idempotency_key=f'sf-step:{digest}',
                    payload=step,
                    occurred_at=occurred_at,
                )
        except IntegrityError:
            continue
        created += 1
    return created


def fetch_tracking_steps(shipment, *, client=None):
    """Best effort: a failed lookup leaves the status check that came before it intact."""
    client = client or SteadfastClient()
    try:
        steps = client.trackings_by_invoice(shipment.invoice)
    except SteadfastError as exc:
        logger.info('Steadfast steps for %s unavailable: %s', shipment.invoice, exc)
        return 0
    return record_tracking_steps(shipment, steps)


def statuses_for_group(group):
    """All raw statuses that map into a status group (e.g. ``delivered``)."""
    return [status for status, mapped in STATUS_GROUPS.items() if mapped == group]


def bulk_refresh_shipments(queryset, *, client=None, limit=50, pause=0.25):
    """Force-refresh up to ``limit`` shipments. Returns a summary dict."""
    import time

    client = client or SteadfastClient()
    if not client.is_configured:
        raise ShipmentError(
            'courier_not_configured',
            'Steadfast API keys are not configured.',
            http_status=503,
        )

    shipments = list(queryset[:limit])
    checked = changed = failed = 0
    errors = []
    for shipment in shipments:
        try:
            _, did_change = refresh_shipment(shipment, force=True, client=client, source='manual')
            checked += 1
            changed += int(did_change)
        except ShipmentError as exc:
            failed += 1
            errors.append({
                'id': str(shipment.pk),
                'order_number': getattr(getattr(shipment, 'order', None), 'order_number', ''),
                'code': exc.code,
                'error': exc.message,
            })
            if exc.code in {'courier_not_configured', 'courier_auth_failed'}:
                break
        if pause:
            time.sleep(pause)
    return {
        'requested': len(shipments),
        'checked': checked,
        'changed': changed,
        'failed': failed,
        'errors': errors[:20],
    }
