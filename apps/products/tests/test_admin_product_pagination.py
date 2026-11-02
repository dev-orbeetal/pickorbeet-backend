from rest_framework.test import APIClient

from apps.orders.tests.factories import ShopTestCase, make_product, make_user


class AdminProductPaginationTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.staff = make_user(role='seller', is_staff=True)
        self.api = APIClient()
        self.api.force_authenticate(self.staff)
        for i in range(25):
            make_product(name=f'Product {i}')

    def test_default_page_size_is_twenty(self):
        response = self.api.get('/api/v1/products/admin/products/')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['count'], 25)
        self.assertEqual(len(body['results']), 20)
        self.assertIsNotNone(body['next'])

    def test_page_size_query_param(self):
        response = self.api.get('/api/v1/products/admin/products/', {'page_size': 10, 'page': 2})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['count'], 25)
        self.assertEqual(len(body['results']), 10)
