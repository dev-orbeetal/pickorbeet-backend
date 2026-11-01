from decimal import Decimal

from rest_framework.test import APIClient

from apps.orders.models import Order
from apps.orders.tests.factories import ShopTestCase, make_product, make_user
from apps.shipping.services import BOOKABLE_ORDER_STATUSES


class AdminManualOrderTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.staff = make_user(role='seller', is_staff=True)
        self.api = APIClient()
        self.api.force_authenticate(self.staff)
        self.product = make_product(name='Facebook Jacket', price='2500.00', stock=8)

    def test_creates_online_order_with_custom_price_and_shipping(self):
        response = self.api.post('/api/v1/orders/admin/manual/', {
            'guest_name': 'Nusrat Jahan',
            'guest_phone': '01712345678',
            'guest_email': 'nusrat@example.com',
            'shipping_address_line1': 'House 9, Road 11',
            'shipping_city': 'Dhaka',
            'shipping_district': 'Dhaka',
            'items': [{
                'product_id': str(self.product.id),
                'quantity': 1,
                'unit_price': '2200.00',
            }],
            'discount': '50.00',
            'delivery_charge': '60.00',
            'payment_method': 'bkash',
            'payment_status': 'paid',
            'order_status': 'pending',
            'source': 'Facebook',
            'notes': 'Inbox order from ad campaign',
        }, format='json')

        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()['order']
        self.assertEqual(body['order_type'], 'online')
        self.assertEqual(body['order_status'], 'pending')
        self.assertEqual(body['payment_status'], 'paid')
        self.assertEqual(body['guest_name'], 'Nusrat Jahan')
        self.assertEqual(body['shipping_phone'], '01712345678')
        self.assertEqual(body['subtotal'], '2200.00')
        self.assertEqual(body['delivery_charge'], '60.00')
        self.assertEqual(body['discount'], '50.00')
        self.assertEqual(body['total'], '2210.00')
        self.assertEqual(body['items'][0]['unit_price'], '2200.00')
        self.assertEqual(body['items'][0]['compare_price'], '2500.00')
        self.assertIn('Source: Facebook', body['notes'])

        order = Order.objects.get(pk=body['id'])
        self.assertFalse(order.stock_reduced)
        self.assertEqual(order.order_type, 'online')
        self.assertIn(order.order_status, BOOKABLE_ORDER_STATUSES)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 8)

    def test_confirm_on_create_reduces_stock(self):
        response = self.api.post('/api/v1/orders/admin/manual/', {
            'guest_name': 'Karim',
            'guest_phone': '01812345678',
            'shipping_address_line1': 'Holding 4',
            'shipping_city': 'Chattogram',
            'shipping_district': 'Chattogram',
            'items': [{
                'product_id': str(self.product.id),
                'quantity': 2,
            }],
            'order_status': 'confirmed',
            'payment_status': 'pending',
            'payment_method': 'cod',
            'source': 'WhatsApp',
        }, format='json')

        self.assertEqual(response.status_code, 201, response.content)
        order = response.json()['order']
        self.assertEqual(order['order_status'], 'confirmed')
        self.assertEqual(Decimal(order['delivery_charge']), Decimal('120.00'))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 6)

    def test_requires_items_and_valid_phone(self):
        empty = self.api.post('/api/v1/orders/admin/manual/', {
            'guest_name': 'X',
            'guest_phone': '01712345678',
            'shipping_address_line1': 'A',
            'shipping_city': 'Dhaka',
            'shipping_district': 'Dhaka',
            'items': [],
        }, format='json')
        self.assertEqual(empty.status_code, 400)

        bad_phone = self.api.post('/api/v1/orders/admin/manual/', {
            'guest_name': 'X',
            'guest_phone': '123',
            'shipping_address_line1': 'A',
            'shipping_city': 'Dhaka',
            'shipping_district': 'Dhaka',
            'items': [{'product_id': str(self.product.id), 'quantity': 1}],
        }, format='json')
        self.assertEqual(bad_phone.status_code, 400)
