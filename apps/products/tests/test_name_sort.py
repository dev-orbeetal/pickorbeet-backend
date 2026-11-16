from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient

from apps.orders.tests.factories import ShopTestCase, make_product, make_user
from apps.products.models import Category
from apps.products.name_sort import similar_name_key

PRODUCTS = '/api/v1/products/admin/products/'


class SimilarNameKeyTests(ShopTestCase):
    def test_color_and_wattage_stay_inside_the_model(self):
        white = similar_name_key('Anker 312 20W PD Charger White')
        black = similar_name_key('Anker 312 30W PD Charger Black')
        other = similar_name_key('Anker 10 Cable')

        self.assertEqual(white.split('\t')[0], black.split('\t')[0])
        self.assertNotEqual(white.split('\t')[0], other.split('\t')[0])
        self.assertLess(other, white)
        self.assertLess(white, black)

    def test_word_order_and_connector_spelling_share_one_family(self):
        first = similar_name_key('Anker PowerLine III USB-C to Lightning Cable, White')
        second = similar_name_key('USB-C to Lightning cable Anker PowerLine III Black')
        self.assertEqual(first.split('\t')[0], second.split('\t')[0])

    def test_model_numbers_sort_in_numeric_order(self):
        h2 = similar_name_key('QCY H2 Pro')
        h3 = similar_name_key('QCY H3')
        h10 = similar_name_key('QCY H10')
        self.assertLess(h2, h3)
        self.assertLess(h3, h10)

    def test_punctuation_and_case_do_not_split_a_name(self):
        self.assertEqual(
            similar_name_key('Anker-Nano (3)'),
            similar_name_key('anker nano 3'),
        )


class AdminProductNameSortTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.api.force_authenticate(make_user(role='super_admin'))
        self.category = Category.objects.create(name='Audio Sort', slug='audio-sort')
        self.names = [
            'Anker 312 30W PD Charger Black',
            'QCY H10',
            'Anker 10 Cable',
            'Anker 312 20W PD Charger White',
            'USB-C to Lightning cable Anker PowerLine III Black',
            'Anker PowerLine III USB-C to Lightning Cable, White',
            'QCY H2 Pro Black',
            'QCY H2 Pro',
        ]
        now = timezone.now()
        for index, name in enumerate(self.names):
            product = make_product(name=name, category=self.category)
            product.created_at = now - timedelta(minutes=len(self.names) - index)
            product.save(update_fields=['created_at'])

    def _names(self, **params):
        response = self.api.get(PRODUCTS, {'page_size': 20, 'category': str(self.category.id), **params})
        self.assertEqual(response.status_code, 200, response.content)
        return [row['name'] for row in response.json()['results']]

    def test_similar_names_are_adjacent_across_pages(self):
        ordered = self._names(ordering='name')
        families = [similar_name_key(name).split('\t')[0] for name in ordered]
        self.assertEqual(families, sorted(families))
        self.assertLess(ordered.index('Anker 312 20W PD Charger White'), ordered.index('QCY H2 Pro'))
        self.assertEqual(ordered.index('Anker 312 30W PD Charger Black') - ordered.index('Anker 312 20W PD Charger White'), 1)
        self.assertEqual(
            abs(
                ordered.index('USB-C to Lightning cable Anker PowerLine III Black')
                - ordered.index('Anker PowerLine III USB-C to Lightning Cable, White')
            ),
            1,
        )

        page = self.api.get(PRODUCTS, {
            'ordering': 'name',
            'page_size': 3,
            'page': 2,
            'category': str(self.category.id),
        })
        self.assertEqual(
            [row['name'] for row in page.json()['results']],
            ordered[3:6],
        )

    def test_default_list_stays_newest_first(self):
        names = self._names()
        self.assertEqual(names[0], self.names[-1])
