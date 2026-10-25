from rest_framework.test import APIClient

from apps.orders.tests.factories import ShopTestCase, make_product
from apps.products.models import Category, SubCategory


class ProductCatalogSearchTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.electronics = Category.objects.create(name='Electronics')
        self.fashion = Category.objects.create(name='Fashion')
        self.earbuds = SubCategory.objects.create(category=self.electronics, name='True Wireless Earbuds')
        self.banks = SubCategory.objects.create(category=self.electronics, name='Power Banks')
        self.other_banks = SubCategory.objects.create(category=self.fashion, name='Power Banks')
        self.anker = make_product(
            name='Anker Soundcore R50i',
            category=self.electronics,
            subcategory=self.earbuds,
            description='Bluetooth audio',
        )
        self.baseus = make_product(
            name='Baseus Adaman',
            category=self.electronics,
            subcategory=self.banks,
            description='20000mAh capacity',
        )
        self.quiet = make_product(
            name='Hoco EQ34 Plus',
            category=self.electronics,
            subcategory=self.earbuds,
            description='Hybrid ANC',
        )
        self.second_bank = make_product(
            name='Oraimo Travel Pack',
            category=self.fashion,
            subcategory=self.other_banks,
            description='Compact charger',
        )
        self.hijab = make_product(name='Cotton Hijab', category=self.fashion, description='Soft fabric')
        self.hidden = make_product(
            name='Hidden Power Brick',
            category=self.electronics,
            subcategory=self.banks,
            description='Not for sale',
            is_active=False,
        )

    def names(self, **params):
        response = self.api.get('/api/v1/products/', params)
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        rows = body if isinstance(body, list) else body['results']
        return {row['name'] for row in rows}, body

    def test_category_name_returns_every_active_product(self):
        found, body = self.names(search='electronics')
        self.assertIsInstance(body, list)
        self.assertEqual(len(body), 3)
        self.assertEqual(found, {self.anker.name, self.baseus.name, self.quiet.name})

    def test_subcategory_name_returns_products_from_every_match(self):
        found, body = self.names(search='  Power   Banks ')
        self.assertIsInstance(body, list)
        self.assertEqual(len(body), 2)
        self.assertEqual(found, {self.baseus.name, self.second_bank.name})

    def test_partial_subcategory_name_includes_products_that_omit_the_word(self):
        found, _body = self.names(search='Earbuds')
        self.assertIn(self.anker.name, found)
        self.assertIn(self.quiet.name, found)
        self.assertNotIn(self.baseus.name, found)
        self.assertNotIn(self.hijab.name, found)

    def test_product_search_still_matches_name_and_ignores_other_categories(self):
        found, body = self.names(search='Soundcore')
        self.assertIsInstance(body, dict)
        self.assertEqual(found, {self.anker.name})

    def test_short_fragment_does_not_dump_a_category(self):
        found, _body = self.names(search='Po')
        self.assertNotIn(self.baseus.name, found)
        self.assertNotIn(self.second_bank.name, found)
