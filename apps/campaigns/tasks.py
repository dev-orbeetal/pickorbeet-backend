"""Scheduled product-notification work. Celery beat runs these; see CELERY_BEAT_SCHEDULE."""
import logging

from celery import shared_task

from .services import send_due
from .watcher import watch_catalog

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def send_due_campaigns():
    return send_due()


@shared_task(ignore_result=True)
def watch_catalog_task():
    return watch_catalog()
