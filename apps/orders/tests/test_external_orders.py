from decimal import Decimal

from rest_framework.test import APIClient

from apps.orders.models import Order
from apps.orders.tests.factories import ShopTestCase, make_product, make_user
from apps.products.models import Category
from apps.reports.models import StockMovement


class ExternalOrderApiTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.seller = make_user(role='seller', is_staff=True)
        self.api = APIClient()
        self.api.force_authenticate(self.seller)
        self.category = Category.objects.create(name='External Goods')
        self.product = make_product(
            name='Facebook Speaker',
            category=self.category,
            price='1500.00',
            stock=0,
            warehouse_stock=0,
            dealer_stock=0,
        )
        self.product.warehouse_stock = 8
        self.product.dealer_stock = 4
        self.product.stock_quantity = 12
        self.product.cost_price = Decimal('500.00')
        self.product.inventory_cost_value = Decimal('6000.00')
        self.product.save()

    def _payload(self, **overrides):
        body = {
            'customer_name': 'Nadia Rahman',
            'customer_phone': '+8801711000000',
            'customer_email': 'nadia@example.com',
            'shipping_address_line1': 'House 9, Road 3',
            'shipping_division': 'Dhaka',
            'shipping_city': 'Dhaka',
            'shipping_district': 'Dhaka',
            'shipping_post_office': 'Dhaka GPO',
            'shipping_postal_code': '1000',
            'items': [{
                'product_id': str(self.product.id),
                'quantity': 2,
                'unit_price': '1200.00',
            }],
            'delivery_charge': '70.00',
            'discount': '50.00',
            'payment_method': 'cod',
            'order_status': 'confirmed',
            'payment_status': 'pending',
            'notes': 'From Facebook page inbox',
        }
        body.update(overrides)
        return body

    def test_external_order_uses_custom_price_and_normal_stock(self):
        response = self.api.post('/api/v1/orders/admin/external/', self._payload(), format='json')
        self.assertEqual(response.status_code, 201, response.content)
        order = Order.objects.get(id=response.json()['order']['id'])
        self.assertEqual(order.order_type, 'external')
        self.assertEqual(order.processed_by_id, self.seller.id)
        self.assertEqual(order.stock_location, '')
        self.assertTrue(order.stock_reduced)
        self.assertEqual(order.subtotal, Decimal('2400.00'))
        self.assertEqual(order.delivery_charge, Decimal('70.00'))
        self.assertEqual(order.discount, Decimal('50.00'))
        self.assertEqual(order.total, Decimal('2420.00'))
        item = order.items.get()
        self.assertEqual(item.unit_price, Decimal('1200.00'))
        self.assertEqual(item.quantity, 2)

        self.product.refresh_from_db()
        # Normal deduction prefers warehouse, then dealer.
        self.assertEqual(self.product.warehouse_stock, 6)
        self.assertEqual(self.product.dealer_stock, 4)
        self.assertEqual(self.product.stock_quantity, 10)
        movement = StockMovement.objects.get(reference_order=order, reason='sale')
        self.assertEqual(movement.location, 'warehouse')
        self.assertEqual(movement.quantity, -2)

    def test_custom_price_stays_on_the_order_and_off_the_catalog(self):
        response = self.api.post('/api/v1/orders/admin/external/', self._payload(), format='json')
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()['order']
        self.assertEqual(body['items'][0]['unit_price'], '1200.00')
        self.assertEqual(body['items'][0]['compare_price'], '1999.00')
        self.assertEqual(body['guest_name'], 'Nadia Rahman')
        self.assertIn('From Facebook page inbox', body['notes'])
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('1500.00'))

    def test_order_requires_items_prices_and_a_valid_phone(self):
        url = '/api/v1/orders/admin/external/'
        no_price = [{'product_id': str(self.product.id), 'quantity': 1}]
        for name, overrides in (
            ('no items', {'items': []}),
            ('no unit price', {'items': no_price}),
            ('no division', {'shipping_division': ''}),
            ('bad phone', {'customer_phone': '123'}),
        ):
            with self.subTest(name):
                response = self.api.post(url, self._payload(**overrides), format='json')
                self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Order.objects.exists())

    def test_edit_rejects_an_invalid_phone(self):
        created = self.api.post('/api/v1/orders/admin/external/', self._payload(), format='json')
        order_id = created.json()['order']['id']
        response = self.api.patch(
            f'/api/v1/orders/admin/{order_id}/external/', {'customer_phone': '123'}, format='json',
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_external_order_can_deduct_from_dealer_stock(self):
        response = self.api.post(
            '/api/v1/orders/admin/external/',
            self._payload(stock_location='dealer', order_status='delivered', payment_status='paid'),
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.product.refresh_from_db()
        self.assertEqual(self.product.warehouse_stock, 8)
        self.assertEqual(self.product.dealer_stock, 2)
        self.assertEqual(self.product.stock_quantity, 10)

    def test_pending_external_order_does_not_deduct_stock_yet(self):
        response = self.api.post(
            '/api/v1/orders/admin/external/',
            self._payload(order_status='pending'),
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.content)
        order = Order.objects.get(id=response.json()['order']['id'])
        self.assertFalse(order.stock_reduced)
        self.product.refresh_from_db()
        self.assertEqual(self.product.warehouse_stock, 8)
        self.assertEqual(self.product.stock_quantity, 12)

    def test_insufficient_location_stock_is_rejected(self):
        response = self.api.post(
            '/api/v1/orders/admin/external/',
            self._payload(stock_location='dealer', items=[{
                'product_id': str(self.product.id),
                'quantity': 5,
                'unit_price': '1200.00',
            }]),
            format='json',
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Order.objects.filter(order_type='external').exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.dealer_stock, 4)

    def test_external_order_can_be_edited(self):
        created = self.api.post('/api/v1/orders/admin/external/', self._payload(), format='json')
        self.assertEqual(created.status_code, 201, created.content)
        order_id = created.json()['order']['id']
        self.product.refresh_from_db()
        self.assertEqual(self.product.warehouse_stock, 6)

        updated = self.api.patch(f'/api/v1/orders/admin/{order_id}/external/', {
            'customer_name': 'Updated Customer',
            'customer_phone': '+8801711000099',
            'shipping_address_line1': 'New House 1',
            'shipping_division': 'Chattogram',
            'shipping_city': 'Chittagong',
            'shipping_district': 'Chattogram',
            'shipping_post_office': 'Chattogram GPO',
            'shipping_postal_code': '4000',
            'delivery_charge': '100.00',
            'discount': '20.00',
            'payment_status': 'paid',
            'notes': 'Edited from admin',
            'items': [{
                'product_id': str(self.product.id),
                'quantity': 3,
                'unit_price': '1100.00',
            }],
            'stock_location': 'warehouse',
        }, format='json')
        self.assertEqual(updated.status_code, 200, updated.content)
        order = Order.objects.get(id=order_id)
        self.assertEqual(order.guest_name, 'Updated Customer')
        self.assertEqual(order.shipping_city, 'Chittagong')
        self.assertEqual(order.delivery_charge, Decimal('100.00'))
        self.assertEqual(order.discount, Decimal('20.00'))
        self.assertEqual(order.payment_status, 'paid')
        self.assertEqual(order.notes, 'Edited from admin')
        self.assertEqual(order.subtotal, Decimal('3300.00'))
        self.assertEqual(order.total, Decimal('3380.00'))
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.get().quantity, 3)
        self.assertEqual(order.items.get().unit_price, Decimal('1100.00'))
        self.product.refresh_from_db()
        # Restored 2, then deducted 3 from original 8 → 5.
        self.assertEqual(self.product.warehouse_stock, 5)
        self.assertTrue(order.stock_reduced)
