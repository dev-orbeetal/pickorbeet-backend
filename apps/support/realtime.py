"""Publish a saved message, a read, or presence to the customer and to staff."""
import json
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from rest_framework.renderers import JSONRenderer

logger = logging.getLogger(__name__)

STAFF_GROUP = 'support_staff'
CUSTOMERS_GROUP = 'support_customers'


def customer_group(user_id):
    return f'support_user_{user_id}'


def _plain(data):
    return json.loads(JSONRenderer().render(data))


def _send(group, event):
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(group, event)
    except Exception:
        logger.warning('Support socket publish failed for %s', group, exc_info=True)


def publish_message(message):
    from .serializers import MessageSerializer

    payload = _plain(MessageSerializer(message).data)
    event = {'type': 'support.message', 'message': payload}
    _send(customer_group(message.conversation.customer_id), event)
    _send(STAFF_GROUP, event)


def publish_read(conversation, *, author, read_at):
    event = {
        'type': 'support.read',
        'conversation_id': str(conversation.id),
        'author': author,
        'read_at': read_at.isoformat(),
    }
    _send(customer_group(conversation.customer_id), event)
    _send(STAFF_GROUP, event)


def publish_presence(agent_online):
    event = {'type': 'support.presence', 'agent_online': bool(agent_online)}
    _send(CUSTOMERS_GROUP, event)
    _send(STAFF_GROUP, event)
