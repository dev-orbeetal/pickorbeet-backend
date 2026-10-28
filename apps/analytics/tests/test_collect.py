import uuid

from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.analytics.models import PageView, Visitor
from apps.orders.tests.factories import ShopTestCase, make_user

COLLECT = '/api/v1/analytics/collect/'
SECRET = 'test-secret'
MOBILE_UA = (
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) '
    'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1'
)
BOT_UA = 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'


def access_token(user):
    return str(RefreshToken.for_user(user).access_token)


def payload(**overrides):
    data = {
        'type': 'pageview',
        'event_id': str(uuid.uuid4()),
        'visitor_id': str(uuid.uuid4()),
        'session_id': str(uuid.uuid4()),
        'path': '/',
        'title': 'Home',
        'referrer': '',
        'channel': 'web',
        'country': 'BD',
        'region': 'Dhaka',
        'city': 'Dhaka',
    }
    data.update(overrides)
    return data


@override_settings(ANALYTICS_INGEST_SECRET=SECRET)
class CollectTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()

    def post(self, body, **extra):
        headers = {
            'HTTP_X_ANALYTICS_SECRET': SECRET,
            'HTTP_USER_AGENT': MOBILE_UA,
        }
        headers.update(extra)
        return self.api.post(COLLECT, body, format='json', **headers)

    def test_secret_is_required_when_configured(self):
        response = self.api.post(COLLECT, payload(), format='json', HTTP_USER_AGENT=MOBILE_UA)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(PageView.objects.count(), 0)

    def test_stores_a_mobile_visit_and_trusted_region(self):
        response = self.post(payload(path='/product/airdopes', title='Airdopes'))
        self.assertEqual(response.status_code, 204, response.content)
        hit = PageView.objects.get()
        self.assertEqual(hit.path, '/product/airdopes')
        self.assertEqual(hit.country_code, 'BD')
        self.assertEqual(hit.region, 'Dhaka')
        self.assertEqual(hit.city, 'Dhaka')
        self.assertEqual(hit.device_type, 'mobile')
        self.assertEqual(hit.visitor.pageview_count, 1)

    @override_settings(ANALYTICS_INGEST_SECRET='', DEBUG=True)
    def test_client_geo_is_ignored_without_a_secret(self):
        response = self.api.post(COLLECT, payload(), format='json', HTTP_USER_AGENT=MOBILE_UA)
        self.assertEqual(response.status_code, 204, response.content)
        hit = PageView.objects.get()
        self.assertEqual(hit.country_code, '')
        self.assertEqual(hit.city, '')

    def test_bots_prefetches_staff_and_admin_paths_are_dropped(self):
        bot = self.post(payload(), HTTP_USER_AGENT=BOT_UA)
        self.assertEqual(bot.status_code, 204)
        prefetch = self.post(payload(), HTTP_PURPOSE='prefetch')
        self.assertEqual(prefetch.status_code, 204)
        staff = make_user(role='seller')
        staff_hit = self.post(payload(), HTTP_AUTHORIZATION=f'Bearer {access_token(staff)}')
        self.assertEqual(staff_hit.status_code, 204)
        admin = self.post(payload(path='/admin/dashboard'))
        self.assertEqual(admin.status_code, 204)
        self.assertEqual(PageView.objects.count(), 0)

    def test_query_strings_and_order_numbers_are_normalized(self):
        response = self.post(payload(
            path='/order-success/ORD-20261028-ABC123?utm_source=eid&email=secret@example.com',
            referrer='https://l.instagram.com/reel/abc',
            utm_campaign='eid-sale',
            title='Thanks',
        ))
        self.assertEqual(response.status_code, 204, response.content)
        hit = PageView.objects.get()
        self.assertEqual(hit.path, '/order-success/:order')
        self.assertNotIn('ORD-20261028', hit.path)
        self.assertNotIn('secret@example.com', hit.path)
        self.assertEqual(hit.utm_source, 'eid')
        self.assertEqual(hit.utm_campaign, 'eid-sale')
        self.assertEqual(hit.source, 'instagram')
        self.assertEqual(hit.referrer_host, 'l.instagram.com')

    def test_customer_token_links_earlier_hits_and_a_bad_token_stays_a_guest(self):
        visitor_id = str(uuid.uuid4())
        guest = self.post(payload(visitor_id=visitor_id, path='/'))
        self.assertEqual(guest.status_code, 204, guest.content)

        customer = make_user(first_name='Nusrat', last_name='Jahan')
        signed_in = self.post(
            payload(visitor_id=visitor_id, path='/cart'),
            HTTP_AUTHORIZATION=f'Bearer {access_token(customer)}',
        )
        self.assertEqual(signed_in.status_code, 204, signed_in.content)
        self.assertEqual(PageView.objects.filter(user=customer).count(), 2)
        self.assertEqual(Visitor.objects.get(visitor_key=visitor_id).user_id, customer.id)

        bad = self.post(
            payload(path='/products'),
            HTTP_AUTHORIZATION='Bearer not-a-real-token',
        )
        self.assertEqual(bad.status_code, 204, bad.content)
        self.assertIsNone(PageView.objects.get(path='/products').user_id)

    def test_duplicate_event_id_is_stored_once(self):
        body = payload()
        first = self.post(body)
        second = self.post(body)
        self.assertEqual(first.status_code, 204)
        self.assertEqual(second.status_code, 204)
        self.assertEqual(PageView.objects.count(), 1)

    def test_engagement_sets_duration(self):
        body = payload()
        self.post(body)
        response = self.post({
            'type': 'engagement',
            'event_id': body['event_id'],
            'visitor_id': body['visitor_id'],
            'duration_ms': 4200,
        })
        self.assertEqual(response.status_code, 204, response.content)
        self.assertEqual(PageView.objects.get().duration_ms, 4200)

    def test_deleting_a_customer_keeps_the_visit_without_their_name(self):
        customer = make_user()
        self.post(payload(), HTTP_AUTHORIZATION=f'Bearer {access_token(customer)}')
        hit = PageView.objects.get()
        self.assertEqual(hit.user_id, customer.id)
        user_id = customer.id
        customer.delete()
        hit.refresh_from_db()
        self.assertIsNone(hit.user_id)
        self.assertFalse(User.objects.filter(pk=user_id).exists())

    def test_whatsapp_referrer_is_its_own_source(self):
        self.post(payload(referrer='https://web.whatsapp.com/'))
        self.assertEqual(PageView.objects.get().source, 'whatsapp')
        self.assertEqual(PageView.objects.get().referrer_host, 'web.whatsapp.com')
