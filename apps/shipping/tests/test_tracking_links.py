from datetime import timedelta
from importlib import import_module

from django.apps import apps
from django.utils import timezone

from apps.orders.tests.factories import ShopTestCase, make_order, make_user
from apps.shipping.models import Shipment, ShipmentEvent
from apps.shipping.serializers import AdminShipmentSerializer, ShipmentSerializer
from apps.shipping.services import (
    apply_courier_status,
    book_shipment,
    parse_courier_time,
    record_tracking_steps,
    refresh_shipment,
)
from apps.shipping.steadfast import SteadfastNotFoundError

from .fakes import FakeClient

backfill = import_module('apps.shipping.migrations.0003_tracking_links').use_official_tracking_links


class NoLinkClient(FakeClient):
    def create_order(self, **kwargs):
        consignment = super().create_order(**kwargs)
        consignment.pop('tracking_link')
        return consignment


class StepsUnavailableClient(FakeClient):
    def trackings_by_invoice(self, invoice):
        raise SteadfastNotFoundError('No trackings', status_code=404)


class TrackingLinkTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.staff = make_user(role='seller')

    def test_booking_saves_the_link_steadfast_returns(self):
        shipment = book_shipment(make_order(user=make_user()), self.staff, client=FakeClient())
        self.assertEqual(shipment.tracking_url, 'https://steadfast.com.bd/t/a1b2c3d4')

    def test_no_link_is_made_up_when_steadfast_sends_none(self):
        shipment = book_shipment(make_order(user=make_user()), self.staff, client=NoLinkClient())
        self.assertEqual(shipment.tracking_url, '')
        self.assertEqual(shipment.tracking_code, 'SF123456789BD')

    def test_backfill_keeps_official_links_and_clears_built_ones(self):
        official = book_shipment(make_order(user=make_user()), self.staff, client=FakeClient())
        Shipment.objects.filter(pk=official.pk).update(tracking_url='https://steadfast.com.bd/t/SF123456789BD')

        built = book_shipment(
            make_order(user=make_user()), self.staff,
            client=NoLinkClient(consignment_id=1424108, tracking_code='SF999'),
        )
        Shipment.objects.filter(pk=built.pk).update(tracking_url='https://steadfast.com.bd/t/SF999')

        other = book_shipment(
            make_order(user=make_user()), self.staff,
            client=NoLinkClient(consignment_id=1424109, tracking_code='SF777'),
        )
        Shipment.objects.filter(pk=other.pk).update(tracking_url='https://example.com/parcel/77')

        backfill(apps, None)

        official.refresh_from_db()
        built.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(official.tracking_url, 'https://steadfast.com.bd/t/a1b2c3d4')
        self.assertEqual(built.tracking_url, '')
        self.assertEqual(other.tracking_url, 'https://example.com/parcel/77')

    def test_staff_get_our_tracking_page_and_the_portal_link(self):
        order = make_order(user=make_user())
        shipment = book_shipment(order, self.staff, client=FakeClient())

        data = AdminShipmentSerializer(shipment).data

        self.assertEqual(data['portal_url'], 'https://steadfast.com.bd/user/consignment/1424107')
        self.assertTrue(data['track_page_url'].endswith(f'/track-order?order={order.order_number}'))
        self.assertNotIn('portal_url', ShipmentSerializer(shipment).data)

    def test_public_tracking_shows_no_steadfast_link_without_one(self):
        order = make_order(user=make_user())
        book_shipment(order, self.staff, client=NoLinkClient())
        response = self.client.post(
            '/api/v1/orders/track/', {'order_number': order.order_number, 'phone': order.shipping_phone},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['shipment']['tracking_url'], '')


class TrackingStepTests(ShopTestCase):
    STEPS = [
        {'status': 'pending', 'message': 'Parcel is out for delivery', 'updated_at': '2026-11-02 15:30:00'},
        {'status': 'pending', 'message': 'Picked up by rider', 'updated_at': '2026-11-02 10:00:00'},
        {'tracking_message': 'Reached the Noakhali hub', 'created_at': '2026-11-02 12:00:00'},
        {'status': 'pending', 'message': '  ', 'updated_at': '2026-11-02 13:00:00'},
        'not a step',
    ]

    def setUp(self):
        super().setUp()
        self.order = make_order(user=make_user())
        self.shipment = book_shipment(self.order, make_user(role='seller'), client=FakeClient())

    def step_events(self):
        return ShipmentEvent.objects.filter(shipment=self.shipment, idempotency_key__startswith='sf-step:')

    def test_steps_are_saved_once_in_time_order(self):
        self.assertEqual(record_tracking_steps(self.shipment, self.STEPS), 3)
        self.assertEqual(record_tracking_steps(self.shipment, self.STEPS), 0)

        messages = list(self.step_events().values_list('message', flat=True))
        self.assertEqual(messages, ['Parcel is out for delivery', 'Reached the Noakhali hub', 'Picked up by rider'])

    def test_a_step_already_sent_by_webhook_is_not_repeated(self):
        apply_courier_status(
            self.shipment, '', source='webhook', message='Picked up by rider',
            idempotency_key='webhook-1', occurred_at=parse_courier_time('2026-11-02 10:00:00'),
        )
        self.assertEqual(record_tracking_steps(self.shipment, self.STEPS[:2]), 1)
        self.assertEqual(
            ShipmentEvent.objects.filter(shipment=self.shipment, message='Picked up by rider').count(), 1)

    def test_status_check_saves_steps_for_active_parcels(self):
        Shipment.objects.filter(pk=self.shipment.pk).update(
            last_checked_at=timezone.now() - timedelta(minutes=5))
        self.shipment.refresh_from_db()
        client = FakeClient(status='pending', trackings=self.STEPS)

        refresh_shipment(self.shipment, client=client)

        self.assertEqual(client.tracking_lookups, [self.order.order_number])
        self.assertEqual(self.step_events().count(), 3)

    def test_finished_parcels_are_not_asked_for_steps_again(self):
        Shipment.objects.filter(pk=self.shipment.pk).update(status='delivered')
        self.shipment.refresh_from_db()
        client = FakeClient(status='delivered')

        refresh_shipment(self.shipment, force=True, client=client)

        self.assertEqual(client.tracking_lookups, [])

    def test_live_timeline_uses_text_and_utc(self):
        steps = [{
            'text': 'Consignment sent to CUMILLA WAREHOUSE. Dispatch ID: 18983817',
            'status': 1,
            'created_at': '2026-11-07T15:47:21.000000Z',
        }]
        self.assertEqual(record_tracking_steps(self.shipment, steps), 1)
        event = self.step_events().get()
        self.assertEqual(event.status, '')
        self.assertEqual(event.message, steps[0]['text'])
        self.assertEqual(timezone.localtime(event.occurred_at).strftime('%Y-%m-%d %H:%M'), '2026-11-07 21:47')

    def test_customer_timeline_keeps_steadfast_sentences(self):
        apply_courier_status(self.shipment, 'pending', source='manual', occurred_at=timezone.now())
        record_tracking_steps(self.shipment, [{
            'text': 'Status has been updated as pending',
            'created_at': '2026-11-07T13:25:34.000000Z',
        }])
        customer = [row['message'] for row in ShipmentSerializer(self.shipment).data['events']]
        staff = [row['message'] for row in AdminShipmentSerializer(self.shipment).data['events']]
        self.assertIn('Status has been updated as pending', customer)
        self.assertTrue(all(customer))
        self.assertIn('', staff)

    def test_missing_steps_do_not_break_the_status_check(self):
        shipment, changed = refresh_shipment(
            self.shipment, force=True, client=StepsUnavailableClient(status='hold'))
        self.assertTrue(changed)
        self.assertEqual(shipment.status, 'hold')
        self.assertEqual(self.step_events().count(), 0)
