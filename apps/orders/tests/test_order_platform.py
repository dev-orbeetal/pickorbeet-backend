from rest_framework.test import APIClient

from apps.orders.models import Cart, CartItem, Order
from apps.orders.tests.factories import ShopTestCase, make_order, make_product, make_user


class OrderPlatformCheckoutTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_user()
        self.api = APIClient()
        self.api.force_authenticate(self.customer)
        self.product = make_product(name='Platform Speaker', price='999.00')
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        self.address = {
            'shipping_name': 'Rakibul Hasan',
            'shipping_phone': '01712345678',
            'shipping_address_line1': 'House 12, Road 4',
            'shipping_division': 'Dhaka',
            'shipping_city': 'Gulshan',
            'shipping_district': 'Dhaka',
            'shipping_post_office': 'Gulshan Model Town',
            'shipping_postal_code': '1212',
            'payment_method': 'cod',
        }

    def _checkout(self, payload=None, **headers):
        body = {**self.address, **(payload or {})}
        return self.api.post(
            '/api/v1/orders/checkout/',
            body,
            format='json',
            **headers,
        )

    def test_checkout_persists_web_platform(self):
        web = self._checkout({'platform': 'web'})
        self.assertEqual(web.status_code, 201, web.content)
        self.assertEqual(web.json()['order']['platform'], 'web')
        self.assertEqual(Order.objects.get(id=web.json()['order']['id']).platform, 'web')

    def test_checkout_persists_app_platform(self):
        app = self._checkout({'platform': 'app'})
        self.assertEqual(app.status_code, 201, app.content)
        self.assertEqual(app.json()['order']['platform'], 'app')
        self.assertEqual(Order.objects.get(id=app.json()['order']['id']).platform, 'app')

    def test_missing_platform_is_unknown(self):
        response = self._checkout()
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['order']['platform'], 'unknown')

    def test_admin_in_checkout_body_is_coerced_to_unknown(self):
        response = self._checkout({'platform': 'admin'})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['order']['platform'], 'unknown')

    def test_header_fallback_when_body_omitted(self):
        response = self._checkout(HTTP_X_CLIENT_PLATFORM='web')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['order']['platform'], 'web')

    def test_body_wins_over_header(self):
        response = self._checkout({'platform': 'app'}, HTTP_X_CLIENT_PLATFORM='web')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['order']['platform'], 'app')


class OrderPlatformAdminTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.staff = make_user(role='seller', is_staff=True)
        self.api = APIClient()
        self.api.force_authenticate(self.staff)
        self.product = make_product(name='Admin Speaker', price='1500.00', stock=10)

    def test_external_order_sets_platform_admin(self):
        response = self.api.post('/api/v1/orders/admin/external/', {
            'customer_name': 'Nadia Rahman',
            'customer_phone': '+8801711000000',
            'shipping_address_line1': 'House 9, Road 3',
            'shipping_division': 'Dhaka',
            'shipping_city': 'Dhaka',
            'shipping_district': 'Dhaka',
            'shipping_post_office': 'Dhaka GPO',
            'shipping_postal_code': '1000',
            'items': [{
                'product_id': str(self.product.id),
                'quantity': 1,
                'unit_price': '1200.00',
            }],
            'order_status': 'confirmed',
            'payment_status': 'pending',
            'payment_method': 'cod',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        order = Order.objects.get(id=response.json()['order']['id'])
        self.assertEqual(order.platform, 'admin')
        self.assertEqual(response.json()['order']['platform'], 'admin')

    def test_admin_list_filters_by_platform(self):
        customer = make_user()
        make_order(user=customer, platform='app')
        make_order(user=customer, platform='web')
        response = self.api.get('/api/v1/orders/admin/', {'platform': 'app'})
        self.assertEqual(response.status_code, 200, response.content)
        rows = response.json().get('results', response.json())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['platform'], 'app')
