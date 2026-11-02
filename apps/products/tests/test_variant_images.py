import io

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from apps.orders.tests.factories import ShopTestCase, make_product, make_user
from apps.products.models import ProductImage


def png_file(name='swatch.png', color=(255, 122, 26)):
    buffer = io.BytesIO()
    Image.new('RGB', (8, 8), color).save(buffer, format='PNG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/png')


class VariantImageTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.product = make_product(name='Color Tee')
        self.product.sku = 'TEE-CLR-1'
        self.product.save(update_fields=['sku'])
        self.staff = make_user(role='seller', is_staff=True)
        self.api.force_authenticate(self.staff)

    def test_upload_image_for_one_variant(self):
        setup = self.api.put(
            f'/api/v1/products/admin/products/{self.product.id}/variant-setup/',
            {
                'option_groups': [{
                    'name': 'Color',
                    'kind': 'swatch',
                    'values': [
                        {'label': 'Orange', 'color_hex': '#FF7A1A'},
                        {'label': 'Black', 'color_hex': '#171717'},
                    ],
                }],
                'variants': [
                    {
                        'barcode': 'ZZV-ORG-9',
                        'price': None,
                        'stock_quantity': 2,
                        'low_stock_threshold': 1,
                        'is_active': True,
                        'selections': [{'name': 'Color', 'label': 'Orange'}],
                    },
                    {
                        'barcode': 'ZZV-BLK-9',
                        'price': None,
                        'stock_quantity': 2,
                        'low_stock_threshold': 1,
                        'is_active': True,
                        'selections': [{'name': 'Color', 'label': 'Black'}],
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(setup.status_code, 200, setup.content)
        orange = next(row for row in setup.json()['variants'] if row['color'] == 'Orange')

        upload = self.api.post(
            f'/api/v1/products/admin/products/{self.product.id}/images/',
            {
                'image': png_file(),
                'is_primary': 'false',
                'variant': str(orange['id']),
            },
            format='multipart',
        )
        self.assertEqual(upload.status_code, 201, upload.content)
        body = upload.json()
        self.assertEqual(str(body['variant']), str(orange['id']))

        image = ProductImage.objects.get(pk=body['id'])
        self.assertEqual(str(image.variant_id), str(orange['id']))

        public = APIClient().get(f'/api/v1/products/{self.product.slug}/')
        self.assertEqual(public.status_code, 200, public.content)
        images = public.json()['images']
        self.assertEqual(len(images), 1)
        self.assertEqual(str(images[0]['variant']), str(orange['id']))
