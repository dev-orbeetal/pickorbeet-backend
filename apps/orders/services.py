"""
Order domain services shared by API views, the Django admin and the courier sync.
"""
import json

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from apps.reports.models import StockMovement

from .models import Order, OrderStatusHistory

# Statuses where stock should be deducted
STOCK_DEDUCTED_STATUSES = {'confirmed', 'processing', 'shipped', 'out_for_delivery', 'delivered'}

# Same areas Order.save() treats as inside Dhaka.
DHAKA_AREAS = {'dhaka', 'mirpur', 'uttara', 'gulshan', 'banani', 'dhanmondi', 'mohammadpur'}

DELIVERY_FIELDS = [
    'shipping_name', 'shipping_phone', 'shipping_address_line1', 'shipping_address_line2',
    'shipping_city', 'shipping_district', 'shipping_postal_code',
]


class DeliveryUpdateError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def is_inside_dhaka(city, district):
    return (city or '').strip().lower() in DHAKA_AREAS or (district or '').strip().lower() == 'dhaka'


def can_edit_delivery(order):
    """Customers may change the delivery details until the order is confirmed or booked."""
    if order.order_type != 'online' or order.order_status != 'pending':
        return False
    shipment = getattr(order, 'shipment', None)
    return shipment is None or not shipment.consignment_id


def update_delivery_details(order, changes, changed_by=None):
    """Change where a pending order goes and re-price delivery for the new zone."""
    with transaction.atomic():
        order = type(order).objects.select_for_update().get(pk=order.pk)
        if not can_edit_delivery(order):
            raise DeliveryUpdateError('Delivery details can no longer be changed for this order.')
        city = changes.get('shipping_city', order.shipping_city)
        district = changes.get('shipping_district', order.shipping_district)
        inside = is_inside_dhaka(city, district)
        if order.payment_status == 'paid' and inside != order.is_inside_dhaka:
            raise DeliveryUpdateError(
                'This order is already paid, so the delivery area cannot change. Please contact support.'
            )

        changed = [field for field in DELIVERY_FIELDS
                   if field in changes and (changes[field] or '') != (getattr(order, field) or '')]
        for field in changed:
            setattr(order, field, changes[field])

        order.is_inside_dhaka = inside
        order.delivery_charge = (
            settings.DELIVERY_CHARGE_INSIDE_DHAKA if inside else settings.DELIVERY_CHARGE_OUTSIDE_DHAKA
        )
        order.save()  # recalculates total from the new delivery charge

        if changed:
            OrderStatusHistory.objects.create(
                order=order,
                status=order.order_status,
                note='Delivery details updated by the customer.',
                changed_by=changed_by,
            )
    return order


def find_variant(item):
    """Find the variant to update stock for. Handles cases where variant FK
    is null but product has variants (e.g. SET_NULL after variant delete)."""
    if item.variant:
        return item.variant
    # If product has variants, try to match by size/color from the order item snapshot
    if item.product.variants.exists():
        variant = item.product.variants.filter(
            size=item.size, color=item.color, is_active=True
        ).first()
        if variant:
            return variant
        # Last resort: return first active variant
        return item.product.variants.filter(is_active=True).first()
    return None


def reduce_stock(order):
    """Reduce stock for all items in the order."""
    if order.stock_reduced:
        return
    for item in order.items.select_related('product', 'variant').all():
        variant = find_variant(item)
        if variant:
            prev = variant.stock_quantity
            variant.stock_quantity = max(0, variant.stock_quantity - item.quantity)
            variant.save(update_fields=['stock_quantity'])
            StockMovement.objects.create(
                product=item.product, variant=variant,
                movement_type='out', quantity=-item.quantity,
                previous_stock=prev, new_stock=variant.stock_quantity,
                reason='sale', reference_order=order,
                note=f'Order #{order.order_number}',
            )
        else:
            prev = item.product.stock_quantity
            item.product.stock_quantity = max(0, item.product.stock_quantity - item.quantity)
            item.product.save(update_fields=['stock_quantity'])
            StockMovement.objects.create(
                product=item.product, variant=None,
                movement_type='out', quantity=-item.quantity,
                previous_stock=prev, new_stock=item.product.stock_quantity,
                reason='sale', reference_order=order,
                note=f'Order #{order.order_number}',
            )
    order.stock_reduced = True


def restore_stock(order):
    """Restore stock for all items in the order."""
    if not order.stock_reduced:
        return
    for item in order.items.select_related('product', 'variant').all():
        variant = find_variant(item)
        if variant:
            prev = variant.stock_quantity
            variant.stock_quantity += item.quantity
            variant.save(update_fields=['stock_quantity'])
            StockMovement.objects.create(
                product=item.product, variant=variant,
                movement_type='return', quantity=item.quantity,
                previous_stock=prev, new_stock=variant.stock_quantity,
                reason='return', reference_order=order,
                note=f'Order #{order.order_number} cancelled/refunded',
            )
        else:
            prev = item.product.stock_quantity
            item.product.stock_quantity += item.quantity
            item.product.save(update_fields=['stock_quantity'])
            StockMovement.objects.create(
                product=item.product, variant=None,
                movement_type='return', quantity=item.quantity,
                previous_stock=prev, new_stock=item.product.stock_quantity,
                reason='return', reference_order=order,
                note=f'Order #{order.order_number} cancelled/refunded',
            )
    order.stock_reduced = False


def change_order_status(order, new_status, note='', changed_by=None):
    """Move an order to ``new_status`` with timestamps, stock and history.

    Used by the staff status endpoint and by the courier sync, so both behave the same.
    A no-op when the order is already in ``new_status`` — no second history row
    and no second notification.
    """
    from apps.notifications.services import notify_order_status, notify_payment_paid

    with transaction.atomic():
        locked = Order.objects.select_for_update().get(pk=order.pk)
        if locked.order_status == new_status:
            return order
        previous_payment = locked.payment_status
        locked.order_status = new_status

        # Update timestamps
        if new_status == 'confirmed':
            locked.confirmed_at = timezone.now()
        elif new_status == 'shipped':
            locked.shipped_at = timezone.now()
        elif new_status == 'delivered':
            locked.delivered_at = timezone.now()
            locked.payment_status = 'paid'
        elif new_status == 'refunded':
            locked.payment_status = 'refunded'

        # Stock management: reduce when entering confirmed+ statuses, restore when going back
        if new_status in STOCK_DEDUCTED_STATUSES:
            reduce_stock(locked)
        else:
            # pending, cancelled, refunded → restore stock if it was reduced
            restore_stock(locked)

        locked.save()

        history = OrderStatusHistory.objects.create(
            order=locked,
            status=new_status,
            note=note,
            changed_by=changed_by,
        )
    order.refresh_from_db()
    notify_order_status(order, history)
    if previous_payment != 'paid' and order.payment_status == 'paid':
        notify_payment_paid(order)
    from apps.orders.emails import notify_order_status_email
    notify_order_status_email(order)
    return order


def record_online_payment(payment, outcome, *, gateway_fields=None):
    """Apply an SSLCommerz result once.

    ``outcome`` is ``paid``, ``failed``, or ``cancelled``. A paid order that is
    still pending is confirmed through ``change_order_status``, so stock, history,
    and the customer notification happen on that one path. Calling this again
    for the same result does not create a second inbox row.
    """
    from apps.notifications.services import notify_payment_failed, notify_payment_paid
    from apps.payments.models import Payment

    with transaction.atomic():
        payment = Payment.objects.select_for_update().select_related('order').get(pk=payment.pk)
        if gateway_fields:
            fields = dict(gateway_fields)
            raw_gateway = fields.get('gateway_response')
            if raw_gateway is not None:
                fields['gateway_response'] = json.loads(json.dumps(raw_gateway, cls=DjangoJSONEncoder))
            for field, value in fields.items():
                setattr(payment, field, value)

        order = payment.order
        if outcome == 'paid':
            if payment.status != 'completed':
                payment.status = 'completed'
                payment.completed_at = timezone.now()
            payment.save()
            became_paid = order.payment_status != 'paid'
            if became_paid:
                order.payment_status = 'paid'
                order.transaction_id = payment.transaction_id or ''
                order.payment_method = 'sslcommerz'
                order.save()
            if order.order_status == 'pending':
                change_order_status(order, 'confirmed', note='Payment received.')
            if became_paid:
                notify_payment_paid(order, payment)
            return payment

        if outcome == 'failed':
            if payment.status == 'failed':
                payment.save()
                return payment
            if payment.status in {'completed', 'refunded'}:
                payment.save()
                return payment
            payment.status = 'failed'
            payment.save()
            notify_payment_failed(order, payment)
            return payment

        if outcome == 'cancelled':
            if payment.status not in {'cancelled', 'completed', 'refunded'}:
                payment.status = 'cancelled'
            payment.save()
            return payment

    raise ValueError(f'Unknown payment outcome {outcome}')
