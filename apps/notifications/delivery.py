"""Push a saved notification onto the live socket and, for customers, FCM."""
import logging
import os
from collections import defaultdict

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db.models import Count
from django.utils import timezone

from .models import Device, Notification
from .serializers import NotificationSerializer

logger = logging.getLogger(__name__)

_firebase_app = None

# These names must match the channels and the drawable the app ships.
SMALL_ICON = 'ic_stat_notify'
ACCENT_COLOR = '#0040EE'


class PushNotDelivered(Exception):
    """Every phone refused the push for a reason that may pass, so the task should retry."""


OFFER_KINDS = ('product.', 'promo.')


def tray_style(notification):
    """Android channel and tray tag. Updates about one order replace each other in the tray."""
    data = notification.data or {}
    if notification.kind.startswith('support.'):
        return 'support', 'support'
    if notification.kind.startswith(OFFER_KINDS):
        campaign_id = data.get('campaign_id')
        return 'offers', f'campaign-{campaign_id}' if campaign_id else f'note-{notification.id}'
    order_id = data.get('order_id')
    if order_id:
        return 'orders', f'order-{order_id}'
    return 'orders', f'note-{notification.id}'


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


def _failure_reason(exc):
    if exc is None:
        return 'unknown'
    return str(getattr(exc, 'code', '') or '') or exc.__class__.__name__


FCM_BATCH = 500


def _message_parts(notification, *, badge):
    """Everything in a push except who it goes to. Single sends and campaign batches share it."""
    from firebase_admin import messaging

    channel, tag = tray_style(notification)
    data = {key: '' if value is None else str(value) for key, value in (notification.data or {}).items()}
    data['notification_id'] = str(notification.id)
    data['kind'] = notification.kind
    data['title'] = notification.title or ''
    data['body'] = notification.body or ''
    data['channel'] = channel
    data['tag'] = tag
    image = data.get('image') or None
    return {
        'notification': messaging.Notification(title=notification.title, body=notification.body, image=image),
        'data': data,
        'android': messaging.AndroidConfig(
            priority='high',
            collapse_key=tag,
            notification=messaging.AndroidNotification(
                channel_id=channel,
                icon=SMALL_ICON,
                color=ACCENT_COLOR,
                tag=tag,
                image=image,
                event_timestamp=notification.created_at,
                priority='high',
                default_sound=True,
                default_vibrate_timings=True,
            ),
        ),
        'apns': messaging.APNSConfig(
            headers={'apns-collapse-id': tag[:64]},
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    sound='default',
                    thread_id=channel,
                    badge=badge,
                    mutable_content=True if image else None,
                ),
            ),
            fcm_options=messaging.APNSFCMOptions(image=image) if image else None,
        ),
    }


def _sort_results(tokens, responses):
    """Split FCM answers into accepted indexes, dead tokens and refusal reasons."""
    accepted, dead, refused = [], [], []
    for index, (token, item) in enumerate(zip(tokens, responses)):
        if item.success:
            accepted.append(index)
        elif _token_is_dead(item.exception):
            dead.append(token)
        else:
            refused.append(_failure_reason(item.exception))
    return accepted, dead, refused


def _retire(tokens, user_label):
    if not tokens:
        return
    Device.objects.filter(token__in=tokens).update(is_active=False, token='')
    logger.info('FCM retired %s expired token(s) for %s', len(tokens), user_label)


def send_push(notification):
    """Send FCM to the recipient's active phones.

    Returns True when at least one phone accepted it or every refusal was a dead token.
    Returns False when push is not configured or this person has no phone,
    so the caller can leave ``push_sent_at`` empty. Raises ``PushNotDelivered``
    when no phone accepted it for a reason that may pass.
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
    message = messaging.MulticastMessage(
        tokens=tokens,
        **_message_parts(notification, badge=unread_count(notification.recipient_id)),
    )
    response = messaging.send_each_for_multicast(message)
    _, dead, refused = _sort_results(tokens, response.responses)
    _retire(dead, f'user {notification.recipient_id}')
    if refused:
        logger.warning(
            'FCM refused notification %s on %s of %s phone(s): %s',
            notification.id, len(refused), len(tokens), ', '.join(sorted(set(refused))),
        )
        if response.success_count == 0:
            raise PushNotDelivered(f'No phone accepted notification {notification.id}')
    notification.push_sent_at = timezone.now()
    notification.save(update_fields=['push_sent_at'])
    return True


def send_push_batch(notifications):
    """FCM for many rows at once, up to 500 phones per request. Returns the ids at least one phone accepted.

    Rows for staff, people without a phone, or a server without Firebase are skipped.
    """
    rows = [row for row in notifications if row.recipient.role == 'customer']
    if not rows or _firebase() is None:
        return set()

    from firebase_admin import messaging

    recipient_ids = {row.recipient_id for row in rows}
    tokens_by_user = defaultdict(list)
    for user_id, token in (
        Device.objects.filter(user_id__in=recipient_ids, is_active=True)
        .exclude(token='')
        .values_list('user_id', 'token')
    ):
        tokens_by_user[user_id].append(token)
    badges = dict(
        Notification.objects.filter(recipient_id__in=recipient_ids, read_at__isnull=True)
        .values('recipient_id')
        .annotate(unread=Count('id'))
        .values_list('recipient_id', 'unread')
    )

    owners, tokens, messages = [], [], []
    for row in rows:
        parts = None
        for token in tokens_by_user.get(row.recipient_id, ()):
            parts = parts or _message_parts(row, badge=badges.get(row.recipient_id, 0))
            owners.append(row.id)
            tokens.append(token)
            messages.append(messaging.Message(token=token, **parts))

    delivered, dead, refused = set(), [], []
    for start in range(0, len(messages), FCM_BATCH):
        response = messaging.send_each(messages[start:start + FCM_BATCH])
        accepted, batch_dead, batch_refused = _sort_results(tokens[start:start + FCM_BATCH], response.responses)
        delivered.update(owners[start + index] for index in accepted)
        dead.extend(batch_dead)
        refused.extend(batch_refused)
    _retire(dead, f'{len(recipient_ids)} customers')
    if refused:
        logger.warning(
            'FCM refused %s of %s campaign pushes: %s',
            len(refused), len(messages), ', '.join(sorted(set(refused))),
        )
    if delivered:
        Notification.objects.filter(pk__in=delivered).update(push_sent_at=timezone.now())
    return delivered
