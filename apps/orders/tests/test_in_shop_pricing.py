from decimal import Decimal

from rest_framework.test import APIClient

from apps.orders.models import OrderItem

from .factories import ShopTestCase, make_product, make_user


class InShopCustomPricingTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.seller = make_user(role='seller', is_staff=True)
        self.api = APIClient()
        self.api.force_authenticate(self.seller)
        self.product = make_product(price='1599.00', compare_price='1999.00', stock=5)

    def test_custom_unit_price_and_discount_persist(self):
        response = self.api.post('/api/v1/orders/admin/in-shop/', {
            'customer_name': 'VIP Customer',
            'customer_phone': '01712345678',
            'items': [{
                'product_id': str(self.product.id),
                'quantity': 2,
                'unit_price': '1200.00',
            }],
            'discount': '100.00',
            'payment_method': 'cash',
        }, format='json')

        self.assertEqual(response.status_code, 201, response.content)
        order = response.json()['order']
        self.assertEqual(order['subtotal'], '2400.00')
        self.assertEqual(order['discount'], '100.00')
        self.assertEqual(order['total'], '2300.00')
        self.assertEqual(order['guest_name'], 'VIP Customer')

        item = OrderItem.objects.get(order_id=order['id'])
        self.assertEqual(item.unit_price, Decimal('1200.00'))
        self.assertEqual(item.total_price, Decimal('2400.00'))
        self.assertEqual(item.compare_price, Decimal('1599.00'))

        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('1599.00'))
        self.assertEqual(self.product.stock_quantity, 3)

    def test_catalog_price_used_when_unit_price_omitted(self):
        response = self.api.post('/api/v1/orders/admin/in-shop/', {
            'items': [{
                'product_id': str(self.product.id),
                'quantity': 1,
            }],
            'payment_method': 'cash',
        }, format='json')

        self.assertEqual(response.status_code, 201, response.content)
        item = response.json()['order']['items'][0]
        self.assertEqual(item['unit_price'], '1599.00')
        self.assertEqual(item['compare_price'], '1999.00')
