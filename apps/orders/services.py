"""
Order domain services shared by API views, the Django admin and the courier sync.
"""
import json
from decimal import Decimal

from django.core import serializers as django_serializers
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.products.costing import StockError, issue_units, restore_units
from apps.products.models import MAX_ORDER_QUANTITY, Product, ProductVariant
from apps.products.variants import variant_options

from .delivery import delivery_charge_for
from .models import Coupon, Order, OrderDeletionLog, OrderItem, OrderStatusHistory


class ExternalOrderUpdateError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


CUSTOMER_PLATFORMS = frozenset({'web', 'app'})


def resolve_customer_platform(request, body_platform=None):
    """
    Resolve web/app for storefront checkout.

    Body wins when present (including invalid values, which become unknown).
    Otherwise fall back to X-Client-Platform. Only web and app are accepted;
    admin must be set server-side for external orders.
    """
    if body_platform is not None:
        value = str(body_platform).strip().lower()
        if value in CUSTOMER_PLATFORMS:
            return value
        if value:
            return 'unknown'
    header = (
        request.headers.get('X-Client-Platform')
        or request.META.get('HTTP_X_CLIENT_PLATFORM')
        or ''
    ).strip().lower()
    if header in CUSTOMER_PLATFORMS:
        return header
    return 'unknown'


# Statuses where stock should be deducted
STOCK_DEDUCTED_STATUSES = {'confirmed', 'processing', 'shipped', 'out_for_delivery', 'delivered'}

from apps.accounts.bd_geo import DHAKA_AREAS, is_inside_dhaka  # noqa: F401 — re-exported for callers

DELIVERY_FIELDS = [
    'shipping_name', 'shipping_phone', 'shipping_address_line1', 'shipping_address_line2',
    'shipping_division', 'shipping_city', 'shipping_district', 'shipping_post_office',
    'shipping_postal_code',
]


class DeliveryUpdateError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


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
        division = changes.get('shipping_division', order.shipping_division)
        inside = is_inside_dhaka(city=city, district=district, division=division)
        if order.payment_status == 'paid' and inside != order.is_inside_dhaka:
            raise DeliveryUpdateError(
                'This order is already paid, so the delivery area cannot change. Please contact support.'
            )

        changed = [field for field in DELIVERY_FIELDS
                   if field in changes and (changes[field] or '') != (getattr(order, field) or '')]
        for field in changed:
            setattr(order, field, changes[field])

        order.is_inside_dhaka = inside
        order.delivery_charge = delivery_charge_for(inside)
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


# Dealers source beyond recorded stock, so that quantity needs its own ceiling.
MAX_DEALER_QUANTITY = MAX_ORDER_QUANTITY


def cart_line_error(product, variant, quantity):
    """Why a customer can't buy this quantity, or None. Never reveals the stock count."""
    if not product.is_active:
        return 'This product is not available'
    if variant is None and product.variants.filter(is_active=True).exists():
        return 'Choose an available option'
    if variant is not None and not variant.is_active:
        return 'This option is not available'
    # Warehouse stock caps quantity; dealer-available items can be sourced
    # even when recorded stock is short or zero.
    item = variant or product
    if item.stock_quantity >= quantity:
        return None
    if item.dealer_available:
        if quantity <= MAX_DEALER_QUANTITY:
            return None
        return f'You can order up to {MAX_DEALER_QUANTITY} of this item'
    if item.stock_quantity > 0:
        return 'Insufficient stock'
    return 'This option is not available' if variant else 'This product is not available'


def reduce_stock(order, user=None):
    """Reduce stock for all items in the order and snapshot their cost once.

    Dealer fulfillment: when ``stock_location`` is dealer and the product is
    marked ``dealer_available``, the order can proceed even if recorded dealer
    stock is zero (dealer sources outside warehouse books). In that case no
    quantity is deducted.
    """
    if order.stock_reduced:
        return
    if order.order_type == 'in_shop':
        prefix = 'In-shop order'
    elif order.order_type == 'external':
        prefix = 'External order'
    else:
        prefix = 'Order'
    location = (order.stock_location or '').strip() or None
    for item in order.items.select_related('product', 'variant').all():
        if item.product_id is None:
            continue
        variant = find_variant(item)
        try:
            unit_cost, cost_total = issue_units(
                product=item.product,
                variant=variant,
                quantity=item.quantity,
                order=order,
                note=f'{prefix} #{order.order_number}',
                user=user,
                location=location,
            )
        except StockError:
            # Dealer-available items can proceed without warehouse deduction.
            dealer_ok = bool(
                (variant and variant.dealer_available)
                or item.product.dealer_available
            )
            if dealer_ok:
                unit_cost, cost_total = Decimal('0.00'), Decimal('0.00')
            else:
                raise
        item.unit_cost = unit_cost
        item.cost_total = cost_total
        item.cost_applied = True
        item.save(update_fields=['unit_cost', 'cost_total', 'cost_applied'])
    order.stock_reduced = True


def restore_stock(order, user=None, note=None):
    """Restore stock. Cost returns only when this order had removed it."""
    if not order.stock_reduced:
        return
    note = note or f'Order #{order.order_number} cancelled/refunded'
    for item in order.items.select_related('product', 'variant').all():
        if item.product_id is None:
            continue
        variant = find_variant(item)
        if item.cost_applied and item.cost_total is not None:
            cost_total = item.cost_total
        elif item.cost_applied and item.unit_cost is not None:
            cost_total = item.unit_cost * item.quantity
        else:
            cost_total = 0
        restore_units(
            product=item.product,
            variant=variant,
            quantity=item.quantity,
            cost_total=cost_total,
            order=order,
            note=note,
            user=user,
        )
        if item.cost_applied:
            item.cost_applied = False
            item.save(update_fields=['cost_applied'])
    order.stock_reduced = False


def _resolve_external_lines(items_data):
    """Validate product/variant lines and return (prepared_rows, subtotal)."""
    prepared = []
    subtotal = Decimal('0.00')
    for item_data in items_data:
        try:
            product = Product.objects.get(id=item_data['product_id'])
        except Product.DoesNotExist as exc:
            raise ExternalOrderUpdateError(
                f"Product {item_data['product_id']} was not found."
            ) from exc
        variant = None
        if item_data.get('variant_id'):
            try:
                variant = ProductVariant.objects.get(
                    id=item_data['variant_id'], product=product,
                )
            except ProductVariant.DoesNotExist as exc:
                raise ExternalOrderUpdateError(
                    'Variant does not belong to the selected product.'
                ) from exc
        elif product.variants.exists():
            raise ExternalOrderUpdateError(f'Select a variant for {product.name}.')
        quantity = int(item_data['quantity'])
        unit_price = Decimal(item_data['unit_price'])
        subtotal += unit_price * quantity
        prepared.append({
            'product': product,
            'variant': variant,
            'quantity': quantity,
            'unit_price': unit_price,
        })
    if not prepared:
        raise ExternalOrderUpdateError('Add at least one product.')
    return prepared, subtotal


def _replace_external_items(order, prepared_rows):
    order.items.all().delete()
    for item in prepared_rows:
        OrderItem.objects.create(
            order=order,
            product=item['product'],
            variant=item['variant'],
            product_name=item['product'].name,
            product_sku=(
                item['variant'].sku if item['variant'] and item['variant'].sku
                else item['product'].sku
            ),
            size=item['variant'].size if item['variant'] else item['product'].size,
            color=item['variant'].color if item['variant'] else item['product'].color,
            options=variant_options(item['variant']) if item['variant'] else [],
            quantity=item['quantity'],
            unit_price=item['unit_price'],
            compare_price=item['product'].compare_price,
        )


def update_external_order(order, data, user=None):
    """Edit an admin-created external order (customer, address, charges, lines)."""
    if order.order_type != 'external':
        raise ExternalOrderUpdateError('Only external / admin orders can be edited this way.')
    if order.order_status in ('cancelled', 'refunded'):
        raise ExternalOrderUpdateError(
            'Cancelled or refunded orders cannot be edited. Reopen the order first.'
        )

    with transaction.atomic():
        locked = Order.objects.select_for_update().get(pk=order.pk)
        if locked.order_type != 'external':
            raise ExternalOrderUpdateError('Only external / admin orders can be edited this way.')

        items_data = data.get('items', None)
        new_location = data.get('stock_location', None)
        location_changed = (
            new_location is not None
            and (new_location or '') != (locked.stock_location or '')
        )
        rewrite_items = items_data is not None
        needs_stock_refresh = False

        if rewrite_items or location_changed:
            shipment = getattr(locked, 'shipment', None)
            if shipment is not None and shipment.consignment_id and rewrite_items:
                raise ExternalOrderUpdateError(
                    'Items cannot change after the parcel is booked with Steadfast.'
                )
            if locked.stock_reduced:
                restore_stock(locked, user=user)
                locked.save(update_fields=['stock_reduced'])
            needs_stock_refresh = locked.order_status in STOCK_DEDUCTED_STATUSES

        if rewrite_items:
            prepared, subtotal = _resolve_external_lines(items_data)
            _replace_external_items(locked, prepared)
            locked.subtotal = subtotal

        if 'customer_name' in data and data['customer_name'] is not None:
            locked.guest_name = data['customer_name']
            locked.shipping_name = data['customer_name']
        if 'customer_phone' in data and data['customer_phone'] is not None:
            locked.guest_phone = data['customer_phone']
            locked.shipping_phone = data['customer_phone']
        if 'customer_email' in data:
            locked.guest_email = data.get('customer_email') or ''
        for field in (
            'shipping_address_line1', 'shipping_address_line2',
            'shipping_division', 'shipping_city', 'shipping_district',
            'shipping_post_office', 'shipping_postal_code',
        ):
            if field in data and data[field] is not None:
                setattr(locked, field, data[field] or '')
        if 'delivery_charge' in data and data['delivery_charge'] is not None:
            locked.delivery_charge = data['delivery_charge']
        if 'discount' in data and data['discount'] is not None:
            locked.discount = data['discount']
        if 'payment_method' in data:
            locked.payment_method = data.get('payment_method') or ''
        if 'payment_status' in data and data['payment_status']:
            locked.payment_status = data['payment_status']
        if 'notes' in data:
            locked.notes = data.get('notes') or ''
        if new_location is not None:
            locked.stock_location = new_location or ''

        locked.save()

        if needs_stock_refresh:
            try:
                reduce_stock(locked, user=user)
            except StockError as exc:
                raise ExternalOrderUpdateError(exc.message) from exc
            locked.save(update_fields=['stock_reduced'])

        OrderStatusHistory.objects.create(
            order=locked,
            status=locked.order_status,
            note='External order updated by admin',
            changed_by=user,
        )
        return locked


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
            reduce_stock(locked, user=changed_by)
        else:
            # pending, cancelled, refunded → restore stock if it was reduced
            restore_stock(locked, user=changed_by)

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
    from apps.orders.emails import queue_order_status_email
    queue_order_status_email(order)
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


class OrderPurgeError(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.message = message
        self.code = code


PURGE_REASON_MIN_LENGTH = 5


def _order_snapshot(order):
    """The order and every row deleted with it, as Django's JSON serializer writes them."""
    from apps.payments.models import Refund

    rows = [order, *order.items.all(), *order.status_history.all(), *order.coupon_usage.all()]
    rows += [*order.payments.all(), *Refund.objects.filter(payment__order=order)]
    shipment = getattr(order, 'shipment', None)
    if shipment is not None:
        rows += [shipment, *shipment.events.all()]
    return json.loads(django_serializers.serialize('json', rows))


def purge_order(order, *, confirm_number, reason, user):
    """Delete an order for good, keeping a copy in ``OrderDeletionLog``.

    Stock the order took goes back, coupon use counts drop, and its notifications
    go. A parcel still moving at Steadfast blocks this: cancel it there first.
    """
    from apps.notifications.models import Notification
    from apps.reports.models import DailySalesReport
    from apps.reports.services import generate_daily_sales_report
    from apps.shipping.services import is_final

    reason = (reason or '').strip()
    if (confirm_number or '').strip().upper() != order.order_number.upper():
        raise OrderPurgeError('Type the order number exactly to confirm.', 'confirmation_mismatch')
    if len(reason) < PURGE_REASON_MIN_LENGTH:
        raise OrderPurgeError('Say why this order is being deleted.', 'reason_required')

    with transaction.atomic():
        locked = Order.objects.select_for_update().get(pk=order.pk)
        shipment = getattr(locked, 'shipment', None)
        if shipment is not None and shipment.consignment_id and not is_final(shipment.status):
            raise OrderPurgeError(
                'Steadfast still has this parcel. Cancel it in the Steadfast portal and refresh '
                'its status before deleting the order.',
                'active_parcel',
            )
        snapshot = _order_snapshot(locked)
        stock_restored = locked.stock_reduced
        restore_stock(locked, user=user, note=f'Order #{locked.order_number} deleted permanently')
        for usage in locked.coupon_usage.all():
            Coupon.objects.filter(pk=usage.coupon_id, times_used__gt=0).update(times_used=F('times_used') - 1)
        log = OrderDeletionLog.objects.create(
            order_id=locked.pk,
            order_number=locked.order_number,
            order_type=locked.order_type,
            order_status=locked.order_status,
            payment_status=locked.payment_status,
            total=locked.total,
            reason=reason,
            stock_restored=stock_restored,
            snapshot=snapshot,
            deleted_by=user,
            deleted_by_name=(getattr(user, 'full_name', '') or '').strip() or getattr(user, 'email', ''),
        )
        Notification.objects.filter(data__order_id=str(locked.pk)).delete()
        report_date = timezone.localdate(locked.created_at)
        locked.delete()
        if DailySalesReport.objects.filter(date=report_date).exists():
            generate_daily_sales_report(report_date, user=user)
    return log
