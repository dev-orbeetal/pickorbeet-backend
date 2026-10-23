"""Create inbox rows for order, payment, and refund events.

Writers call these helpers. A repeated event for the same person is ignored
because ``(recipient, dedupe_key)`` is unique.
"""
import logging

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from .models import Notification

logger = logging.getLogger(__name__)
User = get_user_model()

STAFF_NEW_ORDER = ('seller', 'super_admin')
STAFF_PAYMENT = ('seller', 'accountant', 'super_admin')
STAFF_REFUND = ('accountant', 'super_admin')

STATUS_COPY = {
    'pending': ('Order placed', 'We received order {num}.'),
    'confirmed': ('Order confirmed', 'Order {num} is confirmed.'),
    'processing': ('Order is being prepared', 'We are preparing order {num}.'),
    'shipped': ('Order shipped', 'Order {num} is on the way.'),
    'out_for_delivery': ('Out for delivery', 'Order {num} is out for delivery.'),
    'delivered': ('Order delivered', 'Order {num} was delivered.'),
    'cancelled': ('Order cancelled', 'Order {num} was cancelled.'),
    'refunded': ('Order refunded', 'Order {num} was refunded.'),
}


def staff_users(roles, exclude_ids=None):
    queryset = User.objects.filter(role__in=roles, is_active=True)
    if exclude_ids:
        queryset = queryset.exclude(pk__in=list(exclude_ids))
    return list(queryset)


def _order_data(order, target):
    return {
        'order_id': str(order.id),
        'order_number': order.order_number,
        'target': target,
        'status': order.order_status,
    }


def _enqueue(notification_id):
    from .tasks import deliver_notification

    deliver_notification.delay(str(notification_id))


def _create(recipient, *, kind, title, body, data, dedupe_key):
    if recipient is None or not recipient.is_active:
        return None
    try:
        notification, created = Notification.objects.get_or_create(
            recipient=recipient,
            dedupe_key=dedupe_key,
            defaults={'kind': kind, 'title': title, 'body': body, 'data': data},
        )
    except IntegrityError:
        logger.info('Duplicate notification %s for %s', dedupe_key, recipient.pk)
        return None
    if created:
        transaction.on_commit(lambda notification_id=notification.id: _enqueue(notification_id))
    return notification if created else None


def notify_order_placed(order):
    """Online checkout. Guests alert staff only. In-shop orders are not sent here."""
    if order.order_type != 'online':
        return
    number = order.order_number
    dedupe_key = f'order:{order.id}:placed'
    if order.user_id and order.user.is_active:
        _create(
            order.user,
            kind='order.placed',
            title='Order placed',
            body=f'We received order {number}.',
            data=_order_data(order, 'order'),
            dedupe_key=dedupe_key,
        )
    for user in staff_users(STAFF_NEW_ORDER):
        _create(
            user,
            kind='order.placed',
            title=f'New order {number}',
            body=f'Order {number} was just placed.',
            data=_order_data(order, 'admin_order'),
            dedupe_key=dedupe_key,
        )


def notify_order_status(order, history):
    """One customer row for a real status change. Staff are not copied."""
    if not order.user_id:
        return
    title, template = STATUS_COPY.get(
        order.order_status,
        ('Order updated', 'Order {num} was updated.'),
    )
    _create(
        order.user,
        kind=f'order.{order.order_status}',
        title=title,
        body=template.format(num=order.order_number),
        data=_order_data(order, 'order'),
        dedupe_key=f'order:{order.id}:status:{history.id}',
    )


def notify_payment_paid(order, payment=None):
    dedupe_key = (
        f'payment:{payment.id}:paid' if payment is not None else f'order:{order.id}:payment:paid'
    )
    number = order.order_number
    if order.user_id:
        _create(
            order.user,
            kind='payment.paid',
            title='Payment received',
            body=f'Payment for order {number} was received.',
            data=_order_data(order, 'order'),
            dedupe_key=dedupe_key,
        )
    for user in staff_users(STAFF_PAYMENT):
        _create(
            user,
            kind='payment.paid',
            title='Payment received',
            body=f'Order {number} has been paid.',
            data=_order_data(order, 'admin_order'),
            dedupe_key=dedupe_key,
        )


def notify_payment_failed(order, payment):
    if not order.user_id:
        return
    _create(
        order.user,
        kind='payment.failed',
        title='Payment failed',
        body=f'Payment for order {order.order_number} did not go through.',
        data=_order_data(order, 'order'),
        dedupe_key=f'payment:{payment.id}:failed',
    )


def notify_refund_requested(refund):
    order = refund.payment.order
    exclude = [refund.requested_by_id] if refund.requested_by_id else []
    for user in staff_users(STAFF_REFUND, exclude_ids=exclude):
        _create(
            user,
            kind='refund.requested',
            title='Refund requested',
            body=f'A refund was requested for order {order.order_number}.',
            data=_order_data(order, 'admin_order'),
            dedupe_key=f'refund:{refund.id}:requested',
        )
