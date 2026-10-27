from rest_framework.test import APIClient

from apps.orders.tests.factories import ShopTestCase, make_product, make_user
from apps.products.models import ProductReview, ProductSpecification


class ProductSpecificationAndReviewTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.product = make_product(name='Oraimo Necklace Lite')
        self.customer = make_user(first_name='Nusrat', last_name='Jahan')
        self.other = make_user(first_name='Imran', last_name='Hossain')
        self.staff = make_user(role='seller', is_staff=True)

    def detail(self):
        response = APIClient().get(f'/api/v1/products/{self.product.slug}/')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_staff_replaces_specifications_and_a_plain_update_keeps_them(self):
        self.api.force_authenticate(self.staff)
        created = self.api.patch(
            f'/api/v1/products/admin/products/{self.product.id}/',
            {'specifications': [
                {'name': 'Brand', 'value': 'Oraimo'},
                {'name': 'Model', 'value': 'OEB-311'},
            ]},
            format='json',
        )
        self.assertEqual(created.status_code, 200, created.content)

        kept = self.api.patch(
            f'/api/v1/products/admin/products/{self.product.id}/',
            {'short_description': 'Wireless comfort, all day'},
            format='json',
        )
        self.assertEqual(kept.status_code, 200, kept.content)

        rows = [(row['name'], row['value']) for row in self.detail()['specifications']]
        self.assertEqual(rows, [('Brand', 'Oraimo'), ('Model', 'OEB-311')])
        self.assertEqual(self.detail()['review_count'], 0)
        self.assertIsNone(self.detail()['rating_average'])

        replaced = self.api.patch(
            f'/api/v1/products/admin/products/{self.product.id}/',
            {'specifications': [{'name': 'Warranty', 'value': '1 year'}]},
            format='json',
        )
        self.assertEqual(replaced.status_code, 200, replaced.content)
        self.assertEqual(ProductSpecification.objects.filter(product=self.product).count(), 1)
        self.assertEqual(self.detail()['specifications'][0]['name'], 'Warranty')

    def test_partial_specification_is_rejected(self):
        self.api.force_authenticate(self.staff)
        response = self.api.patch(
            f'/api/v1/products/admin/products/{self.product.id}/',
            {'specifications': [{'name': 'Brand', 'value': ''}]},
            format='json',
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(ProductSpecification.objects.filter(product=self.product).count(), 0)

    def test_one_review_per_customer_updates_the_average(self):
        self.api.force_authenticate(self.customer)
        created = self.api.post(
            f'/api/v1/products/{self.product.slug}/reviews/',
            {'rating': 5, 'comment': 'Clear sound'},
            format='json',
        )
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.json()['author'], 'Nusrat Jahan')

        updated = self.api.post(
            f'/api/v1/products/{self.product.slug}/reviews/',
            {'rating': 4, 'comment': 'Still good'},
            format='json',
        )
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertEqual(ProductReview.objects.filter(product=self.product).count(), 1)
        self.assertEqual(updated.json()['comment'], 'Still good')

        self.api.force_authenticate(self.other)
        second = self.api.post(
            f'/api/v1/products/{self.product.slug}/reviews/',
            {'rating': 2, 'comment': 'Average fit'},
            format='json',
        )
        self.assertEqual(second.status_code, 201, second.content)

        body = self.detail()
        self.assertEqual(body['review_count'], 2)
        self.assertEqual(body['rating_average'], 3.0)

        listing = APIClient().get('/api/v1/products/', {'search': 'Necklace'})
        self.assertEqual(listing.status_code, 200, listing.content)
        payload = listing.json()
        rows = payload if isinstance(payload, list) else payload['results']
        match = next(row for row in rows if row['id'] == str(self.product.id))
        self.assertEqual(match['review_count'], 2)
        self.assertEqual(match['rating_average'], 3.0)

        public = APIClient().get(f'/api/v1/products/{self.product.slug}/reviews/')
        self.assertEqual(public.status_code, 200, public.content)
        self.assertIsNone(public.json()['mine'])
        self.assertEqual(public.json()['count'], 2)
        self.assertEqual(len(public.json()['results']), 2)

    def test_guests_cannot_post_and_only_the_author_can_delete(self):
        guest = self.api.post(
            f'/api/v1/products/{self.product.slug}/reviews/',
            {'rating': 5, 'comment': 'Nice'},
            format='json',
        )
        self.assertEqual(guest.status_code, 401, guest.content)

        self.api.force_authenticate(self.customer)
        saved = self.api.post(
            f'/api/v1/products/{self.product.slug}/reviews/',
            {'rating': 5, 'comment': 'Nice'},
            format='json',
        )
        self.assertEqual(saved.status_code, 201, saved.content)

        blank = self.api.post(
            f'/api/v1/products/{self.product.slug}/reviews/',
            {'rating': 5, 'comment': '   '},
            format='json',
        )
        self.assertEqual(blank.status_code, 400, blank.content)

        self.api.force_authenticate(self.other)
        denied = self.api.delete(f'/api/v1/products/{self.product.slug}/reviews/')
        self.assertEqual(denied.status_code, 404, denied.content)
        self.assertEqual(ProductReview.objects.filter(product=self.product).count(), 1)

        self.api.force_authenticate(self.customer)
        gone = self.api.delete(f'/api/v1/products/{self.product.slug}/reviews/')
        self.assertEqual(gone.status_code, 204, gone.content)
        self.assertEqual(self.detail()['review_count'], 0)
        self.assertIsNone(self.detail()['rating_average'])
