from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import EmailVerificationToken
from apps.orders.tests.factories import ShopTestCase, make_user


class VerifyEmailTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.user = make_user(is_verified=False)
        self.otp = EmailVerificationToken.objects.create(
            user=self.user,
            otp_code='123456',
            expires_at=timezone.now() + timedelta(minutes=10),
        )

    def test_verify_returns_tokens_and_is_idempotent(self):
        first = self.api.post('/api/v1/auth/verify-email/', {
            'email': self.user.email,
            'otp_code': '123456',
        }, format='json')
        self.assertEqual(first.status_code, 200, first.content)
        body = first.json()
        self.assertTrue(body['access'])
        self.assertTrue(body['refresh'])
        self.assertTrue(body['user']['is_verified'])

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_verified)
        self.otp.refresh_from_db()
        self.assertTrue(self.otp.is_used)

        # Client retry after a success (or a timed-out response) still signs in.
        second = self.api.post('/api/v1/auth/verify-email/', {
            'email': self.user.email,
            'otp_code': '123456',
        }, format='json')
        self.assertEqual(second.status_code, 200, second.content)
        self.assertTrue(second.json()['access'])
        self.assertIn('already verified', second.json()['message'].lower())
