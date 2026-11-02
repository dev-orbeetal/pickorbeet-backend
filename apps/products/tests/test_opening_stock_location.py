from rest_framework.test import APIClient

from apps.orders.tests.factories import ShopTestCase, make_user
from apps.payments.models import Expense
from apps.products.models import Category, Product


class ProductCreateStockTests(ShopTestCase):
    """Admin product create never sets stock; quantities come from purchases."""

    def setUp(self):
        super().setUp()
        self.seller = make_user(role='seller', is_staff=True)
        self.api = APIClient()
        self.api.force_authenticate(self.seller)
        self.category = Category.objects.create(name='Create Stock')

    def test_create_ignores_stock_quantity_and_starts_at_zero(self):
        created = self.api.post('/api/v1/products/admin/products/', {
            'name': 'Catalog Only',
            'category': str(self.category.id),
            'price': '100.00',
            'cost_price': '40.00',
            'stock_quantity': 5,
            'dealer_available': True,
        }, format='json')
        self.assertEqual(created.status_code, 201, created.content)
        product = Product.objects.get(id=created.json()['id'])
        self.assertEqual(product.warehouse_stock, 0)
        self.assertEqual(product.dealer_stock, 0)
        self.assertEqual(product.stock_quantity, 0)
        self.assertTrue(product.dealer_available)
        self.assertEqual(
            Expense.objects.filter(product=product, category='inventory_purchase').count(),
            0,
        )

    def test_create_allows_dealer_availability_without_quantity(self):
        created = self.api.post('/api/v1/products/admin/products/', {
            'name': 'Dealer Flag Only',
            'category': str(self.category.id),
            'price': '100.00',
            'dealer_available': True,
        }, format='json')
        self.assertEqual(created.status_code, 201, created.content)
        body = created.json()
        product = Product.objects.get(id=body['id'])
        self.assertTrue(product.dealer_available)
        self.assertEqual(product.stock_quantity, 0)
