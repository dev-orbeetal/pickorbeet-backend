"""Deliver saved inbox rows without blocking the request that created them."""
import logging

from celery import shared_task

from .delivery import publish_created, send_push
from .models import Notification

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5)
def deliver_notification(self, notification_id):
    try:
        notification = Notification.objects.select_related('recipient').get(pk=notification_id)
    except Notification.DoesNotExist:
        return

    try:
        publish_created(notification)
    except Exception as exc:
        logger.warning('Socket publish failed for %s', notification_id, exc_info=True)
        raise self.retry(exc=exc, countdown=min(60, 2 ** self.request.retries))

    if notification.push_sent_at is not None:
        return
    try:
        send_push(notification)
    except Exception as exc:
        logger.warning('FCM send failed for %s', notification_id, exc_info=True)
        raise self.retry(exc=exc, countdown=min(60, 2 ** self.request.retries))
