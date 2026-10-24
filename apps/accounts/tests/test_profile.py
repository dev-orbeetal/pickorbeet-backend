import os
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from apps.orders.tests.factories import ShopTestCase, make_user

PROFILE = '/api/v1/auth/profile/'


def image_file(fmt='PNG', name='avatar.png', color='red'):
    content_type = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'GIF': 'image/gif', 'WEBP': 'image/webp'}[fmt]
    buffer = BytesIO()
    Image.new('RGB', (12, 12), color).save(buffer, format=fmt)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)


class ProfileApiTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user(first_name='Rahik', last_name='Forman', phone='01712345678')
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_guest_cannot_read_or_change_a_profile(self):
        guest = APIClient()
        self.assertEqual(guest.get(PROFILE).status_code, 401)
        self.assertEqual(guest.patch(PROFILE, {'first_name': 'Other'}).status_code, 401)

    def test_updates_contact_details_and_leaves_email_unchanged(self):
        response = self.api.patch(PROFILE, {
            'first_name': '  Rahik Ibn ',
            'last_name': 'Forman',
            'phone': '+880 1712-345678',
            'address': 'House 4, Road 12',
            'city': 'Dhaka',
            'postal_code': '1207',
            'email': 'someone-else@example.com',
            'role': 'super_admin',
        }, format='json')

        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Rahik Ibn')
        self.assertEqual(self.user.phone, '01712345678')
        self.assertEqual(self.user.address, 'House 4, Road 12')
        self.assertEqual(self.user.city, 'Dhaka')
        self.assertNotEqual(self.user.email, 'someone-else@example.com')
        self.assertEqual(self.user.role, 'customer')
        self.assertIn('avatar', response.data)
        self.assertIsNone(response.data['avatar'])

    def test_rejects_a_blank_name_and_a_landline(self):
        blank = self.api.patch(PROFILE, {'first_name': '   '}, format='json')
        self.assertEqual(blank.status_code, 400)
        self.assertIn('first_name', blank.data)

        phone = self.api.patch(PROFILE, {'phone': '021234567'}, format='json')
        self.assertEqual(phone.status_code, 400)
        self.assertIn('phone', phone.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, '01712345678')

    def test_uploads_replaces_and_removes_a_photo(self):
        uploaded = self.api.patch(PROFILE, {'avatar': image_file()}, format='multipart')
        self.assertEqual(uploaded.status_code, 200, uploaded.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar.name.endswith('.png'))
        self.assertTrue(uploaded.data['avatar'].startswith('http'))
        self.assertIn('/media/avatars/', uploaded.data['avatar'])
        first_path = self.user.avatar.path
        self.assertTrue(os.path.exists(first_path))

        replaced = self.api.patch(PROFILE, {'avatar': image_file(color='green')}, format='multipart')
        self.assertEqual(replaced.status_code, 200, replaced.data)
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.avatar.path, first_path)
        self.assertFalse(os.path.exists(first_path))
        self.assertTrue(os.path.exists(self.user.avatar.path))

        kept = self.api.patch(PROFILE, {'city': 'Chattogram'}, format='json')
        self.assertEqual(kept.status_code, 200, kept.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar)
        self.assertEqual(self.user.city, 'Chattogram')

        cleared = self.api.patch(PROFILE, {'clear_avatar': True}, format='json')
        self.assertEqual(cleared.status_code, 200, cleared.data)
        self.assertIsNone(cleared.data['avatar'])
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    def test_rejects_the_wrong_kind_and_an_oversized_photo(self):
        text = SimpleUploadedFile('notes.png', b'not an image', content_type='image/png')
        rejected = self.api.patch(PROFILE, {'avatar': text}, format='multipart')
        self.assertEqual(rejected.status_code, 400)
        self.assertIn('avatar', rejected.data)

        gif = self.api.patch(PROFILE, {'avatar': image_file(fmt='GIF', name='avatar.gif')}, format='multipart')
        self.assertEqual(gif.status_code, 400)
        self.assertIn('avatar', gif.data)

        huge = SimpleUploadedFile('big.jpg', b'\xff\xd8\xff' + b'0' * (2 * 1024 * 1024), content_type='image/jpeg')
        oversized = self.api.patch(PROFILE, {'avatar': huge}, format='multipart')
        self.assertEqual(oversized.status_code, 400)
        self.assertIn('2 MB', str(oversized.data['avatar']))
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    def test_accepts_jpeg_and_webp(self):
        jpeg = self.api.patch(PROFILE, {'avatar': image_file(fmt='JPEG', name='avatar.jpg')}, format='multipart')
        self.assertEqual(jpeg.status_code, 200, jpeg.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar.name.endswith('.jpg'))

        webp = self.api.patch(PROFILE, {'avatar': image_file(fmt='WEBP', name='avatar.webp')}, format='multipart')
        self.assertEqual(webp.status_code, 200, webp.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar.name.endswith('.webp'))
