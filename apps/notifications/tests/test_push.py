"""What a phone receives: the channel, the tray tag and what happens when FCM refuses."""
from unittest import mock

from apps.notifications.delivery import PushNotDelivered, send_push, tray_style
from apps.notifications.models import Device, Notification
from apps.orders.tests.factories import ShopTestCase, make_order, make_user


class Sent:
    def __init__(self, success, exception=None):
        self.success = success
        self.exception = exception


class Batch:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.success_count = sum(1 for item in responses if item.success)


class Unavailable(Exception):
    code = 'unavailable'


class UnregisteredError(Exception):
    pass


class PushTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_user()
        self.order = make_order(user=self.customer)
        Device.objects.create(user=self.customer, token='phone-token', platform='android', device_id='phone-1')

    def note(self, kind='parcel.update', **data):
        return Notification.objects.create(
            recipient=self.customer, kind=kind, title='Out for delivery', body='Parcel is out for delivery',
            data=data, dedupe_key=f'test:{Notification.objects.count()}',
        )

    def send(self, notification, batch):
        with mock.patch('apps.notifications.delivery._firebase', return_value=object()), \
                mock.patch('firebase_admin.messaging.send_each_for_multicast', return_value=batch) as sent:
            result = send_push(notification)
        return result, sent.call_args.args[0]

    def test_order_updates_share_one_tray_entry_per_order(self):
        note = self.note(order_id=str(self.order.id), target='order')

        result, message = self.send(note, Batch(Sent(True)))

        self.assertTrue(result)
        android = message.android.notification
        self.assertEqual(android.channel_id, 'orders')
        self.assertEqual(android.tag, f'order-{self.order.id}')
        self.assertEqual(android.icon, 'ic_stat_notify')
        self.assertEqual(android.color, '#0040EE')
        self.assertEqual(message.data['tag'], f'order-{self.order.id}')
        self.assertEqual(message.data['kind'], 'parcel.update')
        note.refresh_from_db()
        self.assertIsNotNone(note.push_sent_at)

    def test_a_new_arrival_uses_the_offers_channel_and_the_product_photo(self):
        note = self.note(
            kind='product.arrival',
            target='product',
            product_slug='air-max',
            image='https://cdn.example/air.jpg',
            campaign_id='c-1',
        )
        self.assertEqual(tray_style(note), ('offers', 'campaign-c-1'))
        _, message = self.send(note, Batch(Sent(True)))
        self.assertEqual(message.android.notification.channel_id, 'offers')
        self.assertEqual(message.notification.image, 'https://cdn.example/air.jpg')

    def test_help_chat_replies_use_their_own_channel(self):
        note = self.note(kind='support.reply', target='support', conversation_id='c-1')
        self.assertEqual(tray_style(note), ('support', 'support'))

        _, message = self.send(note, Batch(Sent(True)))

        self.assertEqual(message.android.notification.channel_id, 'support')
        self.assertEqual(message.data['channel'], 'support')

    def test_a_refusal_on_every_phone_is_retried(self):
        note = self.note(order_id=str(self.order.id))

        with self.assertLogs('apps.notifications.delivery', level='WARNING') as logs, \
                self.assertRaises(PushNotDelivered):
            self.send(note, Batch(Sent(False, Unavailable())))

        self.assertIn('unavailable', logs.output[0])
        note.refresh_from_db()
        self.assertIsNone(note.push_sent_at)

    def test_expired_tokens_are_retired_without_a_retry(self):
        note = self.note(order_id=str(self.order.id))

        result, _ = self.send(note, Batch(Sent(False, UnregisteredError())))

        self.assertTrue(result)
        device = Device.objects.get(device_id='phone-1')
        self.assertFalse(device.is_active)
        self.assertEqual(device.token, '')
