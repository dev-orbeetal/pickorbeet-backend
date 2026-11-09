from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from apps.orders.tests.factories import ShopTestCase, make_order, make_product, make_user
from apps.products.models import ProductReview, ProductReviewImage, ProductSpecification


def _png(name='photo.png', color=(40, 120, 200)):
    buf = BytesIO()
    Image.new('RGB', (32, 32), color).save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


def _jpeg(name='photo.jpg', content_type='image/jpeg'):
    buf = BytesIO()
    Image.new('RGB', (32, 32), (20, 20, 20)).save(buf, format='JPEG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type=content_type)


class ProductSpecificationAndReviewTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.product = make_product(name='Oraimo Necklace Lite')
        self.customer = make_user(first_name='Nusrat', last_name='Jahan')
        self.other = make_user(first_name='Imran', last_name='Hossain')
        self.staff = make_user(role='seller', is_staff=True)
        make_order(user=self.customer, products=[self.product], status='delivered')
        make_order(user=self.other, products=[self.product], status='delivered')

    def detail(self):
        response = APIClient().get(f'/api/v1/products/{self.product.slug}/')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def reviews_url(self):
        return f'/api/v1/products/{self.product.slug}/reviews/'

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

    def test_official_badge_and_warranty_round_trip(self):
        self.assertFalse(self.detail()['is_official'])
        self.assertEqual(self.detail()['warranty_period'], '')

        self.api.force_authenticate(self.staff)
        updated = self.api.patch(
            f'/api/v1/products/admin/products/{self.product.id}/',
            {'is_official': True, 'warranty_period': '  1 year  '},
            format='json',
        )
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertTrue(updated.json()['is_official'])
        self.assertEqual(updated.json()['warranty_period'], '1 year')

        public = self.detail()
        self.assertTrue(public['is_official'])
        self.assertEqual(public['warranty_period'], '1 year')

        cleared = self.api.patch(
            f'/api/v1/products/admin/products/{self.product.id}/',
            {'is_official': False, 'warranty_period': '   '},
            format='json',
        )
        self.assertEqual(cleared.status_code, 200, cleared.content)
        self.assertFalse(self.detail()['is_official'])
        self.assertEqual(self.detail()['warranty_period'], '')

    def test_official_badge_style_is_saved_for_the_store(self):
        public = APIClient().get('/api/v1/products/settings/public/')
        self.assertEqual(public.status_code, 200, public.content)
        self.assertEqual(public.json()['official_badge_size'], 'medium')
        self.assertEqual(public.json()['official_badge_color'], '#2864E8')
        self.assertEqual(public.json()['official_badge_position'], 'top-left')

        self.api.force_authenticate(self.staff)
        rejected = self.api.patch(
            '/api/v1/products/admin/settings/',
            {'official_badge_color': 'blue'},
            format='json',
        )
        self.assertEqual(rejected.status_code, 400, rejected.content)

        saved = self.api.patch(
            '/api/v1/products/admin/settings/',
            {
                'official_badge_size': 'large',
                'official_badge_color': '#e11d48',
                'official_badge_position': 'bottom-right',
            },
            format='json',
        )
        self.assertEqual(saved.status_code, 200, saved.content)
        self.assertEqual(saved.json()['official_badge_size'], 'large')
        self.assertEqual(saved.json()['official_badge_color'], '#E11D48')
        self.assertEqual(saved.json()['official_badge_position'], 'bottom-right')

        again = APIClient().get('/api/v1/products/settings/public/')
        self.assertEqual(again.json()['official_badge_position'], 'bottom-right')
        self.api.patch(
            '/api/v1/products/admin/settings/',
            {
                'official_badge_size': 'medium',
                'official_badge_color': '#2864E8',
                'official_badge_position': 'top-left',
            },
            format='json',
        )

    def test_partial_specification_is_rejected(self):
        self.api.force_authenticate(self.staff)
        response = self.api.patch(
            f'/api/v1/products/admin/products/{self.product.id}/',
            {'specifications': [{'name': 'Brand', 'value': ''}]},
            format='json',
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(ProductSpecification.objects.filter(product=self.product).count(), 0)

    def test_ineligible_buyer_cannot_review(self):
        pending_user = make_user(first_name='Pending', last_name='Buyer')
        make_order(user=pending_user, products=[self.product], status='processing')
        self.api.force_authenticate(pending_user)
        denied = self.api.post(
            self.reviews_url(),
            {'rating': 5, 'comment': 'Too early'},
            format='json',
        )
        self.assertEqual(denied.status_code, 403, denied.content)
        self.assertEqual(denied.json()['code'], 'not_eligible')
        self.assertEqual(ProductReview.objects.filter(product=self.product).count(), 0)

        listing = self.api.get(self.reviews_url())
        self.assertEqual(listing.status_code, 200, listing.content)
        self.assertFalse(listing.json()['can_review'])

    def test_one_review_per_customer_updates_the_average(self):
        self.api.force_authenticate(self.customer)
        eligible = self.api.get(self.reviews_url())
        self.assertTrue(eligible.json()['can_review'])

        created = self.api.post(
            self.reviews_url(),
            {'rating': 5, 'comment': 'Clear sound'},
            format='json',
        )
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.json()['author'], 'Nusrat Jahan')
        self.assertEqual(created.json()['images'], [])

        updated = self.api.post(
            self.reviews_url(),
            {'rating': 4, 'comment': 'Still good'},
            format='json',
        )
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertEqual(ProductReview.objects.filter(product=self.product).count(), 1)
        self.assertEqual(updated.json()['comment'], 'Still good')

        self.api.force_authenticate(self.other)
        second = self.api.post(
            self.reviews_url(),
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

        public = APIClient().get(self.reviews_url())
        self.assertEqual(public.status_code, 200, public.content)
        data = public.json()
        self.assertIsNone(data['mine'])
        self.assertFalse(data['can_review'])
        self.assertEqual(data['count'], 2)
        self.assertEqual(data['filtered_count'], 2)
        self.assertEqual(len(data['results']), 2)
        self.assertEqual(data['rating_breakdown'], {'1': 0, '2': 1, '3': 0, '4': 1, '5': 0})

    def test_review_photos_filters_and_six_images_rejected(self):
        self.api.force_authenticate(self.customer)
        created = self.api.post(
            self.reviews_url(),
            {
                'rating': 5,
                'comment': 'Looks great',
                'images': [_png('a.png'), _png('b.png', (10, 200, 80))],
            },
            format='multipart',
        )
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(len(created.json()['images']), 2)
        self.assertEqual(ProductReviewImage.objects.filter(review_id=created.json()['id']).count(), 2)
        self.assertTrue(created.json()['images'][0]['image'])

        self.api.force_authenticate(self.other)
        self.api.post(
            self.reviews_url(),
            {'rating': 3, 'comment': 'No photos'},
            format='json',
        )

        filtered = APIClient().get(self.reviews_url(), {'with_photos': '1', 'sort': 'highest'})
        self.assertEqual(filtered.status_code, 200, filtered.content)
        body = filtered.json()
        self.assertEqual(body['count'], 2)
        self.assertEqual(body['filtered_count'], 1)
        self.assertEqual(len(body['results']), 1)
        self.assertEqual(body['results'][0]['rating'], 5)
        self.assertEqual(len(body['results'][0]['images']), 2)

        by_star = APIClient().get(self.reviews_url(), {'rating': '3'})
        self.assertEqual(by_star.json()['filtered_count'], 1)
        self.assertEqual(by_star.json()['results'][0]['rating'], 3)

        # The app sends gallery photos as application/octet-stream even when the bytes are JPEG.
        untyped = self.api.post(
            self.reviews_url(),
            {
                'rating': 5,
                'comment': 'Received it in two days and it is authentic.',
                'images': [_jpeg('scaled_100.jpg', 'application/octet-stream')],
            },
            format='multipart',
        )
        self.assertEqual(untyped.status_code, 200, untyped.content)
        self.assertEqual(len(untyped.json()['images']), 1)

        not_an_image = self.api.post(
            self.reviews_url(),
            {
                'rating': 5,
                'comment': 'This file is not a photo',
                'images': [SimpleUploadedFile('notes.txt', b'not-a-photo', content_type='text/plain')],
            },
            format='multipart',
        )
        self.assertEqual(not_an_image.status_code, 400, not_an_image.content)

        too_many = self.api.post(
            self.reviews_url(),
            {
                'rating': 4,
                'comment': 'Too many pics',
                'images': [_png(f'x{i}.png') for i in range(6)],
            },
            format='multipart',
        )
        self.assertEqual(too_many.status_code, 400, too_many.content)

    def test_guests_cannot_post_and_only_the_author_can_delete(self):
        guest = self.api.post(
            self.reviews_url(),
            {'rating': 5, 'comment': 'Nice'},
            format='json',
        )
        self.assertEqual(guest.status_code, 401, guest.content)

        self.api.force_authenticate(self.customer)
        saved = self.api.post(
            self.reviews_url(),
            {'rating': 5, 'comment': 'Nice'},
            format='json',
        )
        self.assertEqual(saved.status_code, 201, saved.content)

        blank = self.api.post(
            self.reviews_url(),
            {'rating': 5, 'comment': '   '},
            format='json',
        )
        self.assertEqual(blank.status_code, 400, blank.content)

        self.api.force_authenticate(self.other)
        denied = self.api.delete(self.reviews_url())
        self.assertEqual(denied.status_code, 404, denied.content)
        self.assertEqual(ProductReview.objects.filter(product=self.product).count(), 1)

        self.api.force_authenticate(self.customer)
        gone = self.api.delete(self.reviews_url())
        self.assertEqual(gone.status_code, 204, gone.content)
        self.assertEqual(self.detail()['review_count'], 0)
        self.assertIsNone(self.detail()['rating_average'])
