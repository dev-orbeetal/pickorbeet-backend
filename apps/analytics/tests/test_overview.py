import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from django.utils import timezone
from rest_framework.test import APIClient

from apps.analytics.models import PageView, Visitor
from apps.orders.models import Order
from apps.orders.tests.factories import ShopTestCase, make_order, make_user

DHAKA = ZoneInfo('Asia/Dhaka')
OVERVIEW = '/api/v1/analytics/overview/'
FUNNEL = '/api/v1/analytics/funnel/'


def at(day, hour=12):
    return datetime(2026, 10, day, hour, tzinfo=DHAKA)


def make_hit(when, path='/', visitor=None, session=None, user=None):
    if visitor is None:
        visitor = Visitor.objects.create(
            visitor_key=uuid.uuid4(),
            first_seen=when,
            last_seen=when,
        )
    return PageView.objects.create(
        event_id=uuid.uuid4(),
        occurred_at=when,
        visitor=visitor,
        session_key=session or uuid.uuid4(),
        user=user,
        path=path,
        device_type='desktop',
        browser='Chrome',
        os='Mac OS X',
        source='direct',
    )


class OverviewTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.staff = make_user(role='seller')
        self.api = APIClient()
        self.api.force_authenticate(self.staff)

    def test_guest_cannot_read_traffic(self):
        self.assertEqual(APIClient().get(OVERVIEW).status_code, 401)

    def test_dhaka_day_bucket(self):
        # 20:30 UTC is 02:30 the next morning in Dhaka.
        make_hit(datetime(2026, 10, 28, 20, 30, tzinfo=ZoneInfo('UTC')), path='/')
        included = self.api.get(OVERVIEW, {'from': '2026-10-29', 'to': '2026-10-29'})
        self.assertEqual(included.status_code, 200, included.data)
        self.assertEqual(included.data['kpis']['pageviews'], 1)
        self.assertEqual(included.data['series'], [
            {'date': '2026-10-29', 'visitors': 1, 'pageviews': 1, 'sessions': 1},
        ])
        excluded = self.api.get(OVERVIEW, {'from': '2026-10-28', 'to': '2026-10-28'})
        self.assertEqual(excluded.data['kpis']['pageviews'], 0)
        self.assertEqual(excluded.data['timezone'], 'Asia/Dhaka')

    def test_previous_period_delta(self):
        make_hit(at(27), path='/')
        make_hit(at(28, 11), path='/product/one')
        make_hit(at(28, 15), path='/cart')
        response = self.api.get(OVERVIEW, {'from': '2026-10-28', 'to': '2026-10-28'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['kpis']['visitors'], 2)
        self.assertEqual(response.data['kpis']['pageviews'], 2)
        self.assertEqual(response.data['previous']['visitors'], 1)
        self.assertEqual(response.data['change']['visitors'], 100.0)
        self.assertEqual(response.data['series'][0]['date'], '2026-10-28')

    def test_customer_list_uses_the_latest_page(self):
        customer = make_user(first_name='Nusrat', last_name='Jahan', email='nusrat-traffic@example.com')
        visitor = Visitor.objects.create(
            visitor_key=uuid.uuid4(),
            first_seen=at(28, 9),
            last_seen=at(28, 12),
            user=customer,
        )
        make_hit(at(28, 10), '/product/one', visitor=visitor, user=customer)
        make_hit(at(28, 12), '/cart', visitor=visitor, user=customer)
        response = self.api.get(
            '/api/v1/analytics/customers/',
            {'from': '2026-10-28', 'to': '2026-10-28', 'q': 'nusrat-traffic'},
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data['results']), 1)
        row = response.data['results'][0]
        self.assertEqual(row['email'], 'nusrat-traffic@example.com')
        self.assertEqual(row['pageviews'], 2)
        self.assertEqual(row['last_path'], '/cart')
        self.assertEqual(row['name'], 'Nusrat Jahan')

        timeline = self.api.get(f"/api/v1/analytics/customers/{customer.id}/")
        self.assertEqual(timeline.status_code, 200, timeline.data)
        self.assertEqual(timeline.data['results'][0]['path'], '/cart')

        live = self.api.get('/api/v1/analytics/live/')
        self.assertEqual(live.status_code, 200, live.data)
        self.assertEqual(live.data['results'][0]['path'], '/cart')
        self.assertEqual(live.data['results'][0]['user']['email'], 'nusrat-traffic@example.com')

    def test_funnel_counts_product_cart_checkout_and_online_orders(self):
        when = at(28, 16)
        make_hit(when, '/product/airdopes')
        make_hit(when, '/product/speaker')
        make_hit(when, '/products')
        make_hit(when, '/cart')
        make_hit(when, '/checkout')
        online = make_order(order_type='online')
        cancelled = make_order(order_type='online', status='cancelled')
        in_shop = make_order(order_type='in_shop')
        Order.objects.filter(pk__in=[online.pk, cancelled.pk, in_shop.pk]).update(created_at=when)

        response = self.api.get(FUNNEL, {'from': '2026-10-28', 'to': '2026-10-28'})
        self.assertEqual(response.status_code, 200, response.data)
        steps = {step['key']: step for step in response.data['steps']}
        self.assertEqual(steps['product']['pageviews'], 2)
        self.assertEqual(steps['cart']['pageviews'], 1)
        self.assertEqual(steps['checkout']['pageviews'], 1)
        self.assertEqual(steps['orders']['pageviews'], 1)
        self.assertLess(when, timezone.now())
