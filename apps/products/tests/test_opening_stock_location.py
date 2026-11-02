from decimal import Decimal

from rest_framework.test import APIClient

from apps.orders.tests.factories import ShopTestCase, make_user
from apps.payments.models import Expense
from apps.products.models import Category, Product


class OpeningStockLocationTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.seller = make_user(role='seller', is_staff=True)
        self.api = APIClient()
        self.api.force_authenticate(self.seller)
        self.category = Category.objects.create(name='Opening Stock')

    def test_warehouse_opening_requires_cost_and_creates_purchase(self):
        denied = self.api.post('/api/v1/products/admin/products/', {
            'name': 'Needs Cost',
            'category': str(self.category.id),
            'price': '100.00',
            'stock_quantity': 5,
            'opening_stock_location': 'warehouse',
        }, format='json')
        self.assertEqual(denied.status_code, 400, denied.content)

        created = self.api.post('/api/v1/products/admin/products/', {
            'name': 'Warehouse Item',
            'category': str(self.category.id),
            'price': '100.00',
            'cost_price': '40.00',
            'stock_quantity': 5,
            'opening_stock_location': 'warehouse',
        }, format='json')
        self.assertEqual(created.status_code, 201, created.content)
        product = Product.objects.get(id=created.json()['id'])
        self.assertEqual(product.warehouse_stock, 5)
        self.assertEqual(product.dealer_stock, 0)
        self.assertEqual(product.stock_quantity, 5)
        self.assertEqual(product.inventory_cost_value, Decimal('200.00'))
        self.assertEqual(
            Expense.objects.filter(product=product, category='inventory_purchase').count(),
            1,
        )

    def test_dealer_opening_does_not_require_purchase(self):
        created = self.api.post('/api/v1/products/admin/products/', {
            'name': 'Dealer Item',
            'category': str(self.category.id),
            'price': '100.00',
            'stock_quantity': 7,
            'opening_stock_location': 'dealer',
        }, format='json')
        self.assertEqual(created.status_code, 201, created.content)
        product = Product.objects.get(id=created.json()['id'])
        self.assertEqual(product.warehouse_stock, 0)
        self.assertEqual(product.dealer_stock, 7)
        self.assertEqual(product.stock_quantity, 7)
        self.assertEqual(
            Expense.objects.filter(product=product, category='inventory_purchase').count(),
            0,
        )
