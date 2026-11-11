import base64
import json
import tempfile
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase
from rest_framework.test import APIClient

from apps.orders.tests.factories import ShopTestCase, make_product, make_user
from apps.products.catalog_pricing import catalog_price_increase, raised_catalog_prices
from apps.products.models import CatalogImport, Category, Product

PRODUCTS = '/api/v1/products/admin/products/'
IMPORTS = '/api/v1/products/admin/imports/'
PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
)
HIDDEN = {'provider', 'catalog_import', 'source_url'}


def payload_keys(value):
    if isinstance(value, dict):
        found = set(value)
        for child in value.values():
            found |= payload_keys(child)
        return found
    if isinstance(value, list):
        return set().union(*(payload_keys(child) for child in value)) if value else set()
    return set()


class CatalogImportTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.staff = make_user(role='super_admin')
        self.api.force_authenticate(self.staff)
        self.public = APIClient()

    def write_catalog(self, root, *, price='100.00', sku='IT-1'):
        root = Path(root)
        image_dir = root / 'images' / sku
        image_dir.mkdir(parents=True)
        (image_dir / '01.png').write_bytes(PNG)
        (root / 'categories.json').write_text(json.dumps([
            {
                'name': 'Monitor', 'slug': 'monitor', 'description': '',
                'parent_slug': None, 'display_order': 0, 'image': None,
            },
            {
                'name': 'Esonic', 'slug': 'monitor-esonic', 'description': '',
                'parent_slug': 'monitor', 'display_order': 0, 'image': None,
            },
        ]), encoding='utf-8')
        (root / 'products.json').write_text(json.dumps([{
            'name': 'Fixture Monitor',
            'slug': 'it-fixture-monitor',
            'sku': sku,
            'category_slug': 'monitor',
            'subcategory_slug': 'monitor-esonic',
            'description': 'A scraped monitor',
            'short_description': 'Fixture',
            'price': price,
            'compare_price': '200.00',
            'color': 'White',
            'warranty_period': '1 year',
            'stock_quantity': 9,
            'warehouse_stock': 9,
            'dealer_stock': 4,
            'is_active': True,
            'specifications': [{'name': 'Brand', 'value': 'Esonic', 'sort_order': 0}],
            'images': [{
                'image': f'images/{sku}/01.png',
                'alt_text': 'Fixture Monitor',
                'is_primary': True,
                'display_order': 0,
            }],
            'source': {
                'site': 'https://i-tech-computer.com',
                'url': 'https://i-tech-computer.com/product/fixture/',
                'external_id': '1',
            },
        }]), encoding='utf-8')

    def import_fixture(self, **kwargs):
        folder = tempfile.mkdtemp()
        self.write_catalog(folder, **kwargs)
        call_command('import_scraped_catalog', folder, provider='itech')
        return folder

    def test_import_is_idempotent_and_hidden_from_shoppers(self):
        self.import_fixture()
        product = Product.objects.get(sku='IT-1')
        self.assertEqual(product.catalog_import.provider, 'itech')
        self.assertEqual(product.catalog_import.label, 'i-Tech')
        self.assertEqual(product.price, Decimal('150.00'))
        self.assertEqual(product.compare_price, Decimal('250.00'))
        self.assertEqual(product.stock_quantity, 0)
        self.assertEqual(product.warehouse_stock, 0)
        self.assertEqual(product.dealer_stock, 0)
        self.assertFalse(product.dealer_available)
        self.assertEqual(product.warranty_period, '1 year')
        self.assertEqual(product.subcategory.slug, 'monitor-esonic')
        self.assertTrue(product.category.is_active)
        self.assertFalse(product.category.is_featured)
        image_name = product.images.get().image.name
        self.assertTrue(image_name.startswith('products/imports/itech/IT-1/'))
        self.assertTrue((Path(settings.MEDIA_ROOT) / image_name).is_file())
        self.assertEqual(product.specifications.get().value, 'Esonic')

        detail = self.public.get(f'/api/v1/products/{product.slug}/')
        self.assertEqual(detail.status_code, 200, detail.content)
        self.assertFalse(HIDDEN & payload_keys(detail.json()))
        self.assertEqual(detail.json()['availability'], 'out_of_stock')
        self.assertEqual(detail.json()['stock_quantity'], 0)
        self.assertNotIn('warehouse_stock', detail.json())
        listed = self.public.get('/api/v1/products/', {'category_slug': 'monitor'})
        self.assertEqual(listed.status_code, 200, listed.content)
        self.assertFalse(HIDDEN & payload_keys(listed.json()))

        admin = self.api.get(f'{PRODUCTS}{product.id}/')
        self.assertEqual(admin.status_code, 200, admin.content)
        self.assertEqual(admin.json()['provider'], 'itech')
        self.assertEqual(admin.json()['catalog_import'], str(product.catalog_import_id))
        self.assertEqual(admin.json()['source_url'], 'https://i-tech-computer.com/product/fixture/')

        product.price = Decimal('50.00')
        product.save(update_fields=['price'])
        self.import_fixture(price='999.00')
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal('50.00'))
        self.assertEqual(CatalogImport.objects.count(), 1)

        self.import_fixture(sku='IT-2')
        added = Product.objects.get(sku='IT-2')
        product.refresh_from_db()
        self.assertEqual(added.catalog_import.label, 'i-Tech 2')
        self.assertNotEqual(added.catalog_import_id, product.catalog_import_id)
        self.assertEqual(product.catalog_import.label, 'i-Tech')

    def test_batch_percent_updates_only_that_batch(self):
        self.import_fixture()
        imported = Product.objects.get(sku='IT-1')
        store = make_product(name='Store speaker', price='100.00', compare_price='200.00')
        batch = imported.catalog_import

        guest = APIClient()
        denied = guest.post(f'{IMPORTS}{batch.id}/adjust/', {'price_percent': 10}, format='json')
        self.assertIn(denied.status_code, (401, 403))

        empty = self.api.post(f'{IMPORTS}{batch.id}/adjust/', {}, format='json')
        self.assertEqual(empty.status_code, 400, empty.content)

        response = self.api.post(f'{IMPORTS}{batch.id}/adjust/', {'price_percent': 10}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['updated'], 1)
        imported.refresh_from_db()
        store.refresh_from_db()
        self.assertEqual(imported.price, Decimal('165.00'))
        self.assertEqual(imported.compare_price, Decimal('275.00'))
        self.assertEqual(store.price, Decimal('100.00'))
        self.assertEqual(store.compare_price, Decimal('200.00'))

        flags = self.api.post(
            f'{IMPORTS}{batch.id}/adjust/',
            {'dealer_available': True, 'warranty_period': '2 years', 'is_active': False},
            format='json',
        )
        self.assertEqual(flags.status_code, 200, flags.content)
        imported.refresh_from_db()
        store.refresh_from_db()
        self.assertTrue(imported.dealer_available)
        self.assertEqual(imported.warranty_period, '2 years')
        self.assertFalse(imported.is_active)
        self.assertFalse(store.dealer_available)
        self.assertTrue(store.is_active)

        too_low = self.api.post(f'{IMPORTS}{batch.id}/adjust/', {'price_percent': -101}, format='json')
        self.assertEqual(too_low.status_code, 400, too_low.content)
        imported.refresh_from_db()
        self.assertEqual(imported.price, Decimal('165.00'))

    def test_provider_filter_splits_store_and_imported_products(self):
        self.import_fixture()
        imported = Product.objects.get(sku='IT-1')
        store = make_product(name='Store speaker')

        itech = self._ids(provider='itech')
        own = self._ids(provider='store')
        other = self._ids(provider='marvellous')
        self.assertEqual(itech, {str(imported.id)})
        self.assertIn(str(store.id), own)
        self.assertNotIn(str(imported.id), own)
        self.assertEqual(other, set())
        listed = self.api.get(PRODUCTS, {'provider': 'itech'})
        self.assertEqual(listed.json()['results'][0]['provider'], 'itech')

        batches = self.api.get(IMPORTS, {'provider': 'itech'})
        self.assertEqual(batches.status_code, 200, batches.content)
        self.assertEqual(batches.json()[0]['label'], 'i-Tech')
        self.assertEqual(batches.json()[0]['product_count'], 1)
        self.assertFalse(Category.objects.get(slug='monitor').is_featured)

    def _ids(self, **params):
        response = self.api.get(PRODUCTS, params)
        self.assertEqual(response.status_code, 200, response.content)
        return {row['id'] for row in response.json()['results']}


class CatalogPriceBandTests(SimpleTestCase):
    def test_bands(self):
        cases = [
            ('0', '0'),
            ('999.99', '50'),
            ('1000', '100'),
            ('1999.99', '100'),
            ('2000', '200'),
            ('3000', '250'),
            ('4000', '300'),
            ('6000', '400'),
            ('10000', '500'),
            ('14999.99', '500'),
            ('15000', '600'),
            ('20000', '600'),
            ('20000.01', '500'),
            ('145000', '500'),
        ]
        for price, increase in cases:
            with self.subTest(price=price):
                self.assertEqual(catalog_price_increase(price), Decimal(increase))

    def test_compare_price_keeps_the_same_gap(self):
        price, compare = raised_catalog_prices(Decimal('1800.00'), Decimal('2200.00'))
        self.assertEqual(price, Decimal('1900.00'))
        self.assertEqual(compare, Decimal('2300.00'))
        unchanged, no_compare = raised_catalog_prices(Decimal('0.00'), None)
        self.assertEqual(unchanged, Decimal('0.00'))
        self.assertIsNone(no_compare)
