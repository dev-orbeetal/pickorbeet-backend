from rest_framework.test import APIClient

from apps.orders.tests.factories import ShopTestCase, make_product, make_user
from apps.products.models import Category, ProductReview, ProductSpecification, SubCategory


class CatalogIndexTests(ShopTestCase):
    def test_lists_every_active_product_without_pagination(self):
        category = Category.objects.create(name='Phones')
        subcategory = SubCategory.objects.create(category=category, name='Android')
        hidden_category = Category.objects.create(name='Hidden', is_active=False)
        product = make_product(
            name='Galaxy A55',
            price='42999.00',
            stock=4,
            category=category,
            subcategory=subcategory,
            short_description='Official phone',
        )
        ProductSpecification.objects.create(product=product, name='Brand', value='Samsung')
        ProductReview.objects.create(
            product=product,
            user=make_user(),
            rating=5,
            comment='Clear and fast',
        )
        make_product(name='Hidden phone', category=hidden_category, is_active=False)
        make_product(name='Sold out', price='100.00', stock=0, category=category)
        for index in range(20):
            make_product(name=f'Extra phone {index}', category=category, stock=1)

        response = APIClient().get('/api/v1/products/catalog-index/')
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertNotIn('next', body)
        self.assertNotIn('count', body)
        self.assertNotIn('results', body)

        self.assertEqual(len(body['products']), 22)
        row = next(item for item in body['products'] if item['slug'] == product.slug)
        self.assertEqual(row['name'], 'Galaxy A55')
        self.assertEqual(row['price'], '42999.00')
        self.assertEqual(row['short_description'], 'Official phone')
        self.assertIsNone(row['image'])
        self.assertTrue(row['in_stock'])
        self.assertEqual(row['category_slug'], category.slug)
        self.assertEqual(row['brand'], 'Samsung')
        self.assertEqual(row['rating_average'], 5.0)
        self.assertEqual(row['review_count'], 1)
        self.assertTrue(row['updated_at'])

        sold = next(item for item in body['products'] if item['name'] == 'Sold out')
        self.assertFalse(sold['in_stock'])
        self.assertNotIn('Hidden phone', [item['name'] for item in body['products']])

        self.assertEqual(len(body['categories']), 1)
        self.assertEqual(body['categories'][0]['slug'], category.slug)
        self.assertEqual(body['categories'][0]['name'], 'Phones')
        self.assertEqual(body['categories'][0]['subcategories'], [
            {
                'slug': subcategory.slug,
                'name': 'Android',
                'updated_at': body['categories'][0]['subcategories'][0]['updated_at'],
            },
        ])
        self.assertTrue(body['categories'][0]['subcategories'][0]['updated_at'])
