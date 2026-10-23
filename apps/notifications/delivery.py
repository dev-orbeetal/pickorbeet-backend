"""Push a saved notification onto the live socket and, for customers, FCM."""
import logging
import os

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.utils import timezone

from .models import Device, Notification
from .serializers import NotificationSerializer

logger = logging.getLogger(__name__)

_firebase_app = None


def group_name(user_id):
    return f'notifications_{user_id}'


def unread_count(user_id):
    return Notification.objects.filter(recipient_id=user_id, read_at__isnull=True).count()


def payload(notification):
    return NotificationSerializer(notification).data


def publish_created(notification):
    """Tell open clients that a row was added. Failures are retried by the worker."""
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        group_name(notification.recipient_id),
        {
            'type': 'notification.created',
            'notification': payload(notification),
            'unread_count': unread_count(notification.recipient_id),
        },
    )


def publish_read(user_id):
    """Best-effort unread refresh after the inbox is marked read."""
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(
            group_name(user_id),
            {
                'type': 'notification.read',
                'unread_count': unread_count(user_id),
            },
        )
    except Exception:
        logger.warning('Could not publish notification.read for %s', user_id, exc_info=True)


def _firebase():
    """Return the Firebase app, or None when the server has no service account."""
    global _firebase_app
    path = getattr(settings, 'FIREBASE_CREDENTIALS', '') or ''
    if not path or not os.path.isfile(path):
        return None
    if _firebase_app is not None:
        return _firebase_app
    import firebase_admin
    from firebase_admin import credentials

    if firebase_admin._apps:
        _firebase_app = firebase_admin.get_app()
        return _firebase_app
    _firebase_app = firebase_admin.initialize_app(credentials.Certificate(path))
    return _firebase_app


def _token_is_dead(exc):
    if exc is None:
        return False
    code = str(getattr(exc, 'code', '') or '')
    if code in {'registration-token-not-registered', 'invalid-registration-token', 'unregistered'}:
        return True
    return exc.__class__.__name__ in {'UnregisteredError', 'SenderIdMismatchError'}


def send_push(notification):
    """Send FCM to the recipient's active phones.

    Returns True when a send was attempted (tokens may still be invalid).
    Returns False when push is not configured or this person has no phone,
    so the caller can leave ``push_sent_at`` empty.
    """
    if notification.recipient.role != 'customer':
        return False
    if _firebase() is None:
        logger.info('FCM skipped; FIREBASE_CREDENTIALS is not set')
        return False

    devices = list(
        Device.objects.filter(user=notification.recipient, is_active=True).exclude(token='')
    )
    if not devices:
        return False

    from firebase_admin import messaging

    tokens = [device.token for device in devices]
    data = {key: '' if value is None else str(value) for key, value in (notification.data or {}).items()}
    data['notification_id'] = str(notification.id)
    data['kind'] = notification.kind
    message = messaging.MulticastMessage(
        tokens=tokens,
        notification=messaging.Notification(title=notification.title, body=notification.body),
        data=data,
        android=messaging.AndroidConfig(priority='high'),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(aps=messaging.Aps(sound='default')),
        ),
    )
    response = messaging.send_each_for_multicast(message)
    dead = []
    for index, item in enumerate(response.responses):
        if item.success or not _token_is_dead(item.exception):
            continue
        dead.append(tokens[index])
    if dead:
        Device.objects.filter(token__in=dead).update(is_active=False, token='')
    notification.push_sent_at = timezone.now()
    notification.save(update_fields=['push_sent_at'])
    return True
