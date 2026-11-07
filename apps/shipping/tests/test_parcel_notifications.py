from datetime import timedelta

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.notifications.models import Notification
from apps.orders.tests.factories import ShopTestCase, make_order, make_user
from apps.shipping.models import Shipment, ShipmentEvent
from apps.shipping.services import book_shipment, refresh_shipment

from .fakes import FakeClient

WEBHOOK = '/api/v1/shipping/steadfast/webhook/'


def courier_time(**ago):
    return timezone.localtime(timezone.now() - timedelta(**ago)).strftime('%Y-%m-%d %H:%M:%S')


@override_settings(STEADFAST_WEBHOOK_TOKEN='hook-secret', STEADFAST_SYNC_ORDER_STATUS=True)
class ParcelNotificationTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_user()
        self.order = make_order(user=self.customer)
        self.shipment = book_shipment(self.order, make_user(role='seller'), client=FakeClient())
        # Booked two hours ago, so the steps below come after the booking.
        ShipmentEvent.objects.filter(shipment=self.shipment).update(
            occurred_at=timezone.now() - timedelta(hours=2))
        Shipment.objects.filter(pk=self.shipment.pk).update(
            last_checked_at=timezone.now() - timedelta(minutes=5))
        self.shipment.refresh_from_db()
        self.api = APIClient()

    def parcel_notes(self):
        return Notification.objects.filter(recipient=self.customer, kind='parcel.update').order_by('created_at')

    def webhook(self, key, **body):
        payload = {
            'notification_type': 'tracking_update',
            'consignment_id': 1424107,
            'invoice': self.order.order_number,
            **body,
        }
        return self.api.post(
            WEBHOOK, payload, format='json',
            HTTP_AUTHORIZATION='Bearer hook-secret', HTTP_IDEMPOTENCY_KEY=key,
        )

    def test_booking_sends_only_the_order_shipped_notice(self):
        self.assertTrue(Notification.objects.filter(recipient=self.customer, kind='order.shipped').exists())
        self.assertFalse(self.parcel_notes().exists())

    def test_every_webhook_step_reaches_the_customer_once(self):
        self.webhook('evt-1', tracking_message='Reached the Noakhali hub', updated_at=courier_time(minutes=40))
        self.webhook('evt-1', tracking_message='Reached the Noakhali hub', updated_at=courier_time(minutes=40))
        self.webhook('evt-2', tracking_message='Parcel is out for delivery', updated_at=courier_time(minutes=5))

        notes = list(self.parcel_notes())
        self.assertEqual([note.title for note in notes], ['Parcel update', 'Out for delivery'])
        self.assertEqual(notes[0].body, f'Reached the Noakhali hub\nOrder {self.order.order_number}')
        self.assertEqual(notes[1].data['order_id'], str(self.order.id))
        self.assertEqual(notes[1].data['target'], 'order')

    def test_a_step_from_the_webhook_and_a_poll_arrives_once(self):
        self.webhook('evt-1', tracking_message='Picked up by rider', updated_at=courier_time(minutes=30))
        client = FakeClient(status='in_review', trackings=[
            {'status': 'pending', 'message': 'Picked up by rider', 'updated_at': courier_time(minutes=29)},
        ])

        refresh_shipment(self.shipment, force=True, client=client)

        self.assertEqual(self.parcel_notes().count(), 1)

    def test_a_poll_sends_only_the_newest_new_step(self):
        client = FakeClient(status='pending', trackings=[
            {'status': 'pending', 'message': 'Picked up by rider', 'updated_at': courier_time(minutes=90)},
            {'status': 'pending', 'message': 'Parcel is out for delivery', 'updated_at': courier_time(minutes=3)},
            {'tracking_message': 'Reached the Noakhali hub', 'created_at': courier_time(minutes=45)},
        ])

        refresh_shipment(self.shipment, client=client)

        notes = list(self.parcel_notes())
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].title, 'Out for delivery')
        self.assertTrue(notes[0].body.startswith('Parcel is out for delivery'))

    def test_an_older_step_found_late_is_not_sent(self):
        self.webhook('evt-1', tracking_message='Parcel is out for delivery', updated_at=courier_time(minutes=5))
        client = FakeClient(status='in_review', trackings=[
            {'status': 'pending', 'message': 'Reached the Noakhali hub', 'updated_at': courier_time(minutes=60)},
        ])

        refresh_shipment(self.shipment, force=True, client=client)

        self.assertEqual([note.title for note in self.parcel_notes()], ['Out for delivery'])

    def test_old_steps_are_not_sent(self):
        client = FakeClient(status='pending', trackings=[
            {'status': 'pending', 'message': 'Picked up by rider', 'updated_at': courier_time(days=3)},
        ])
        ShipmentEvent.objects.filter(shipment=self.shipment).update(occurred_at=timezone.now() - timedelta(days=4))

        refresh_shipment(self.shipment, client=client)

        self.assertEqual(ShipmentEvent.objects.filter(shipment=self.shipment, message='Picked up by rider').count(), 1)
        self.assertFalse(self.parcel_notes().exists())

    def test_a_status_change_without_steps_uses_our_words(self):
        refresh_shipment(self.shipment, client=FakeClient(status='hold', trackings=[]))

        note = self.parcel_notes().get()
        self.assertEqual(note.title, 'Parcel on hold')
        self.assertIn('Steadfast will call you', note.body)
        self.assertEqual(note.data['parcel_status'], 'hold')

    def test_delivery_is_told_once_by_the_order_notice(self):
        self.api.post(
            WEBHOOK,
            {
                'notification_type': 'delivery_status',
                'consignment_id': 1424107,
                'invoice': self.order.order_number,
                'status': 'delivered',
                'cod_amount': 0,
                'tracking_message': 'Your package has been delivered successfully.',
                'updated_at': courier_time(minutes=1),
            },
            format='json',
            HTTP_AUTHORIZATION='Bearer hook-secret',
        )

        self.assertTrue(Notification.objects.filter(recipient=self.customer, kind='order.delivered').exists())
        self.assertFalse(self.parcel_notes().exists())

    def test_guest_orders_send_nothing(self):
        order = make_order(user=None)
        shipment = book_shipment(
            order, make_user(role='seller'), client=FakeClient(consignment_id=1424199, tracking_code='SF2'))

        refresh_shipment(shipment, force=True, client=FakeClient(status='hold', trackings=[]))

        self.assertFalse(Notification.objects.filter(kind='parcel.update').exists())
