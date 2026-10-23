"""Order, shipment, delivery, sale, and cart mail."""
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from core.mailer import (
    build_tracker,
    display_order_number,
    format_taka,
    format_when,
    frontend,
    product_image,
    product_url,
    send_branded,
    track_url,
)

logger = logging.getLogger(__name__)


def _meta(color, quantity):
    parts = [str(color)] if color else []
    parts.append(f'Qty: {quantity}')
    return ' | '.join(parts)


def _line(name, color, quantity, price, compare, product):
    return {
        'name': name,
        'meta': _meta(color, quantity),
        'price': format_taka(price),
        'compare': format_taka(compare) if compare else '',
        'image': product_image(product),
        'url': product_url(product),
    }


def _order_lines(order):
    rows = []
    items = order.items.select_related('product')
    for item in items:
        compare = None
        if item.compare_price and item.unit_price and item.compare_price > item.unit_price:
            compare = item.compare_price * item.quantity
        rows.append(_line(
            item.product_name, item.color, item.quantity, item.total_price, compare, item.product,
        ))
    return rows


def _money(order):
    return {
        'subtotal': format_taka(order.subtotal),
        'delivery': format_taka(order.delivery_charge),
        'discount': format_taka(order.discount) if order.discount else '',
        'total': format_taka(order.total),
    }


def _history_time(order, status):
    row = order.status_history.filter(status=status).order_by('created_at').first()
    return row.created_at if row else None


def _shipment_dates(order):
    return [
        format_when(order.created_at),
        format_when(_history_time(order, 'processing') or order.confirmed_at),
        format_when(order.shipped_at or _history_time(order, 'shipped')),
        format_when(_history_time(order, 'out_for_delivery')),
        format_when(order.delivered_at or _history_time(order, 'delivered')),
    ]


def _expected_delivery(order):
    start = order.shipped_at or timezone.now()
    days = int(getattr(settings, 'DELIVERY_ETA_DAYS', 5))
    return format_when(start + timedelta(days=days))


def _recipient(order):
    if order.order_type != 'online':
        return ''
    return order.customer_email or ''


def send_order_confirmed_email(order):
    number = display_order_number(order)
    return send_branded(
        f'Order {number} is confirmed',
        'emails/order_confirmed.html',
        {
            'preheader': f'{number} has been placed.',
            'footer_mode': 'support',
            'support_line': 'If you have any questions, feel free to contact our support team.',
            'order_number': number,
            'meta_label': 'Order Date',
            'meta_value': format_when(order.created_at, with_time=True),
            'items': _order_lines(order),
            'details_url': frontend('orders'),
            **_money(order),
        },
        _recipient(order),
    )


def send_order_on_the_way_email(order):
    number = display_order_number(order)
    out = order.order_status == 'out_for_delivery'
    active = 3 if out else 2
    intro = (
        'Your order is out for delivery and will arrive soon.'
        if out else
        'Great news! Your order has been shipped and is on its way to you.'
    )
    subject = (
        f'Your order {number} is out for delivery'
        if out else
        f'Your order {number} is on the way'
    )
    return send_branded(
        subject,
        'emails/order_on_the_way.html',
        {
            'preheader': intro,
            'footer_mode': 'support',
            'support_line': 'If you have any questions about your order, contact us anytime.',
            'intro': intro,
            'order_number': number,
            'meta_label': 'Expected Delivery',
            'meta_value': _expected_delivery(order),
            'steps': build_tracker(active, _shipment_dates(order)),
            'items': _order_lines(order),
            'track_url': track_url(order),
        },
        _recipient(order),
    )


def send_order_delivered_email(order):
    number = display_order_number(order)
    lines = _order_lines(order)
    review = lines[0]['url'] if lines else frontend('orders')
    return send_branded(
        f'Order {number} was delivered',
        'emails/order_delivered.html',
        {
            'preheader': f'{number} was delivered. We hope you love it.',
            'footer_mode': 'thanks',
            'order_number': number,
            'meta_label': 'Delivered on',
            'meta_value': format_when(order.delivered_at or timezone.now(), with_time=True),
            'items': lines,
            'review_url': review,
            'buy_url': review,
            'explore_url': frontend('products'),
        },
        _recipient(order),
    )


def notify_order_placed_email(order):
    """Checkout hook. A mail failure must not undo the order."""
    try:
        if not _recipient(order):
            return False
        return send_order_confirmed_email(order)
    except Exception:
        logger.exception('Order confirmation email failed for %s', order.pk)
        return False


def notify_order_status_email(order):
    """Shipment hook. Confirmed and processing stay in the inbox only."""
    try:
        if not _recipient(order):
            return False
        if order.order_status in ('shipped', 'out_for_delivery'):
            return send_order_on_the_way_email(order)
        if order.order_status == 'delivered':
            return send_order_delivered_email(order)
        return False
    except Exception:
        logger.exception('Order status email failed for %s', order.pk)
        return False


def send_abandoned_cart_email(cart):
    """One reminder for a signed-in shopper. Nothing is scheduled automatically."""
    user = cart.user
    if user is None or not user.is_active or not user.email:
        return False
    items = list(cart.items.select_related('product', 'variant'))
    if not items:
        return False
    rows = []
    for item in items:
        product = item.product
        variant = item.variant
        color = ''
        if variant is not None and variant.color:
            color = variant.color
        elif product.color:
            color = product.color
        compare = None
        if product.compare_price and product.compare_price > item.unit_price:
            compare = product.compare_price * item.quantity
        rows.append(_line(product.name, color, item.quantity, item.total_price, compare, product))
    return send_branded(
        'Still thinking? Your cart is waiting',
        'emails/abandoned_cart.html',
        {
            'preheader': 'Your cart is waiting for you. Complete your purchase before the items are gone.',
            'footer_mode': 'contact',
            'items': rows,
        },
        user.email,
    )


def send_mega_sale_email(recipient, *, discount='60', subject=None):
    """Campaign mail. Callers choose the audience; this does not mail the whole list."""
    label = str(discount).strip().rstrip('%')
    return send_branded(
        subject or f'Up to {label}% off at PickOrbeet',
        'emails/mega_sale.html',
        {
            'preheader': f'Mega sale. Up to {label}% off electronics.',
            'footer_mode': 'social',
            'discount': label,
        },
        recipient,
    )
