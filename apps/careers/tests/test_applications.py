import os
import shutil
import tempfile
from io import BytesIO
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.careers.models import CareerApplication
from apps.careers.views import PublicCareerApplyView
from apps.orders.tests.factories import make_user


def _png(name='photo.png'):
    buf = BytesIO()
    Image.new('RGB', (32, 32), (40, 120, 200)).save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


def _pdf(name='cv.pdf', extra=b''):
    body = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n' + extra
    return SimpleUploadedFile(name, body, content_type='application/pdf')


def _application(**overrides):
    payload = {
        'name': 'Nusrat Jahan',
        'email': 'Nusrat@Example.com',
        'phone': '+8801712345678',
        'university': 'University of Dhaka',
        'session': '2022-23',
        'department': 'Computer Science and Engineering',
        'student_id': '2021-1-60-123',
        'cv': _pdf(),
        'picture': _png(),
    }
    payload.update(overrides)
    return payload


class CareerApplicationTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.override = override_settings(
            PRIVATE_MEDIA_ROOT=self.media,
            EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        )
        self.override.enable()
        cache.clear()
        self.api = APIClient()
        self.staff = make_user(role='seller')
        self.customer = make_user()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def submit(self, **overrides):
        return self.api.post('/api/v1/careers/apply/', _application(**overrides), format='multipart')

    def test_valid_submit_stores_a_private_application_and_emails_support(self):
        response = self.submit()
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(
            response.json(),
            {'message': 'Your application has been received. We will be in touch.'},
        )
        self.assertNotIn(b'private_media', response.content)
        self.assertNotIn(b'.pdf', response.content)

        application = CareerApplication.objects.get()
        self.assertEqual(application.email, 'nusrat@example.com')
        self.assertEqual(application.phone, '01712345678')
        self.assertEqual(application.student_id, '2021-1-60-123')
        self.assertEqual(application.status, 'new')
        self.assertTrue(os.path.isfile(application.cv.path))
        self.assertTrue(application.cv.path.startswith(os.path.abspath(self.media)))
        with self.assertRaises(ValueError):
            application.cv.url

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Nusrat Jahan', mail.outbox[0].subject)
        self.assertIn('University of Dhaka', mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].attachments, [])

    def test_mail_failure_still_accepts_the_application(self):
        with patch('apps.careers.emails.send_branded', side_effect=OSError('smtp down')):
            response = self.submit()
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(CareerApplication.objects.count(), 1)

    def test_rejects_a_bad_phone_a_non_pdf_and_an_oversized_cv(self):
        phone = self.submit(phone='12345')
        self.assertEqual(phone.status_code, 400)
        self.assertIn('phone', phone.json())

        word = self.submit(cv=SimpleUploadedFile('cv.docx', b'PK\x03\x04not-a-pdf', content_type='application/pdf'))
        self.assertEqual(word.status_code, 400)
        self.assertIn('cv', word.json())

        huge = self.submit(cv=_pdf(extra=b'0' * (5 * 1024 * 1024)))
        self.assertEqual(huge.status_code, 400)
        self.assertIn('cv', huge.json())
        self.assertEqual(CareerApplication.objects.count(), 0)

    def test_rejects_a_short_student_id_and_json_submissions(self):
        short = self.submit(student_id='A1')
        self.assertEqual(short.status_code, 400)
        self.assertIn('student_id', short.json())

        json_post = self.api.post('/api/v1/careers/apply/', {'name': 'Nusrat'}, format='json')
        self.assertEqual(json_post.status_code, 415)

    def test_apply_view_is_throttled(self):
        self.assertIn(ScopedRateThrottle, PublicCareerApplyView.throttle_classes)
        self.assertEqual(PublicCareerApplyView.throttle_scope, 'career_apply')

    def test_anonymous_and_customers_cannot_review(self):
        self.submit()
        application = CareerApplication.objects.get()

        anonymous = self.api.get('/api/v1/careers/admin/applications/')
        self.assertEqual(anonymous.status_code, 401)

        self.api.force_authenticate(self.customer)
        forbidden = self.api.get('/api/v1/careers/admin/applications/')
        self.assertEqual(forbidden.status_code, 403)
        hidden = self.api.get(f'/api/v1/careers/admin/applications/{application.pk}/cv/')
        self.assertEqual(hidden.status_code, 403)

    def test_staff_can_list_open_download_and_update_without_file_urls(self):
        self.submit()
        application = CareerApplication.objects.get()
        self.api.force_authenticate(self.staff)

        listed = self.api.get('/api/v1/careers/admin/applications/', {'search': 'Dhaka'})
        self.assertEqual(listed.status_code, 200, listed.content)
        row = listed.json()['results'][0]
        self.assertEqual(row['email'], 'nusrat@example.com')
        self.assertTrue(row['has_cv'])
        self.assertTrue(row['has_picture'])
        self.assertNotIn('cv', row)
        self.assertNotIn('picture', row)
        self.assertNotIn('careers/', listed.content.decode())

        opened = self.api.get(f'/api/v1/careers/admin/applications/{application.pk}/')
        self.assertEqual(opened.status_code, 200, opened.content)
        self.assertEqual(opened.json()['status'], 'reviewing')
        application.refresh_from_db()
        self.assertEqual(application.status, 'reviewing')

        cv = self.api.get(f'/api/v1/careers/admin/applications/{application.pk}/cv/')
        self.assertEqual(cv.status_code, 200)
        self.assertTrue(b''.join(cv.streaming_content).startswith(b'%PDF'))
        self.assertEqual(cv['Cache-Control'], 'private, no-store')

        photo = self.api.get(f'/api/v1/careers/admin/applications/{application.pk}/picture/')
        self.assertEqual(photo.status_code, 200)
        self.assertEqual(photo['Content-Type'], 'image/png')

        updated = self.api.patch(
            f'/api/v1/careers/admin/applications/{application.pk}/',
            {'name': 'Someone Else', 'status': 'shortlisted', 'admin_notes': 'Strong project work'},
            format='json',
        )
        self.assertEqual(updated.status_code, 200, updated.content)
        application.refresh_from_db()
        self.assertEqual(application.name, 'Nusrat Jahan')
        self.assertEqual(application.status, 'shortlisted')
        self.assertEqual(application.admin_notes, 'Strong project work')

    def test_deleting_an_application_removes_its_files(self):
        self.submit()
        application = CareerApplication.objects.get()
        cv_path = application.cv.path
        picture_path = application.picture.path
        self.assertTrue(os.path.isfile(cv_path))

        self.api.force_authenticate(self.staff)
        deleted = self.api.delete(f'/api/v1/careers/admin/applications/{application.pk}/')
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(CareerApplication.objects.exists())
        self.assertFalse(os.path.isfile(cv_path))
        self.assertFalse(os.path.isfile(picture_path))
