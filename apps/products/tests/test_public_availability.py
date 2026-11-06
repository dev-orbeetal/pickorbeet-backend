from decimal import Decimal

from rest_framework.test import APIClient

from apps.orders.tests.factories import ShopTestCase, make_product, make_user
from apps.products.models import ProductVariant

STOCK_KEYS = {
    'stock_quantity', 'warehouse_stock', 'dealer_stock', 'dealer_available',
    'low_stock_threshold', 'is_low_stock', 'cost_price',
}


def leaked_keys(value):
    """Every stock-related key anywhere in a JSON payload."""
    if isinstance(value, dict):
        found = STOCK_KEYS & set(value)
        for child in value.values():
            found |= leaked_keys(child)
        return found
    if isinstance(value, list):
        return set().union(set(), *(leaked_keys(child) for child in value))
    return set()


def make_variant(product, sku, stock, dealer_available):
    return ProductVariant.objects.create(
        product=product, sku=sku, size=sku, stock_quantity=stock,
        warehouse_stock=stock, dealer_available=dealer_available,
    )


class PublicAvailabilityTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()

    def detail(self, product):
        response = self.api.get(f'/api/v1/products/{product.slug}/')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_availability_rules(self):
        cases = [
            (5, True, 'in_stock'),
            (5, False, 'in_stock'),
            (0, True, 'in_stock'),
            (0, False, 'out_of_stock'),
        ]
        for stock, dealer, expected in cases:
            with self.subTest(stock=stock, dealer=dealer):
                body = self.detail(make_product(stock=stock, dealer_available=dealer))
                self.assertEqual(body['availability'], expected)
                self.assertEqual(body['is_out_of_stock'], expected == 'out_of_stock')

    def test_variant_rules_set_the_product_status(self):
        product = make_product(stock=0, dealer_available=False)
        sold_out = make_variant(product, 'V-OUT', 0, False)
        self.assertEqual(self.detail(product)['availability'], 'out_of_stock')

        make_variant(product, 'V-STOCK', 3, False)
        body = self.detail(product)
        self.assertEqual(body['availability'], 'in_stock')
        by_sku = {variant['sku']: variant['availability'] for variant in body['variants']}
        self.assertEqual(by_sku, {sold_out.sku: 'out_of_stock', 'V-STOCK': 'in_stock'})

    def test_inactive_products_stay_hidden(self):
        product = make_product(is_active=False)
        response = self.api.get(f'/api/v1/products/{product.slug}/')
        self.assertEqual(response.status_code, 404)

    def test_public_payloads_never_expose_stock(self):
        product = make_product(stock=3, dealer_available=True, is_featured=True)
        make_variant(product, 'V-PRIV', 2, True)

        customer = APIClient()
        customer.force_authenticate(make_user())
        customer.post('/api/v1/orders/cart/add/', {
            'product_id': str(product.id),
            'variant_id': str(product.variants.first().id),
        }, format='json')

        for client, url in (
            (self.api, f'/api/v1/products/{product.slug}/'),
            (self.api, '/api/v1/products/'),
            (self.api, '/api/v1/products/featured/'),
            (self.api, '/api/v1/products/by-category/'),
            (self.api, '/api/v1/products/homepage/'),
            (self.api, '/api/v1/products/catalog-index/'),
            (customer, '/api/v1/orders/cart/'),
        ):
            with self.subTest(url=url):
                response = client.get(url)
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(leaked_keys(response.json()), set())


class AdminStockTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.api.force_authenticate(make_user(role='seller', is_staff=True))
        self.product = make_product(
            stock=4, warehouse_stock=4, low_stock_threshold=10, cost_price=Decimal('750.50'),
        )
        self.variant_product = make_product(stock=0, low_stock_threshold=10)
        make_variant(self.variant_product, 'V-ADMIN', 2, False)

    def assert_exact_stock(self, row):
        self.assertEqual(row['stock_quantity'], 4)
        self.assertEqual(row['low_stock_threshold'], 10)
        self.assertTrue(row['is_low_stock'])

    def test_admin_list_keeps_exact_stock(self):
        response = self.api.get('/api/v1/products/admin/products/')
        self.assertEqual(response.status_code, 200, response.content)
        rows = {row['id']: row for row in response.json()['results']}
        self.assert_exact_stock(rows[str(self.product.id)])
        self.assertEqual(rows[str(self.variant_product.id)]['variants'][0]['stock_quantity'], 2)

    def test_admin_detail_keeps_exact_stock(self):
        body = self.api.get(f'/api/v1/products/admin/products/{self.product.id}/').json()
        self.assert_exact_stock(body)
        variant_body = self.api.get(
            f'/api/v1/products/admin/products/{self.variant_product.id}/'
        ).json()
        self.assertEqual(variant_body['variants'][0]['warehouse_stock'], 2)
        self.assertIn('dealer_available', variant_body['variants'][0])

    def test_low_stock_report_keeps_exact_stock(self):
        response = self.api.get('/api/v1/products/admin/low-stock/')
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        rows = {row['id']: row for row in data.get('results', data)}
        self.assert_exact_stock(rows[str(self.product.id)])
        self.assertEqual(rows[str(self.variant_product.id)]['variants'][0]['stock_quantity'], 2)

    def test_inventory_separates_buying_and_selling_price(self):
        response = self.api.get('/api/v1/products/admin/inventory/')
        self.assertEqual(response.status_code, 200, response.content)
        rows = {row['id']: row for row in response.json()['items']}
        self.assertEqual(rows[str(self.product.id)]['cost_price'], 750.5)
        self.assertEqual(rows[str(self.product.id)]['price'], float(self.product.price))
        self.assertIsNone(rows[str(self.variant_product.id)]['cost_price'])

    def test_admin_stock_apis_reject_customers(self):
        customer = APIClient()
        customer.force_authenticate(make_user())
        for url in (
            '/api/v1/products/admin/products/',
            '/api/v1/products/admin/inventory/',
            '/api/v1/products/admin/low-stock/',
        ):
            with self.subTest(url=url):
                self.assertEqual(customer.get(url).status_code, 403)
