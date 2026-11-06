from rest_framework.test import APIClient

from apps.orders.tests.factories import ShopTestCase, make_product, make_user
from apps.products.models import ProductVariant


class DealerAvailableVariantTests(ShopTestCase):
    """Per-variant dealer availability feeds the public In Stock / Out of Stock status."""

    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.product = make_product(name='Dealer Variant Phone')
        self.product.sku = 'DVP-1'
        self.product.dealer_available = False
        self.product.save(update_fields=['sku', 'dealer_available'])
        self.staff = make_user(role='seller', is_staff=True)
        self.api.force_authenticate(self.staff)

        setup = self.api.put(
            f'/api/v1/products/admin/products/{self.product.id}/variant-setup/',
            {
                'option_groups': [
                    {
                        'name': 'Color',
                        'kind': 'swatch',
                        'values': [
                            {'label': 'Black', 'color_hex': '#111111'},
                            {'label': 'White', 'color_hex': '#F5F5F5'},
                        ],
                    },
                ],
                'variants': [
                    {
                        'barcode': 'ZZV-DVP-BLK',
                        'price': '1200.00',
                        'low_stock_threshold': 2,
                        'is_active': True,
                        'dealer_available': True,
                        'selections': [{'name': 'Color', 'label': 'Black'}],
                    },
                    {
                        'barcode': 'ZZV-DVP-WHT',
                        'price': '1200.00',
                        'low_stock_threshold': 2,
                        'is_active': True,
                        'dealer_available': False,
                        'selections': [{'name': 'Color', 'label': 'White'}],
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(setup.status_code, 200, setup.content)
        self.black = ProductVariant.objects.get(product=self.product, color='Black')
        self.white = ProductVariant.objects.get(product=self.product, color='White')
        self.assertTrue(self.black.dealer_available)
        self.assertFalse(self.white.dealer_available)

    def test_public_detail_marks_unavailable_variants_out_of_stock(self):
        public = APIClient().get(f'/api/v1/products/{self.product.slug}/')
        self.assertEqual(public.status_code, 200, public.content)
        body = public.json()
        availability = {variant['sku']: variant['availability'] for variant in body['variants']}
        self.assertEqual(availability[self.black.sku], 'in_stock')
        self.assertEqual(availability[self.white.sku], 'out_of_stock')
        color_labels = [
            value['label']
            for group in body['option_groups']
            if group['name'] == 'Color'
            for value in group['values']
        ]
        self.assertEqual(color_labels, ['Black', 'White'])
        self.assertFalse(body['is_out_of_stock'])

    def test_public_list_keeps_products_without_available_variants(self):
        self.black.dealer_available = False
        self.black.save(update_fields=['dealer_available'])
        listed = APIClient().get('/api/v1/products/')
        self.assertEqual(listed.status_code, 200, listed.content)
        rows = {row['id']: row for row in listed.json().get('results', listed.json())}
        self.assertEqual(rows[str(self.product.id)]['availability'], 'out_of_stock')
        self.assertTrue(rows[str(self.product.id)]['is_out_of_stock'])
