from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import AuthSession, LoginEvent, PasswordResetToken, SecurityCode
from apps.accounts.security import generate_code
from apps.orders.tests.factories import ShopTestCase, make_user

LOGIN = '/api/v1/auth/login/'
VERIFY = '/api/v1/auth/2fa/verify/'
RESEND = '/api/v1/auth/2fa/resend/'
ENABLE = '/api/v1/auth/2fa/enable/'
ENABLE_CONFIRM = '/api/v1/auth/2fa/enable/confirm/'
DISABLE = '/api/v1/auth/2fa/disable/'
SESSIONS = '/api/v1/auth/sessions/'
REVOKE_OTHERS = '/api/v1/auth/sessions/revoke-others/'
ACTIVITY = '/api/v1/auth/login-activity/'
RECOVERY = '/api/v1/auth/recovery-email/'
RECOVERY_CONFIRM = '/api/v1/auth/recovery-email/confirm/'
PROFILE = '/api/v1/auth/profile/'
CHANGE = '/api/v1/auth/change-password/'
REFRESH = '/api/v1/auth/token/refresh/'
FORGOT = '/api/v1/auth/forgot-password/'
GOOGLE = '/api/v1/auth/google/'
PASSWORD = 'Str0ng-pass!'
NEW_PASSWORD = 'N3w-pass-word!'


def device_headers(device_id='phone-1', name='Pixel 8'):
    return {
        'HTTP_X_DEVICE_ID': device_id,
        'HTTP_X_DEVICE_NAME': name,
        'HTTP_X_CLIENT_PLATFORM': 'app',
    }


class SecurityApiTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.user = make_user(email='rahik@example.com', is_verified=True)
        self.codes = patch('apps.accounts.security.generate_code', return_value='654321')
        self.codes.start()
        self.addCleanup(self.codes.stop)

    def login(self, email=None, password=PASSWORD, **headers):
        return self.api.post(LOGIN, {
            'email': email or self.user.email,
            'password': password,
        }, format='json', **headers)

    def bearer(self, access):
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

    def test_login_without_2fa_returns_tokens_and_records_the_device(self):
        response = self.login(**device_headers())

        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn('requires_2fa', response.data)
        self.assertTrue(response.data['access'])
        self.assertEqual(response.data['user']['email'], self.user.email)
        session = AuthSession.objects.get(user=self.user)
        self.assertEqual(session.device_name, 'Pixel 8')
        self.assertEqual(session.device_id, 'phone-1')
        self.assertIsNone(session.revoked_at)
        event = LoginEvent.objects.get(user=self.user)
        self.assertTrue(event.success)
        self.assertEqual(event.method, LoginEvent.PASSWORD)

        self.bearer(response.data['access'])
        profile = self.api.get(PROFILE)
        self.assertEqual(profile.status_code, 200, profile.data)
        self.assertFalse(profile.data['two_factor_enabled'])
        self.assertTrue(profile.data['has_password'])
        self.assertIsNone(profile.data['recovery_email'])

    def test_wrong_password_is_recorded_and_does_not_start_2fa(self):
        self.user.two_factor_enabled = True
        self.user.save(update_fields=['two_factor_enabled'])
        response = self.login(password='not-the-password')

        self.assertEqual(response.status_code, 401)
        self.assertNotIn('requires_2fa', response.data)
        event = LoginEvent.objects.get()
        self.assertFalse(event.success)
        self.assertEqual(AuthSession.objects.count(), 0)

    def test_2fa_login_sends_a_code_and_verify_opens_a_session(self):
        self.user.two_factor_enabled = True
        self.user.save(update_fields=['two_factor_enabled'])
        mail.outbox.clear()

        challenged = self.login(**device_headers('phone-2', 'iPhone'))
        self.assertEqual(challenged.status_code, 200, challenged.data)
        self.assertTrue(challenged.data['requires_2fa'])
        self.assertNotIn('access', challenged.data)
        self.assertEqual(AuthSession.objects.count(), 0)
        self.assertEqual(mail.outbox[-1].to, [self.user.email])
        self.assertIn('654321', mail.outbox[-1].body)

        wrong = self.api.post(VERIFY, {
            'challenge': challenged.data['challenge'],
            'otp_code': '000000',
        }, format='json')
        self.assertEqual(wrong.status_code, 400)

        verified = self.api.post(VERIFY, {
            'challenge': challenged.data['challenge'],
            'otp_code': '654321',
        }, format='json', **device_headers('phone-2', 'iPhone'))
        self.assertEqual(verified.status_code, 200, verified.data)
        self.assertTrue(verified.data['access'])
        session = AuthSession.objects.get()
        self.assertEqual(session.device_id, 'phone-2')
        self.assertTrue(LoginEvent.objects.filter(method=LoginEvent.TWO_FACTOR, success=True).exists())
        self.assertTrue(LoginEvent.objects.filter(method=LoginEvent.TWO_FACTOR, success=False).exists())

    def test_code_locks_after_five_wrong_attempts(self):
        self.user.two_factor_enabled = True
        self.user.save(update_fields=['two_factor_enabled'])
        challenged = self.login()
        challenge = challenged.data['challenge']
        for _ in range(5):
            self.api.post(VERIFY, {'challenge': challenge, 'otp_code': '000000'}, format='json')
        locked = self.api.post(VERIFY, {'challenge': challenge, 'otp_code': '654321'}, format='json')
        self.assertEqual(locked.status_code, 400)
        self.assertIn('Too many', locked.data['detail'])

    def test_resend_waits_and_then_sends_again(self):
        self.user.two_factor_enabled = True
        self.user.save(update_fields=['two_factor_enabled'])
        challenged = self.login()
        early = self.api.post(RESEND, {'challenge': challenged.data['challenge']}, format='json')
        self.assertEqual(early.status_code, 429)

        SecurityCode.objects.update(last_sent_at=timezone.now() - timedelta(seconds=61))
        sent = self.api.post(RESEND, {'challenge': challenged.data['challenge']}, format='json')
        self.assertEqual(sent.status_code, 200, sent.data)

    def test_enable_requires_a_verified_email_and_a_code(self):
        unverified = make_user(is_verified=False)
        self.api.force_authenticate(unverified)
        blocked = self.api.post(ENABLE, {}, format='json')
        self.assertEqual(blocked.status_code, 400)

        self.api.force_authenticate(self.user)
        started = self.api.post(ENABLE, {}, format='json')
        self.assertEqual(started.status_code, 200, started.data)
        self.assertIn('challenge', started.data)
        self.user.refresh_from_db()
        self.assertFalse(self.user.two_factor_enabled)

        confirmed = self.api.post(ENABLE_CONFIRM, {
            'challenge': started.data['challenge'],
            'otp_code': '654321',
        }, format='json')
        self.assertEqual(confirmed.status_code, 200, confirmed.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.two_factor_enabled)

        self.api.force_authenticate(self.user)
        disabled = self.api.post(DISABLE, {'password': PASSWORD}, format='json')
        self.assertEqual(disabled.status_code, 200, disabled.data)
        self.user.refresh_from_db()
        self.assertFalse(self.user.two_factor_enabled)

    def test_google_only_account_turns_2fa_off_with_a_code(self):
        self.user.set_unusable_password()
        self.user.two_factor_enabled = True
        self.user.save()
        self.api.force_authenticate(self.user)

        started = self.api.post(DISABLE, {}, format='json')
        self.assertEqual(started.status_code, 200, started.data)
        self.assertTrue(started.data['requires_code'])
        self.user.refresh_from_db()
        self.assertTrue(self.user.two_factor_enabled)

        finished = self.api.post(DISABLE, {
            'challenge': started.data['challenge'],
            'otp_code': '654321',
        }, format='json')
        self.assertEqual(finished.status_code, 200, finished.data)
        self.user.refresh_from_db()
        self.assertFalse(self.user.two_factor_enabled)

    def test_sessions_mark_this_device_and_revoke_the_other(self):
        first = self.login(**device_headers('phone-a', 'Pixel'))
        second = self.login(**device_headers('phone-b', 'iPhone'))
        self.bearer(second.data['access'])

        listed = self.api.get(SESSIONS)
        self.assertEqual(listed.status_code, 200, listed.data)
        current = [row for row in listed.data['results'] if row['current']]
        other = [row for row in listed.data['results'] if not row['current']]
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]['device_name'], 'iPhone')
        self.assertEqual(other[0]['device_name'], 'Pixel')

        refused = self.api.post(f"/api/v1/auth/sessions/{current[0]['id']}/revoke/", {}, format='json')
        self.assertEqual(refused.status_code, 400)

        revoked = self.api.post(f"/api/v1/auth/sessions/{other[0]['id']}/revoke/", {}, format='json')
        self.assertEqual(revoked.status_code, 200, revoked.data)

        self.bearer(first.data['access'])
        self.assertEqual(self.api.get(PROFILE).status_code, 401)
        stale = self.api.post(REFRESH, {'refresh': first.data['refresh']}, format='json')
        self.assertEqual(stale.status_code, 401)

        self.bearer(second.data['access'])
        self.assertEqual(self.api.get(PROFILE).status_code, 200)

    def test_revoke_others_keeps_the_current_session(self):
        self.login(**device_headers('phone-a', 'Pixel'))
        current = self.login(**device_headers('phone-b', 'iPhone'))
        self.bearer(current.data['access'])
        response = self.api.post(REVOKE_OTHERS, {}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(AuthSession.objects.filter(revoked_at__isnull=True).count(), 1)
        self.assertEqual(self.api.get(PROFILE).status_code, 200)

    def test_refresh_rotates_the_token_and_keeps_this_session(self):
        signed_in = self.login(**device_headers())
        refreshed = self.api.post(REFRESH, {'refresh': signed_in.data['refresh']}, format='json')
        self.assertEqual(refreshed.status_code, 200, refreshed.data)
        self.assertNotEqual(refreshed.data['refresh'], signed_in.data['refresh'])
        self.assertEqual(AuthSession.objects.filter(revoked_at__isnull=True).count(), 1)

        self.bearer(refreshed.data['access'])
        self.assertEqual(self.api.get(PROFILE).status_code, 200)
        reused = self.api.post(REFRESH, {'refresh': signed_in.data['refresh']}, format='json')
        self.assertEqual(reused.status_code, 401)
        access = str(RefreshToken.for_user(self.user).access_token)
        self.bearer(access)
        self.assertEqual(self.api.get(PROFILE).status_code, 200)

    def test_login_activity_lists_success_and_failure(self):
        self.login(password='nope')
        signed_in = self.login(**device_headers())
        self.bearer(signed_in.data['access'])
        activity = self.api.get(ACTIVITY)
        self.assertEqual(activity.status_code, 200, activity.data)
        methods = [(row['success'], row['device_name']) for row in activity.data['results']]
        self.assertIn((True, 'Pixel 8'), methods)
        self.assertIn((False, 'Unknown device'), methods)

    def test_password_change_keeps_this_device_and_signs_out_the_other(self):
        other = self.login(**device_headers('phone-a', 'Pixel'))
        current = self.login(**device_headers('phone-b', 'iPhone'))
        self.bearer(current.data['access'])
        changed = self.api.post(CHANGE, {
            'old_password': PASSWORD,
            'new_password': NEW_PASSWORD,
            'new_password_confirm': NEW_PASSWORD,
        }, format='json')
        self.assertEqual(changed.status_code, 200, changed.data)
        self.assertEqual(self.api.get(PROFILE).status_code, 200)

        self.bearer(other.data['access'])
        self.assertEqual(self.api.get(PROFILE).status_code, 401)
        again = self.login(password=NEW_PASSWORD, **device_headers('phone-c', 'iPad'))
        self.assertEqual(again.status_code, 200, again.data)

    def test_google_only_account_can_set_a_password(self):
        self.user.set_unusable_password()
        self.user.save()
        signed_in = self.api.post(LOGIN, {'email': self.user.email, 'password': PASSWORD}, format='json')
        self.assertEqual(signed_in.status_code, 401)

        access = str(RefreshToken.for_user(self.user).access_token)
        self.bearer(access)
        response = self.api.post(CHANGE, {
            'new_password': NEW_PASSWORD,
            'new_password_confirm': NEW_PASSWORD,
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))

    def test_recovery_email_is_verified_and_can_reset_the_password(self):
        signed_in = self.login()
        self.bearer(signed_in.data['access'])
        same = self.api.post(RECOVERY, {'email': self.user.email}, format='json')
        self.assertEqual(same.status_code, 400)

        mail.outbox.clear()
        started = self.api.post(RECOVERY, {'email': 'backup@example.com'}, format='json')
        self.assertEqual(started.status_code, 200, started.data)
        self.assertEqual(mail.outbox[-1].to, ['backup@example.com'])
        self.user.refresh_from_db()
        self.assertIsNone(self.user.recovery_email)

        confirmed = self.api.post(RECOVERY_CONFIRM, {
            'challenge': started.data['challenge'],
            'otp_code': '654321',
        }, format='json')
        self.assertEqual(confirmed.status_code, 200, confirmed.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.recovery_email, 'backup@example.com')
        self.assertTrue(self.user.recovery_email_verified)

        mail.outbox.clear()
        guest = APIClient()
        forgot = guest.post(FORGOT, {'email': 'backup@example.com'}, format='json')
        self.assertEqual(forgot.status_code, 200)
        self.assertEqual(mail.outbox[-1].to, ['backup@example.com'])
        self.assertEqual(PasswordResetToken.objects.filter(user=self.user, is_used=False).count(), 1)

        removed = self.api.delete(RECOVERY)
        self.assertEqual(removed.status_code, 200, removed.data)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.recovery_email)
        self.assertFalse(self.user.recovery_email_verified)

    @patch('apps.accounts.views._google_id_info')
    def test_google_sign_in_with_2fa_does_not_issue_tokens(self, info):
        self.user.two_factor_enabled = True
        self.user.save(update_fields=['two_factor_enabled'])
        info.return_value = {
            'email': self.user.email,
            'given_name': 'Rahik',
            'family_name': 'Forman',
            'sub': 'google-1',
        }
        with self.settings(GOOGLE_CLIENT_ID='test-client'):
            response = self.api.post(GOOGLE, {'credential': 'token'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['requires_2fa'])
        self.assertNotIn('access', response.data)
        self.assertEqual(AuthSession.objects.count(), 0)


class SecurityCodeHelperTests(ShopTestCase):
    def test_generate_code_is_six_digits(self):
        code = generate_code()
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())
