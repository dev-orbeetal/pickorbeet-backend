"""Open a thread, store a message, and tell the other side."""
from django.db import IntegrityError
from django.db.models import F
from django.utils import timezone

from apps.notifications.services import notify_support_reply
from apps.orders.emails import _expected_delivery
from apps.orders.models import Order
from core.mailer import display_order_number

from .models import Conversation, Message
from .profile import load_profile
from .realtime import publish_message, publish_read

MESSAGE_LIMIT = 300


def order_card(order):
    """The fields the chat card shows. Delivery uses the same date as the order emails."""
    item = None
    if order is not None:
        item = next(iter(order.items.all()), None)
    image = ''
    name = ''
    if item is not None:
        name = item.product_name
        product = item.product
        if product is not None and product.primary_image:
            image = product.primary_image
    return {
        'id': str(order.id),
        'order_number': order.order_number,
        'display_number': display_order_number(order),
        'product_name': name,
        'product_image': image,
        'status': order.order_status,
        'status_label': order.get_order_status_display(),
        'expected_delivery': _expected_delivery(order),
    }


def messages_for(conversation):
    recent = conversation.messages.order_by('-created_at').values_list('id', flat=True)[:MESSAGE_LIMIT]
    return (
        conversation.messages.filter(id__in=list(recent))
        .select_related('order', 'staff')
        .prefetch_related('order__items__product__images')
        .order_by('created_at')
    )


def _greeting(user):
    name = (user.first_name or '').strip() or 'there'
    return f'Hi {name}! Welcome to PickOrbeet Support. How can I help you today?'


def open_conversation(user):
    """The customer's thread. The first open stores one greeting and nothing else."""
    existing = Conversation.objects.filter(customer=user).first()
    if existing is not None:
        return existing
    try:
        conversation = Conversation.objects.create(customer=user)
    except IntegrityError:
        return Conversation.objects.get(customer=user)
    message = Message.objects.create(
        conversation=conversation,
        author=Message.AGENT,
        body=_greeting(user),
    )
    Conversation.objects.filter(pk=conversation.pk).update(last_message_at=message.created_at)
    conversation.last_message_at = message.created_at
    return conversation


def order_for_track(user, order_number=''):
    """Prefer the order the customer opened Help from, otherwise the latest one still active."""
    owned = Order.objects.filter(user=user).prefetch_related('items__product__images')
    requested = (order_number or '').strip().lstrip('#')
    if requested:
        match = owned.filter(order_number__iexact=requested).first()
        if match is not None:
            return match
    return owned.exclude(order_status='cancelled').order_by('-created_at').first()


def post_customer_message(user, *, body='', topic='', order_number='', image=None):
    conversation = open_conversation(user)
    order = order_for_track(user, order_number) if topic == Message.TRACK_ORDER else None
    message = Message.objects.create(
        conversation=conversation,
        author=Message.CUSTOMER,
        body=(body or '').strip(),
        topic=topic,
        order=order,
        image=image,
    )
    updates = {
        'staff_unread': F('staff_unread') + 1,
        'last_message_at': message.created_at,
        'updated_at': timezone.now(),
    }
    if topic:
        updates['topic'] = topic
    Conversation.objects.filter(pk=conversation.pk).update(**updates)
    conversation.refresh_from_db()
    publish_message(message)
    return conversation, message


def post_staff_reply(staff, conversation, body):
    message = Message.objects.create(
        conversation=conversation,
        author=Message.AGENT,
        staff=staff,
        body=body.strip(),
    )
    Conversation.objects.filter(pk=conversation.pk).update(
        customer_unread=F('customer_unread') + 1,
        last_message_at=message.created_at,
        updated_at=timezone.now(),
    )
    conversation.refresh_from_db()
    publish_message(message)
    profile = load_profile()
    preview = message.body or 'Sent you a message'
    notify_support_reply(
        conversation.customer,
        message_id=message.id,
        title=profile.display_name,
        body=preview[:180],
        conversation_id=conversation.id,
    )
    return message


def mark_read(conversation, *, by_staff):
    """The side that opened the thread has seen the other side's messages."""
    author = Message.CUSTOMER if by_staff else Message.AGENT
    now = timezone.now()
    updated = Message.objects.filter(
        conversation=conversation,
        author=author,
        read_at__isnull=True,
    ).update(read_at=now)
    unread_field = 'staff_unread' if by_staff else 'customer_unread'
    had_unread = getattr(conversation, unread_field)
    if not updated and not had_unread:
        return
    Conversation.objects.filter(pk=conversation.pk).update(**{unread_field: 0})
    setattr(conversation, unread_field, 0)
    if updated:
        publish_read(conversation, author=author, read_at=now)


def customer_name(user):
    name = f'{(user.first_name or "").strip()} {(user.last_name or "").strip()}'.strip()
    return name or user.email or 'Customer'
