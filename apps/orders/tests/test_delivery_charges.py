from decimal import Decimal

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from apps.accounts.bd_geo import is_inside_dhaka
from apps.products.models import StoreSettings

from .factories import ShopTestCase, make_order, make_product, make_user
from .test_cart_stock import ADDRESS

CHATTOGRAM = {
    **ADDRESS,
    'shipping_division': 'Chattogram', 'shipping_city': 'Chattogram',
    'shipping_district': 'Chattogram', 'shipping_post_office': 'Chattogram GPO',
    'shipping_postal_code': '4000',
}


class DhakaZoneTests(SimpleTestCase):
    def test_only_dhaka_district_is_inside(self):
        self.assertTrue(is_inside_dhaka(city='Mirpur', district='Dhaka', division='Dhaka'))
        self.assertFalse(is_inside_dhaka(city='Tongi', district='Gazipur', division='Dhaka'))
        self.assertFalse(is_inside_dhaka(city='Narayanganj', district='Narayanganj', division='Dhaka'))

    def test_district_beats_a_dhaka_city_name(self):
        self.assertFalse(is_inside_dhaka(city='Dhaka', district='Noakhali', division='Chattogram'))

    def test_city_decides_only_without_a_district(self):
        self.assertTrue(is_inside_dhaka(city=' Uttara ', district=''))
        self.assertFalse(is_inside_dhaka(city='Feni', district=''))


class DeliveryChargeTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_user()
        self.api = APIClient()
        self.api.force_authenticate(self.customer)

    def checkout(self, address):
        product = make_product(price='1000.00', compare_price=None)
        self.api.post('/api/v1/orders/cart/add/', {'product_id': str(product.id)}, format='json')
        response = self.api.post('/api/v1/orders/checkout/', address, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        return self.customer.orders.latest('created_at')

    def test_defaults_are_70_inside_and_125_outside(self):
        self.assertEqual(self.checkout(ADDRESS).delivery_charge, Decimal('70.00'))
        self.assertEqual(self.checkout(CHATTOGRAM).delivery_charge, Decimal('125.00'))

    def test_checkout_and_cart_use_the_store_amounts(self):
        store = StoreSettings.get_settings()
        store.delivery_charge_inside_dhaka = Decimal('80.00')
        store.delivery_charge_outside_dhaka = Decimal('150.00')
        store.save()

        cart = self.api.get('/api/v1/orders/cart/').json()
        self.assertEqual(Decimal(str(cart['delivery_charge_inside_dhaka'])), Decimal('80.00'))
        self.assertEqual(Decimal(str(cart['delivery_charge_outside_dhaka'])), Decimal('150.00'))

        order = self.checkout(CHATTOGRAM)
        self.assertEqual(order.delivery_charge, Decimal('150.00'))
        self.assertEqual(order.total, Decimal('1150.00'))

    def test_placed_orders_keep_their_charge(self):
        order = make_order(user=self.customer)
        self.assertEqual(order.delivery_charge, Decimal('70.00'))
        store = StoreSettings.get_settings()
        store.delivery_charge_inside_dhaka = Decimal('90.00')
        store.save()
        order.save()
        order.refresh_from_db()
        self.assertEqual(order.delivery_charge, Decimal('70.00'))


class DeliveryChargeSettingsTests(ShopTestCase):
    URL = '/api/v1/products/admin/settings/'

    def client_for(self, role):
        api = APIClient()
        api.force_authenticate(make_user(role=role, is_staff=True))
        return api

    def test_only_a_super_admin_can_change_the_amounts(self):
        denied = self.client_for('seller').patch(self.URL, {'delivery_charge_inside_dhaka': '0'}, format='json')
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(StoreSettings.get_settings().delivery_charge_inside_dhaka, Decimal('70.00'))

        saved = self.client_for('super_admin').patch(self.URL, {
            'delivery_charge_inside_dhaka': '75',
            'delivery_charge_outside_dhaka': '130.50',
        }, format='json')
        self.assertEqual(saved.status_code, 200, saved.content)
        store = StoreSettings.get_settings()
        self.assertEqual(store.delivery_charge_inside_dhaka, Decimal('75.00'))
        self.assertEqual(store.delivery_charge_outside_dhaka, Decimal('130.50'))

        public = APIClient().get('/api/v1/products/settings/public/').json()
        self.assertEqual(Decimal(str(public['delivery_charge_inside_dhaka'])), Decimal('75.00'))

    def test_rejects_amounts_that_are_not_a_charge(self):
        api = self.client_for('super_admin')
        for value in ('-1', 'abc', 'NaN', '10001'):
            response = api.patch(self.URL, {'delivery_charge_outside_dhaka': value}, format='json')
            self.assertEqual(response.status_code, 400, value)
        self.assertEqual(StoreSettings.get_settings().delivery_charge_outside_dhaka, Decimal('125.00'))

    def test_other_staff_can_still_save_the_rest(self):
        response = self.client_for('seller').patch(self.URL, {'popular_searches': 'Earbuds'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(StoreSettings.get_settings().popular_searches, 'Earbuds')
