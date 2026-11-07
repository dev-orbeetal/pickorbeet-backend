from datetime import timedelta
from io import StringIO
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from redis.exceptions import ConnectionError as RedisConnectionError
from rest_framework.test import APIClient

from apps.notifications.models import Notification
from apps.orders.tests.factories import ShopTestCase, make_order, make_user
from apps.shipping.models import Shipment, ShipmentEvent, ShipmentSyncRun
from apps.shipping.services import apply_courier_status, book_shipment
from apps.shipping.steadfast import SteadfastAuthError
from apps.shipping.sync import paused_until, shipments_due, sync_active_shipments, sync_health

from .fakes import FakeClient


class FakeLock:
    def __init__(self, free=True):
        self.free = free
        self.released = False

    def acquire(self):
        return self.free

    def release(self):
        self.released = True


class FakeRedis:
    def __init__(self, lock):
        self._lock = lock

    def lock(self, name, timeout, blocking):
        return self._lock


class DownRedis:
    def lock(self, name, timeout, blocking):
        return self

    def acquire(self):
        raise RedisConnectionError('Connection refused')


class SyncTestCase(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.staff = make_user(role='seller')
        self.lock = FakeLock()
        patcher = mock.patch('apps.shipping.sync._redis_client', return_value=FakeRedis(self.lock))
        patcher.start()
        self.addCleanup(patcher.stop)

    def parcel(self, number, *, status='in_review', checked_ago=None):
        order = make_order(user=make_user())
        shipment = book_shipment(
            order, self.staff, client=FakeClient(consignment_id=5000 + number, tracking_code=f'SF{number}'))
        checked = None if checked_ago is None else timezone.now() - timedelta(seconds=checked_ago)
        Shipment.objects.filter(pk=shipment.pk).update(status=status, last_checked_at=checked)
        shipment.refresh_from_db()
        return shipment


class DueShipmentTests(SyncTestCase):
    def test_active_parcels_not_checked_recently_oldest_first(self):
        never = self.parcel(1)
        old = self.parcel(2, checked_ago=600)
        older = self.parcel(3, checked_ago=3600)
        self.parcel(4, checked_ago=30)
        self.parcel(5, status='delivered', checked_ago=3600)
        unbooked = self.parcel(6, checked_ago=3600)
        Shipment.objects.filter(pk=unbooked.pk).update(consignment_id='', tracking_code='')

        self.assertEqual(list(shipments_due()), [never, older, old])
        self.assertEqual(list(shipments_due(limit=2)), [never, older])


class SyncRunTests(SyncTestCase):
    def test_a_run_checks_due_parcels_and_records_itself(self):
        first = self.parcel(1, checked_ago=600)
        self.parcel(2, checked_ago=600)
        client = FakeClient(status='pending', trackings=[])

        result = sync_active_shipments(client=client, pause=0)

        self.assertEqual(result, {'checked': 2, 'changed': 2, 'failed': 0, 'error_code': ''})
        first.refresh_from_db()
        self.assertEqual(first.status, 'pending')
        run = ShipmentSyncRun.objects.get()
        self.assertEqual((run.trigger, run.checked, run.changed), ('schedule', 2, 2))
        self.assertIsNotNone(run.finished_at)
        self.assertTrue(self.lock.released)

    def test_a_run_already_in_progress_is_not_doubled(self):
        self.parcel(1, checked_ago=600)
        self.lock.free = False
        client = FakeClient(status='pending')

        self.assertEqual(sync_active_shipments(client=client, pause=0), {'skipped': 'locked'})
        self.assertEqual(client.status_checks, [])
        self.assertFalse(ShipmentSyncRun.objects.exists())

    def test_runs_without_the_lock_when_redis_is_down(self):
        self.parcel(1, checked_ago=600)
        with mock.patch('apps.shipping.sync._redis_client', return_value=DownRedis()):
            result = sync_active_shipments(client=FakeClient(status='pending', trackings=[]), pause=0)
        self.assertEqual(result['checked'], 1)

    def test_rejected_api_keys_pause_checks_for_fifteen_minutes(self):
        self.parcel(1, checked_ago=600)
        self.parcel(2, checked_ago=600)
        bad = FakeClient(error=SteadfastAuthError('Unauthorized'))

        result = sync_active_shipments(client=bad, pause=0)
        self.assertEqual((result['failed'], result['error_code']), (1, 'courier_auth_failed'))
        self.assertEqual(len(bad.status_checks), 1)
        self.assertIsNotNone(paused_until())

        good = FakeClient(status='pending', trackings=[])
        self.assertEqual(sync_active_shipments(client=good, pause=0)['skipped'], 'paused')
        self.assertEqual(good.status_checks, [])

        later = timezone.now() - timedelta(minutes=16)
        ShipmentSyncRun.objects.update(started_at=later)
        Shipment.objects.update(last_checked_at=later)
        self.assertEqual(sync_active_shipments(client=good, pause=0)['checked'], 2)

    def test_force_runs_while_paused(self):
        self.parcel(1, checked_ago=600)
        ShipmentSyncRun.objects.create(started_at=timezone.now(), error_code='courier_auth_failed')
        result = sync_active_shipments(client=FakeClient(status='pending', trackings=[]), pause=0, force=True)
        self.assertEqual(result['checked'], 1)

    def test_nothing_runs_without_api_keys(self):
        client = FakeClient()
        client.is_configured = False
        self.assertEqual(sync_active_shipments(client=client), {'skipped': 'not_configured'})

    def test_runs_older_than_a_week_are_removed(self):
        ShipmentSyncRun.objects.create(started_at=timezone.now() - timedelta(days=8), finished_at=timezone.now())
        sync_active_shipments(client=FakeClient(), pause=0)
        self.assertEqual(ShipmentSyncRun.objects.count(), 1)

    def test_beat_runs_the_check_every_two_minutes(self):
        entry = settings.CELERY_BEAT_SCHEDULE['steadfast-sync']
        self.assertEqual(entry['task'], 'apps.shipping.tasks.sync_active_shipments_task')
        self.assertEqual(entry['schedule'], 120)

    def test_the_command_uses_the_same_check(self):
        self.parcel(1, checked_ago=600)
        out = StringIO()
        with mock.patch('apps.shipping.sync.SteadfastClient', return_value=FakeClient(status='hold', trackings=[])):
            call_command('sync_shipments', '--pause', '0', stdout=out)
        self.assertIn('Checked 1 shipment(s): 1 changed, 0 failed.', out.getvalue())
        self.assertEqual(ShipmentSyncRun.objects.get().trigger, 'command')


@override_settings(STEADFAST_API_KEY='key', STEADFAST_SECRET_KEY='secret')
class SyncHealthTests(SyncTestCase):
    def test_warns_when_no_check_finished_for_ten_minutes(self):
        self.parcel(1)
        self.assertIn('Celery beat', sync_health()['warning'])

        ShipmentSyncRun.objects.create(started_at=timezone.now(), finished_at=timezone.now(), checked=1)
        health = sync_health()
        self.assertEqual(health['warning'], '')
        self.assertEqual(health['last_run_checked'], 1)

    def test_no_warning_while_nothing_is_on_the_way(self):
        self.assertEqual(sync_health()['warning'], '')

    def test_reports_the_last_webhook_and_a_pause(self):
        shipment = self.parcel(1)
        apply_courier_status(shipment, 'hold', source='webhook', idempotency_key='hook-1')
        ShipmentSyncRun.objects.create(
            started_at=timezone.now(), finished_at=timezone.now(), error_code='courier_auth_failed')

        health = sync_health()
        self.assertIsNotNone(health['last_webhook_at'])
        self.assertIsNotNone(health['paused_until'])
        self.assertIn('rejected the API keys', health['warning'])

    def test_shipment_summary_includes_sync_health(self):
        api = APIClient()
        api.force_authenticate(self.staff)
        response = api.get('/api/v1/shipping/admin/shipments/summary/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['sync']['interval_seconds'], 120)


@override_settings(STEADFAST_SYNC_ORDER_STATUS=True)
class CourierStatusRuleTests(SyncTestCase):
    def setUp(self):
        super().setUp()
        self.shipment = self.parcel(1)
        self.order = self.shipment.order
        self.accountant = make_user(role='accountant')

    def alerts(self):
        return Notification.objects.filter(kind__startswith='shipment.')

    def test_delivered_marks_the_order_paid(self):
        apply_courier_status(self.shipment, 'delivered', source='poll')
        self.order.refresh_from_db()
        self.assertEqual((self.order.order_status, self.order.payment_status), ('delivered', 'paid'))
        self.assertFalse(self.alerts().exists())

    def test_approval_pending_changes_nothing(self):
        for status in ('delivered_approval_pending', 'partial_delivered_approval_pending',
                       'cancelled_approval_pending'):
            apply_courier_status(self.shipment, status, source='poll')
        self.order.refresh_from_db()
        self.assertEqual((self.order.order_status, self.order.payment_status), ('shipped', 'pending'))
        self.assertFalse(self.alerts().exists())

    def test_partial_delivery_alerts_staff_with_the_amount(self):
        apply_courier_status(self.shipment, 'partial_delivered', source='webhook', courier_cod_amount=800)
        apply_courier_status(self.shipment, 'partial_delivered', source='webhook')

        self.order.refresh_from_db()
        self.assertEqual((self.order.order_status, self.order.payment_status), ('shipped', 'pending'))
        alerts = self.alerts()
        self.assertEqual({alert.recipient_id for alert in alerts}, {self.staff.pk, self.accountant.pk})
        self.assertEqual(alerts.count(), 2)
        self.assertIn('collected ৳800.00', alerts.first().body)

    def test_cancelled_alerts_staff_and_leaves_the_order(self):
        apply_courier_status(self.shipment, 'cancelled', source='poll')
        self.order.refresh_from_db()
        self.assertEqual(self.order.order_status, 'shipped')
        self.assertEqual(self.alerts().filter(kind='shipment.cancelled').count(), 2)
        self.assertTrue(ShipmentEvent.objects.filter(shipment=self.shipment, status='cancelled').exists())
