from rest_framework.test import APIClient

from apps.orders.tests.factories import ShopTestCase, make_product
from apps.products.models import Category, SubCategory


class PublicCategoryVisibilityTests(ShopTestCase):
    def test_hides_categories_and_subcategories_without_active_products(self):
        electronics = Category.objects.create(name='Electronics', is_active=True)
        fashion = Category.objects.create(name='Fashion', is_active=True)
        empty = Category.objects.create(name='Empty Shelf', is_active=True)

        tws = SubCategory.objects.create(category=electronics, name='TWS', is_active=True)
        adapters = SubCategory.objects.create(category=electronics, name='Adapters', is_active=True)
        jackets = SubCategory.objects.create(category=fashion, name='Jackets', is_active=True)

        make_product(name='Earbuds', category=electronics, subcategory=tws, stock=3)
        make_product(name='Inactive charger', category=electronics, subcategory=adapters, is_active=False)
        make_product(name='Inactive jacket', category=fashion, subcategory=jackets, is_active=False)

        response = APIClient().get('/api/v1/products/categories/')
        self.assertEqual(response.status_code, 200, response.content)
        rows = response.json()
        if isinstance(rows, dict) and 'results' in rows:
            rows = rows['results']

        names = [row['name'] for row in rows]
        self.assertIn('Electronics', names)
        self.assertNotIn('Fashion', names)
        self.assertNotIn('Empty Shelf', names)

        electronics_row = next(row for row in rows if row['name'] == 'Electronics')
        sub_names = [sub['name'] for sub in electronics_row['subcategories']]
        self.assertEqual(sub_names, ['TWS'])
