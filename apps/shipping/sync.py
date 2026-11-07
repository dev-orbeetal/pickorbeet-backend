"""The scheduled Steadfast status check: every active parcel, about every two minutes.

Webhooks stay the fast path. This catches anything a webhook missed.
"""
import logging
import time
from contextlib import contextmanager
from datetime import timedelta

from django.conf import settings
from django.db.models import F, Q
from django.utils import timezone

from .models import Shipment, ShipmentEvent, ShipmentSyncRun
from .services import FINAL_STATUSES, ShipmentError, refresh_shipment
from .steadfast import SteadfastClient

logger = logging.getLogger(__name__)

AUTH_ERRORS = {'courier_not_configured', 'courier_auth_failed'}
AUTH_BACKOFF = timedelta(minutes=15)
STALE_AFTER = timedelta(minutes=10)
KEEP_RUNS_FOR = timedelta(days=7)
LOCK_NAME = 'pickorbeet:steadfast-sync'
LOCK_TIMEOUT = 10 * 60


def _redis_client():
    import redis

    return redis.Redis.from_url(settings.REDIS_URL, socket_timeout=5, socket_connect_timeout=5)


@contextmanager
def sync_lock():
    """Yields False when another run holds the lock. Runs unlocked if Redis cannot be reached."""
    from redis.exceptions import LockError, RedisError

    lock = None
    try:
        lock = _redis_client().lock(LOCK_NAME, timeout=LOCK_TIMEOUT, blocking=False)
        acquired = lock.acquire()
    except RedisError:
        logger.warning('Steadfast sync lock unavailable; running without it', exc_info=True)
        lock, acquired = None, True
    if not acquired:
        yield False
        return
    try:
        yield True
    finally:
        if lock is not None:
            try:
                lock.release()
            except (LockError, RedisError):
                logger.info('Steadfast sync lock had already expired')


def shipments_due(*, min_age=None, limit=200, now=None):
    """Active parcels not checked within ``min_age`` seconds, the longest-unchecked first."""
    now = now or timezone.now()
    min_age = settings.STEADFAST_SYNC_MIN_AGE_SECONDS if min_age is None else min_age
    cutoff = now - timedelta(seconds=min_age)
    return (
        Shipment.objects.exclude(status__in=FINAL_STATUSES)
        .exclude(consignment_id='', tracking_code='')
        .filter(Q(last_checked_at__isnull=True) | Q(last_checked_at__lt=cutoff))
        .select_related('order')
        .order_by(F('last_checked_at').asc(nulls_first=True))[:limit]
    )


def paused_until(now=None):
    """After Steadfast rejects the API keys, checks pause for 15 minutes instead of failing every run."""
    now = now or timezone.now()
    last = ShipmentSyncRun.objects.only('started_at', 'error_code').first()
    if last is None or last.error_code not in AUTH_ERRORS:
        return None
    until = last.started_at + AUTH_BACKOFF
    return until if until > now else None


def sync_active_shipments(*, client=None, limit=200, min_age=None, pause=0.25, trigger='schedule', force=False):
    """Check due parcels with Steadfast. Returns a summary; ``skipped`` explains a run that did nothing."""
    now = timezone.now()
    until = paused_until(now)
    if until and not force:
        return {'skipped': 'paused', 'until': until.isoformat()}
    client = client or SteadfastClient()
    if not client.is_configured:
        return {'skipped': 'not_configured'}

    with sync_lock() as acquired:
        if not acquired:
            return {'skipped': 'locked'}
        run = ShipmentSyncRun.objects.create(trigger=trigger, started_at=now)
        for shipment in shipments_due(min_age=min_age, limit=limit, now=now):
            try:
                _, changed = refresh_shipment(shipment, force=True, client=client, source='poll')
            except ShipmentError as exc:
                run.failed += 1
                run.error_code, run.error = exc.code, exc.message[:500]
                logger.warning('Steadfast check failed for %s: %s', shipment.invoice, exc.message)
                if exc.code in AUTH_ERRORS:
                    break
            else:
                run.checked += 1
                run.changed += int(changed)
            if pause:
                time.sleep(pause)
        run.finished_at = timezone.now()
        run.save()

    ShipmentSyncRun.objects.filter(started_at__lt=now - KEEP_RUNS_FOR).delete()
    return {
        'checked': run.checked,
        'changed': run.changed,
        'failed': run.failed,
        'error_code': run.error_code,
    }


def sync_health(now=None):
    """What the Shipments page shows about the automatic check."""
    now = now or timezone.now()
    last = ShipmentSyncRun.objects.filter(finished_at__isnull=False).first()
    last_webhook = (
        ShipmentEvent.objects.filter(source='webhook').order_by('-created_at')
        .values_list('created_at', flat=True).first()
    )
    configured = SteadfastClient().is_configured
    until = paused_until(now)
    active = Shipment.objects.exclude(status__in=FINAL_STATUSES).exclude(consignment_id='', tracking_code='')

    warning = ''
    if not configured:
        warning = 'Steadfast API keys are not configured, so parcels are not checked automatically.'
    elif until:
        warning = 'Steadfast rejected the API keys. Automatic checks are paused; check the keys.'
    elif active.exists() and (last is None or now - last.finished_at > STALE_AFTER):
        warning = 'No automatic check has finished in the last 10 minutes. Check the Celery beat service.'

    return {
        'interval_seconds': settings.STEADFAST_SYNC_INTERVAL_SECONDS,
        'last_run_at': last.finished_at if last else None,
        'last_run_checked': last.checked if last else 0,
        'last_run_changed': last.changed if last else 0,
        'last_run_failed': last.failed if last else 0,
        'last_run_error': last.error if last else '',
        'last_webhook_at': last_webhook,
        'paused_until': until,
        'warning': warning,
    }
