"""Scheduled Steadfast work. Celery beat runs these; see CELERY_BEAT_SCHEDULE."""
import logging

from celery import shared_task

from .services import ShipmentError, refresh_police_stations
from .steadfast import SteadfastClient
from .sync import sync_active_shipments

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def sync_active_shipments_task():
    return sync_active_shipments(trigger='schedule')


@shared_task
def refresh_police_stations_task():
    client = SteadfastClient()
    if not client.is_configured:
        return None
    try:
        return refresh_police_stations(client=client)
    except ShipmentError as exc:
        logger.warning('Steadfast police station refresh failed: %s', exc.message)
        return None
