from rest_framework.test import APIClient

from apps.orders.tests.factories import ShopTestCase, make_product, make_user
from apps.products.models import ProductVideo
from apps.products.youtube import extract_youtube_id


class YouTubeIdTests(ShopTestCase):
    def test_extracts_common_url_shapes(self):
        self.assertEqual(extract_youtube_id('https://www.youtube.com/watch?v=dQw4w9WgXcQ'), 'dQw4w9WgXcQ')
        self.assertEqual(extract_youtube_id('https://youtu.be/dQw4w9WgXcQ'), 'dQw4w9WgXcQ')
        self.assertEqual(extract_youtube_id('https://www.youtube.com/embed/dQw4w9WgXcQ'), 'dQw4w9WgXcQ')
        self.assertEqual(extract_youtube_id('https://www.youtube.com/shorts/dQw4w9WgXcQ'), 'dQw4w9WgXcQ')
        self.assertIsNone(extract_youtube_id('https://example.com/watch?v=dQw4w9WgXcQ'))


class ProductVideoApiTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.product = make_product(name='Demo Cam')
        self.staff = make_user(role='seller', is_staff=True)
        self.api.force_authenticate(self.staff)

    def test_create_video_and_expose_on_public_detail(self):
        create = self.api.post(
            f'/api/v1/products/admin/products/{self.product.id}/videos/',
            {
                'youtube_url': 'https://youtu.be/dQw4w9WgXcQ',
                'title': 'Unboxing',
                'is_primary': True,
            },
            format='json',
        )
        self.assertEqual(create.status_code, 201, create.content)
        body = create.json()
        self.assertEqual(body['youtube_id'], 'dQw4w9WgXcQ')
        self.assertIsNone(body['variant'])

        video = ProductVideo.objects.get(pk=body['id'])
        self.assertEqual(video.youtube_id, 'dQw4w9WgXcQ')

        public = APIClient().get(f'/api/v1/products/{self.product.slug}/')
        self.assertEqual(public.status_code, 200, public.content)
        videos = public.json()['videos']
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0]['youtube_id'], 'dQw4w9WgXcQ')
        self.assertEqual(videos[0]['title'], 'Unboxing')

    def test_rejects_invalid_youtube_url(self):
        bad = self.api.post(
            f'/api/v1/products/admin/products/{self.product.id}/videos/',
            {'youtube_url': 'https://vimeo.com/123'},
            format='json',
        )
        self.assertEqual(bad.status_code, 400)

    def test_delete_video(self):
        video = ProductVideo.objects.create(
            product=self.product,
            youtube_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            youtube_id='dQw4w9WgXcQ',
        )
        deleted = self.api.delete(f'/api/v1/products/admin/videos/{video.id}/')
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(ProductVideo.objects.filter(pk=video.id).exists())
