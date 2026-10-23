"""Inbox rules: who is notified, and that the same event is stored once."""
from decimal import Decimal

from rest_framework.test import APIClient

from apps.notifications.models import Device, Notification
from apps.orders.services import change_order_status
from apps.payments.models import Payment
from apps.orders.tests.factories import ShopTestCase, make_order, make_product, make_user


ADDRESS = {
    'guest_email': 'guest@example.com',
    'guest_name': 'Guest Buyer',
    'guest_phone': '01712345678',
    'shipping_name': 'Guest Buyer',
    'shipping_phone': '01712345678',
    'shipping_address_line1': 'House 12, Road 4',
    'shipping_city': 'Dhaka',
    'shipping_district': 'Dhaka',
}


class GuestCheckoutTests(ShopTestCase):
    def test_guest_checkout_alerts_staff_only(self):
        seller = make_user(role='seller')
        admin = make_user(role='super_admin')
        accountant = make_user(role='accountant')
        product = make_product()
        client = APIClient()
        added = client.post(
            '/api/v1/orders/cart/add/',
            {'product_id': str(product.id), 'quantity': 1},
            format='json',
        )
        self.assertEqual(added.status_code, 200, added.content)
        response = client.post('/api/v1/orders/checkout/', ADDRESS, format='json')
        self.assertEqual(response.status_code, 201, response.content)

        rows = Notification.objects.filter(kind='order.placed')
        self.assertEqual(set(rows.values_list('recipient_id', flat=True)), {seller.id, admin.id})
        self.assertFalse(rows.filter(recipient=accountant).exists())
        self.assertTrue(all(row.data['target'] == 'admin_order' for row in rows))


class PaymentNotificationTests(ShopTestCase):
    def test_repeated_ipn_does_not_duplicate(self):
        customer = make_user()
        seller = make_user(role='seller')
        order = make_order(user=customer)
        payment = Payment.objects.create(
            order=order,
            payment_method='sslcommerz',
            status='processing',
            amount=order.total,
            transaction_id='TXN-REPEAT',
        )
        body = {
            'tran_id': 'TXN-REPEAT',
            'status': 'VALID',
            'amount': str(order.total),
            'val_id': 'VAL-1',
        }
        client = APIClient()
        first = client.post('/api/v1/payments/ipn/', body, format='json')
        second = client.post('/api/v1/payments/ipn/', body, format='json')
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(second.status_code, 200, second.content)

        paid_key = f'payment:{payment.id}:paid'
        self.assertEqual(Notification.objects.filter(dedupe_key=paid_key).count(), 2)
        self.assertTrue(Notification.objects.filter(recipient=customer, dedupe_key=paid_key).exists())
        self.assertTrue(Notification.objects.filter(recipient=seller, dedupe_key=paid_key).exists())
        self.assertEqual(
            Notification.objects.filter(recipient=customer, kind='order.confirmed').count(),
            1,
        )
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'paid')
        self.assertEqual(order.order_status, 'confirmed')


class StatusNotificationTests(ShopTestCase):
    def test_unchanged_status_does_not_notify(self):
        customer = make_user()
        seller = make_user(role='seller')
        order = make_order(user=customer, status='confirmed')
        before = Notification.objects.count()

        change_order_status(order, 'confirmed', note='again')
        self.assertEqual(Notification.objects.count(), before)
        self.assertFalse(order.status_history.filter(note='again').exists())

        change_order_status(order, 'shipped', note='Left the warehouse')
        self.assertTrue(Notification.objects.filter(recipient=customer, kind='order.shipped').exists())
        self.assertFalse(Notification.objects.filter(recipient=seller, kind='order.shipped').exists())
        body = Notification.objects.get(recipient=customer, kind='order.shipped').body
        self.assertIn(order.order_number, body)
        self.assertIn('on the way', body)


class RefundNotificationTests(ShopTestCase):
    def test_refund_requester_is_excluded(self):
        customer = make_user()
        accountant = make_user(role='accountant')
        admin = make_user(role='super_admin')
        seller = make_user(role='seller')
        order = make_order(user=customer, status='delivered', payment_status='paid')
        payment = Payment.objects.create(
            order=order,
            payment_method='sslcommerz',
            status='completed',
            amount=Decimal('100.00'),
            transaction_id='TXN-REFUND',
        )
        client = APIClient()
        client.force_authenticate(accountant)
        response = client.post('/api/v1/payments/admin/refunds/', {
            'payment_id': str(payment.id),
            'amount': '100.00',
            'reason': 'Damaged on arrival',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.content)

        requested = Notification.objects.filter(kind='refund.requested')
        self.assertEqual(list(requested.values_list('recipient_id', flat=True)), [admin.id])
        self.assertFalse(requested.filter(recipient=accountant).exists())
        self.assertFalse(requested.filter(recipient=seller).exists())
        self.assertFalse(requested.filter(recipient=customer).exists())


class InboxApiTests(ShopTestCase):
    def test_mark_read_and_device_replacement_stay_on_the_current_user(self):
        owner = make_user()
        other = make_user()
        order = make_order(user=owner)
        change_order_status(order, 'processing', note='Packing')
        note = Notification.objects.get(recipient=owner, kind='order.processing')

        owner_api = APIClient()
        other_api = APIClient()
        owner_api.force_authenticate(owner)
        other_api.force_authenticate(other)

        hidden = other_api.post(f'/api/v1/notifications/{note.id}/read/')
        self.assertEqual(hidden.status_code, 404)
        note.refresh_from_db()
        self.assertIsNone(note.read_at)

        listed = owner_api.get('/api/v1/notifications/')
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()['count'], 1)
        unread = owner_api.get('/api/v1/notifications/unread-count/')
        self.assertEqual(unread.json()['unread_count'], 1)

        marked = owner_api.post(f'/api/v1/notifications/{note.id}/read/')
        self.assertEqual(marked.status_code, 200)
        self.assertIsNotNone(marked.json()['read_at'])
        self.assertEqual(owner_api.get('/api/v1/notifications/unread-count/').json()['unread_count'], 0)
        self.assertEqual(other_api.get('/api/v1/notifications/').json()['count'], 0)

        registered = owner_api.put('/api/v1/notifications/devices/', {
            'token': 'token-owner',
            'platform': 'android',
            'device_id': 'phone-1',
        }, format='json')
        self.assertEqual(registered.status_code, 200, registered.content)

        replaced = other_api.put('/api/v1/notifications/devices/', {
            'token': 'token-owner',
            'platform': 'ios',
            'device_id': 'phone-1',
        }, format='json')
        self.assertEqual(replaced.status_code, 200, replaced.content)
        self.assertFalse(Device.objects.get(user=owner, device_id='phone-1').is_active)
        moved = Device.objects.get(user=other, device_id='phone-1')
        self.assertTrue(moved.is_active)
        self.assertEqual(moved.token, 'token-owner')

        removed = other_api.delete('/api/v1/notifications/devices/phone-1/')
        self.assertEqual(removed.status_code, 204)
        moved.refresh_from_db()
        self.assertFalse(moved.is_active)
        self.assertEqual(moved.token, '')


class DeliveryDispatchTests(ShopTestCase):
    def test_created_row_is_handed_to_the_worker_after_commit(self):
        from apps.notifications.tasks import deliver_notification

        customer = make_user()
        order = make_order(user=customer, status='pending')
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            change_order_status(order, 'processing', note='Packing')
        self.assertTrue(callbacks)
        note = Notification.objects.get(recipient=customer, kind='order.processing')
        deliver_notification(str(note.id))
        note.refresh_from_db()
        self.assertIsNone(note.push_sent_at)
