from datetime import date

from rest_framework.test import APIClient

from apps.orders.tests.factories import ShopTestCase, make_product, make_user
from apps.payments.purchases import create_purchase_receipt
from apps.products.models import Category, Product, SubCategory

CATEGORIES = '/api/v1/products/admin/categories/'
SUBCATEGORIES = '/api/v1/products/admin/subcategories/'
PRODUCTS = '/api/v1/products/admin/products/'


class AdminCatalogTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.user = make_user(role='super_admin')
        self.api.force_authenticate(self.user)
        self.audio = Category.objects.create(name='Audio', slug='audio')
        self.home = Category.objects.create(name='Home', slug='home')
        self.earphone = SubCategory.objects.create(category=self.audio, name='Earphone')
        self.speaker = SubCategory.objects.create(category=self.audio, name='Speaker')
        self.lamp = SubCategory.objects.create(category=self.home, name='Lamp')

    def _category(self, category):
        rows = self.api.get(CATEGORIES).json()
        return next(row for row in rows if row['id'] == str(category.id))

    def _subcategory(self, category, subcategory):
        rows = self._category(category)['subcategories']
        return next(row for row in rows if row['id'] == str(subcategory.id))

    def _ids(self, **params):
        response = self.api.get(PRODUCTS, params)
        self.assertEqual(response.status_code, 200, response.content)
        return {row['id'] for row in response.json()['results']}

    def test_counts_cover_subcategories_and_direct_products_once(self):
        make_product(name='A', category=self.audio, subcategory=self.earphone)
        make_product(name='B', category=self.audio, subcategory=self.earphone)
        make_product(name='C', category=self.audio, subcategory=self.speaker)
        make_product(name='D', category=self.audio)

        category = self._category(self.audio)
        self.assertEqual(category['product_count'], 4)
        self.assertEqual(category['direct_product_count'], 1)
        counts = {row['name']: row['product_count'] for row in category['subcategories']}
        self.assertEqual(counts, {'Earphone': 2, 'Speaker': 1})

    def test_counts_are_products_not_units_or_variants(self):
        product = make_product(name='Stocked', category=self.audio, subcategory=self.earphone, stock=500)
        product.variants.create(sku='STOCKED-S', size='S', stock_quantity=4)
        product.variants.create(sku='STOCKED-M', size='M', stock_quantity=4)

        self.assertEqual(self._category(self.audio)['product_count'], 1)
        self.assertEqual(self._subcategory(self.audio, self.earphone)['product_count'], 1)

    def test_admin_count_includes_inactive_rows_but_public_count_does_not(self):
        make_product(name='Live', category=self.audio)
        make_product(name='Hidden', category=self.audio, is_active=False)

        self.assertEqual(self._category(self.audio)['product_count'], 2)
        self.assertEqual(len(self._ids(category=str(self.audio.id))), 2)
        public = self.client.get(f'/api/v1/products/categories/{self.audio.slug}/').json()
        self.assertEqual(public['product_count'], 1)
        self.assertNotIn('direct_product_count', public)

    def test_counts_follow_add_move_and_delete(self):
        made = self.api.post(PRODUCTS, {
            'name': 'New Earbud',
            'price': '100.00',
            'category': str(self.audio.id),
            'subcategory': str(self.earphone.id),
        }, format='json')
        self.assertEqual(made.status_code, 201, made.content)
        product_id = made.json()['id']
        self.assertEqual(self._subcategory(self.audio, self.earphone)['product_count'], 1)

        moved = self.api.patch(f'{PRODUCTS}{product_id}/', {
            'category': str(self.home.id),
            'subcategory': str(self.lamp.id),
        }, format='json')
        self.assertEqual(moved.status_code, 200, moved.content)
        self.assertEqual(self._category(self.audio)['product_count'], 0)
        self.assertEqual(self._category(self.home)['product_count'], 1)
        self.assertEqual(self._subcategory(self.home, self.lamp)['product_count'], 1)

        self.assertEqual(self.api.delete(f'{PRODUCTS}{product_id}/').status_code, 204)
        self.assertEqual(self._category(self.home)['product_count'], 0)

    def test_move_keeps_the_same_record_and_its_stock(self):
        product = make_product(name='Mover', category=self.audio, subcategory=self.earphone, stock=7)
        receipt, _expense = create_purchase_receipt(
            purchase_date=date.today(),
            payee='City Wholesale',
            lines=[{'product': product.id, 'quantity': 3, 'unit_cost': '10.00'}],
            user=self.user,
        )
        count = Product.objects.count()
        product.refresh_from_db()
        stock = product.stock_quantity
        before = (product.slug, product.barcode, product.sku, product.price, product.cost_price)

        response = self.api.patch(f'{PRODUCTS}{product.id}/', {
            'category': str(self.home.id),
            'subcategory': None,
        }, format='json')
        self.assertEqual(response.status_code, 200, response.content)

        product.refresh_from_db()
        self.assertEqual(Product.objects.count(), count)
        self.assertEqual(product.category, self.home)
        self.assertIsNone(product.subcategory)
        self.assertEqual(product.stock_quantity, stock)
        self.assertEqual(
            (product.slug, product.barcode, product.sku, product.price, product.cost_price), before,
        )
        self.assertEqual(receipt.lines.get().product_id, product.id)

    def test_subcategory_must_belong_to_the_category(self):
        product = make_product(name='Mover', category=self.audio, subcategory=self.earphone)

        cross = self.api.patch(f'{PRODUCTS}{product.id}/', {
            'category': str(self.home.id),
            'subcategory': str(self.earphone.id),
        }, format='json')
        self.assertEqual(cross.status_code, 400)
        self.assertIn('subcategory', cross.json())

        stale = self.api.patch(f'{PRODUCTS}{product.id}/', {'category': str(self.home.id)}, format='json')
        self.assertEqual(stale.status_code, 400)

        created = self.api.post(PRODUCTS, {
            'name': 'Wrong',
            'price': '10.00',
            'category': str(self.home.id),
            'subcategory': str(self.earphone.id),
        }, format='json')
        self.assertEqual(created.status_code, 400)
        product.refresh_from_db()
        self.assertEqual(product.category, self.audio)

    def test_unrelated_edit_of_a_stale_link_is_not_blocked(self):
        product = make_product(name='Stale', category=self.audio, subcategory=self.lamp)
        response = self.api.patch(f'{PRODUCTS}{product.id}/', {'is_featured': True}, format='json')
        self.assertEqual(response.status_code, 200, response.content)

    def test_direct_filter_lists_products_with_no_subcategory(self):
        direct = make_product(name='Direct', category=self.audio)
        nested = make_product(name='Nested', category=self.audio, subcategory=self.earphone)

        self.assertEqual(self._ids(category=str(self.audio.id), direct='true'), {str(direct.id)})
        self.assertEqual(
            self._ids(category=str(self.audio.id)), {str(direct.id), str(nested.id)},
        )

    def test_stale_link_shows_once_as_a_direct_product(self):
        stale = make_product(name='Stale', category=self.audio, subcategory=self.lamp)

        self.assertEqual(self._ids(category=str(self.audio.id), direct='true'), {str(stale.id)})
        self.assertEqual(self._ids(category=str(self.home.id), subcategory=str(self.lamp.id)), set())
        audio = self._category(self.audio)
        self.assertEqual(audio['product_count'], 1)
        self.assertEqual(audio['direct_product_count'], 1)
        self.assertEqual(self._category(self.home)['product_count'], 0)
        self.assertEqual(self._subcategory(self.home, self.lamp)['product_count'], 0)

    def test_category_list_is_not_cut_off_by_page_size(self):
        for index in range(25):
            Category.objects.create(name=f'Extra {index}', slug=f'extra-{index}')
        rows = self.api.get(CATEGORIES).json()
        self.assertEqual(len(rows), 27)

    def test_categories_and_subcategories_keep_their_display_order(self):
        Category.objects.filter(pk=self.home.pk).update(display_order=0)
        Category.objects.filter(pk=self.audio.pk).update(display_order=1)
        SubCategory.objects.filter(pk=self.earphone.pk).update(display_order=5)
        SubCategory.objects.filter(pk=self.speaker.pk).update(display_order=2)
        make_product(name='Counted', category=self.audio, subcategory=self.earphone)

        rows = self.api.get(CATEGORIES).json()
        self.assertEqual([row['name'] for row in rows], ['Home', 'Audio'])
        self.assertEqual(
            [row['name'] for row in rows[1]['subcategories']], ['Speaker', 'Earphone'],
        )

    def test_category_with_products_refuses_delete_with_a_reason(self):
        make_product(name='Keeper', category=self.audio)
        response = self.api.delete(f'{CATEGORIES}{self.audio.id}/')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Audio', response.json()['detail'])
        self.assertTrue(Category.objects.filter(pk=self.audio.pk).exists())

    def test_empty_category_can_be_deleted(self):
        response = self.api.delete(f'{CATEGORIES}{self.home.id}/')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Category.objects.filter(pk=self.home.pk).exists())

    def test_deleting_a_subcategory_keeps_its_products_in_the_category(self):
        product = make_product(name='Survivor', category=self.audio, subcategory=self.earphone)
        response = self.api.delete(f'{SUBCATEGORIES}{self.earphone.id}/')
        self.assertEqual(response.status_code, 204)

        product.refresh_from_db()
        self.assertIsNone(product.subcategory)
        category = self._category(self.audio)
        self.assertEqual(category['product_count'], 1)
        self.assertEqual(category['direct_product_count'], 1)

    def test_product_with_purchase_records_refuses_delete_and_keeps_its_images(self):
        product = make_product(name='Bought', category=self.audio, stock=0)
        image = product.images.create(image='products/kept.png')
        create_purchase_receipt(
            purchase_date=date.today(),
            payee='City Wholesale',
            lines=[{'product': product.id, 'quantity': 1, 'unit_cost': '10.00'}],
            user=self.user,
        )
        deleted = []
        original = image.image.storage.__class__.delete
        image.image.storage.__class__.delete = lambda storage, name: deleted.append(name)
        self.addCleanup(setattr, image.image.storage.__class__, 'delete', original)

        response = self.api.delete(f'{PRODUCTS}{product.id}/')

        self.assertEqual(response.status_code, 400)
        self.assertIn('inactive', response.json()['detail'])
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())
        self.assertEqual(deleted, [])

    def test_seller_can_reach_the_catalog_endpoints(self):
        seller = APIClient()
        seller.force_authenticate(make_user(role='seller'))
        self.assertEqual(seller.get(CATEGORIES).status_code, 200)
