from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient

from apps.orders.tests.factories import ShopTestCase, make_product, make_user
from apps.products.homepage import build_homepage, ensure_curated_product_sections
from apps.products.models import HomepageSection, HomepageSectionProduct, Product


class HomepageSectionAdminTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.staff = make_user(role='seller', is_staff=True)
        self.api = APIClient()
        self.api.force_authenticate(self.staff)
        self.alpha = make_product(name='Alpha Buds', price='1000.00')
        self.beta = make_product(name='Beta Stand', price='1500.00')
        self.gamma = make_product(name='Gamma Lamp', price='2000.00')
        now = timezone.now()
        Product.objects.filter(pk=self.alpha.pk).update(created_at=now - timedelta(days=2))
        Product.objects.filter(pk=self.beta.pk).update(created_at=now - timedelta(days=1))
        Product.objects.filter(pk=self.gamma.pk).update(created_at=now)

    def test_list_ensures_trending_and_new_arrivals(self):
        response = self.api.get('/api/v1/products/admin/homepage-sections/')
        self.assertEqual(response.status_code, 200, response.content)
        keys = [row['key'] for row in response.json()]
        self.assertEqual(keys, ['trending', 'new-arrivals'])

    def test_curate_trending_products_and_expose_on_homepage(self):
        response = self.api.patch('/api/v1/products/admin/homepage-sections/trending/', {
            'title': 'Hot Right Now',
            'is_enabled': True,
            'item_limit': 8,
            'product_source': 'manual',
            'product_ids': [str(self.beta.id), str(self.alpha.id)],
        }, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body['title'], 'Hot Right Now')
        self.assertEqual([item['id'] for item in body['products']], [str(self.beta.id), str(self.alpha.id)])

        homepage = build_homepage(request=None)
        trending = next(section for section in homepage['sections'] if section['key'] == 'trending')
        self.assertEqual(trending['title'], 'Hot Right Now')
        self.assertEqual(
            [product['id'] for product in trending['products']],
            [str(self.beta.id), str(self.alpha.id)],
        )

    def test_new_arrivals_latest_clears_manual_picks(self):
        ensure_curated_product_sections()
        section = HomepageSection.objects.get(key='new-arrivals')
        HomepageSectionProduct.objects.create(section=section, product=self.alpha, display_order=0)

        response = self.api.patch('/api/v1/products/admin/homepage-sections/new-arrivals/', {
            'product_source': 'latest',
            'product_ids': [str(self.beta.id)],
        }, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['products'], [])
        self.assertFalse(HomepageSectionProduct.objects.filter(section__key='new-arrivals').exists())

        homepage = build_homepage(request=None)
        arrivals = next(section for section in homepage['sections'] if section['key'] == 'new-arrivals')
        self.assertEqual(arrivals['products'][0]['id'], str(self.gamma.id))

    def test_featured_toggle_drives_trending_homepage(self):
        ensure_curated_product_sections()
        HomepageSection.objects.filter(key='trending').update(product_source='featured')
        self.beta.is_featured = True
        self.beta.save(update_fields=['is_featured'])

        homepage = build_homepage(request=None)
        trending = next(section for section in homepage['sections'] if section['key'] == 'trending')
        self.assertEqual([product['id'] for product in trending['products']], [str(self.beta.id)])
