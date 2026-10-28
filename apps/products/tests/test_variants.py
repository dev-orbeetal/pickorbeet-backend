from rest_framework.test import APIClient

from apps.orders.tests.factories import ShopTestCase, make_product, make_user


class VariantOptionTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.product = make_product(name='Oraimo Necklace Lite')
        self.product.sku = 'ORA-OEB-311'
        self.product.save(update_fields=['sku'])
        self.staff = make_user(role='seller', is_staff=True)
        self.api.force_authenticate(self.staff)

    def payload(self, **overrides):
        body = {
            'option_groups': [
                {'name': 'Size', 'kind': 'text', 'values': [{'label': 'M'}]},
                {
                    'name': 'Color',
                    'kind': 'swatch',
                    'values': [{'label': 'Midnight', 'color_hex': '#0b1f3a'}],
                },
                {'name': 'Storage', 'kind': 'text', 'values': [{'label': '128GB'}]},
            ],
            'variants': [{
                'barcode': 'ZZV-NECK-1',
                'price': '1080.00',
                'stock_quantity': 4,
                'low_stock_threshold': 2,
                'is_active': True,
                'selections': [
                    {'name': 'Size', 'label': 'M'},
                    {'name': 'Color', 'label': 'Midnight'},
                    {'name': 'Storage', 'label': '128GB'},
                ],
            }],
        }
        body.update(overrides)
        return body

    def test_setup_publishes_groups_hex_and_sku(self):
        saved = self.api.put(
            f'/api/v1/products/admin/products/{self.product.id}/variant-setup/',
            self.payload(),
            format='json',
        )
        self.assertEqual(saved.status_code, 200, saved.content)
        variant = saved.json()['variants'][0]
        self.assertEqual(variant['sku'], 'ORA-OEB-311-M-MIDNIGHT-128GB')
        self.assertEqual(variant['size'], 'M')
        self.assertEqual(variant['color'], 'Midnight')
        self.assertEqual(variant['options'][1]['color_hex'], '#0B1F3A')

        public = APIClient().get(f'/api/v1/products/{self.product.slug}/')
        self.assertEqual(public.status_code, 200, public.content)
        body = public.json()
        self.assertEqual(
            [group['name'] for group in body['option_groups']],
            ['Size', 'Color', 'Storage'],
        )
        color = body['option_groups'][1]['values'][0]
        self.assertEqual(color['label'], 'Midnight')
        self.assertEqual(color['color_hex'], '#0B1F3A')
        self.assertEqual(body['variants'][0]['sku'], 'ORA-OEB-311-M-MIDNIGHT-128GB')

        again = self.api.put(
            f'/api/v1/products/admin/products/{self.product.id}/variant-setup/',
            self.payload(variants=[{
                **self.payload()['variants'][0],
                'id': variant['id'],
                'stock_quantity': 9,
            }]),
            format='json',
        )
        self.assertEqual(again.status_code, 200, again.content)
        kept = again.json()['variants'][0]
        self.assertEqual(kept['sku'], 'ORA-OEB-311-M-MIDNIGHT-128GB')
        self.assertEqual(kept['stock_quantity'], 9)

    def test_duplicate_combination_is_rejected(self):
        row = self.payload()['variants'][0]
        response = self.api.put(
            f'/api/v1/products/admin/products/{self.product.id}/variant-setup/',
            self.payload(variants=[row, dict(row)]),
            format='json',
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('same values', response.json()['detail'])

    def test_swatch_without_a_color_is_rejected(self):
        body = self.payload()
        body['option_groups'][1]['values'][0]['color_hex'] = ''
        response = self.api.put(
            f'/api/v1/products/admin/products/{self.product.id}/variant-setup/',
            body,
            format='json',
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('Choose a color', response.json()['detail'])
