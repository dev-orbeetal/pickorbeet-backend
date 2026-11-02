from datetime import timedelta
from unittest import mock

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.orders.tests.factories import ShopTestCase, make_order, make_user
from apps.shipping.models import Shipment, ShipmentEvent
from apps.shipping.services import book_shipment

from .fakes import FakeClient

WEBHOOK = '/api/v1/shipping/steadfast/webhook/'


@override_settings(STEADFAST_WEBHOOK_TOKEN='hook-secret', STEADFAST_SYNC_ORDER_STATUS=True)
class WebhookTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.order = make_order(user=make_user())
        self.shipment = book_shipment(self.order, make_user(role='seller'), client=FakeClient())
        self.api = APIClient()

    def post(self, body, token='hook-secret', **headers):
        if token is not None:
            headers['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        return self.api.post(WEBHOOK, body, format='json', **headers)

    def delivery(self, status='delivered', **extra):
        body = {
            'notification_type': 'delivery_status',
            'consignment_id': 1424107,
            'invoice': self.order.order_number,
            'cod_amount': 1659.0,
            'status': status,
            'delivery_charge': 60.0,
            'tracking_message': 'Your package has been delivered successfully.',
            'updated_at': '2025-10-24 12:45:30',
        }
        body.update(extra)
        return body

    def test_rejects_missing_or_wrong_token(self):
        self.assertEqual(self.post(self.delivery(), token=None).status_code, 401)
        self.assertEqual(self.post(self.delivery(), token='nope').status_code, 401)

    @override_settings(STEADFAST_WEBHOOK_TOKEN='')
    def test_rejects_everything_when_not_configured(self):
        self.assertEqual(self.post(self.delivery(), token='').status_code, 401)

    def test_delivery_status_updates_shipment_and_order(self):
        response = self.post(self.delivery(), HTTP_IDEMPOTENCY_KEY='evt-1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')

        self.shipment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.shipment.status, 'delivered')
        self.assertEqual(self.shipment.status_message, 'Your package has been delivered successfully.')
        self.assertEqual(str(self.shipment.delivery_charge), '60.00')
        self.assertEqual(self.shipment.status_updated_at.year, 2025)
        self.assertEqual(self.order.order_status, 'delivered')

    def test_duplicate_deliveries_are_ignored(self):
        self.post(self.delivery('hold'), HTTP_IDEMPOTENCY_KEY='evt-2')
        self.post(self.delivery('hold'), HTTP_IDEMPOTENCY_KEY='evt-2')
        self.assertEqual(ShipmentEvent.objects.filter(idempotency_key='evt-2').count(), 1)

    def test_retries_without_a_key_are_deduplicated_by_content(self):
        self.post(self.delivery('pending'))
        self.post(self.delivery('pending'))
        self.assertEqual(ShipmentEvent.objects.filter(source='webhook').count(), 1)

    def test_tracking_update_keeps_status(self):
        response = self.post({
            'notification_type': 'tracking_update',
            'consignment_id': 1424107,
            'invoice': self.order.order_number,
            'tracking_message': 'Package arrived at the sorting center.',
            'updated_at': '2025-10-24 13:15:00',
        })
        self.assertEqual(response.status_code, 200)
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.status, 'in_review')
        self.assertEqual(self.shipment.status_message, 'Package arrived at the sorting center.')

    def test_unknown_consignment(self):
        response = self.post(self.delivery(consignment_id=999, invoice='ORD-NOPE'))
        self.assertEqual(response.status_code, 404)

    def test_unsupported_notification(self):
        response = self.post({'notification_type': 'balance_update', 'consignment_id': 1424107})
        self.assertEqual(response.status_code, 400)


@override_settings(STEADFAST_SYNC_ORDER_STATUS=True)
class ShipmentEndpointTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_user()
        self.staff = make_user(role='seller')
        self.order = make_order(user=self.customer)
        self.api = APIClient()

    def book_url(self):
        return f'/api/v1/orders/admin/{self.order.pk}/shipment/'

    def test_only_staff_can_book(self):
        self.api.force_authenticate(self.customer)
        self.assertEqual(self.api.post(self.book_url(), {}, format='json').status_code, 403)

    @mock.patch('apps.shipping.services.SteadfastClient', return_value=FakeClient())
    def test_staff_booking_returns_the_order_with_its_shipment(self, _client):
        self.api.force_authenticate(self.staff)
        response = self.api.post(self.book_url(), {'note': 'Fragile'}, format='json')
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body['order_status'], 'shipped')
        self.assertEqual(body['shipment']['tracking_code'], 'SF123456789BD')
        self.assertEqual(body['shipment']['status_group'], 'in_review')
        self.assertEqual(body['shipment']['recipient_phone'], '01712345678')  # staff payload

        again = self.api.post(self.book_url(), {}, format='json')
        self.assertEqual(again.status_code, 409)

    @mock.patch('apps.shipping.services.SteadfastClient')
    def test_booking_without_keys_is_a_clear_503(self, client_cls):
        from apps.shipping.steadfast import SteadfastConfigError
        client_cls.return_value = FakeClient(error=SteadfastConfigError('Steadfast API keys are not configured.'))
        self.api.force_authenticate(self.staff)
        response = self.api.post(self.book_url(), {}, format='json')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['code'], 'courier_not_configured')

    def test_customer_payload_hides_booking_internals(self):
        book_shipment(self.order, self.staff, client=FakeClient())
        self.api.force_authenticate(self.customer)
        body = self.api.get(f'/api/v1/orders/my-orders/{self.order.pk}/').json()
        self.assertEqual(body['shipment']['tracking_code'], 'SF123456789BD')
        self.assertNotIn('recipient_phone', body['shipment'])
        self.assertNotIn('booked_by', body['shipment'])
        self.assertFalse(body['can_edit_delivery'])

    def test_customer_refresh_rules(self):
        book_shipment(self.order, self.staff, client=FakeClient())
        url = f'/api/v1/orders/my-orders/{self.order.pk}/shipment/refresh/'

        self.api.force_authenticate(make_user())
        self.assertEqual(self.api.post(url).status_code, 404)  # someone else's order

        self.api.force_authenticate(self.customer)
        cooling = self.api.post(url)
        self.assertEqual(cooling.status_code, 429)
        self.assertIn('Retry-After', cooling.headers)
        self.assertEqual(cooling.json()['code'], 'refresh_cooldown')

        Shipment.objects.filter(order=self.order).update(last_checked_at=timezone.now() - timedelta(minutes=5))
        with mock.patch('apps.shipping.services.SteadfastClient', return_value=FakeClient(status='pending')):
            fresh = self.api.post(url)
        self.assertEqual(fresh.status_code, 200)
        self.assertEqual(fresh.json()['shipment']['status'], 'pending')

    def test_customer_refresh_before_booking(self):
        self.api.force_authenticate(self.customer)
        response = self.api.post(f'/api/v1/orders/my-orders/{self.order.pk}/shipment/refresh/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['code'], 'not_booked')

    def test_staff_refresh_ignores_cooldown(self):
        book_shipment(self.order, self.staff, client=FakeClient())
        self.api.force_authenticate(self.staff)
        with mock.patch('apps.shipping.services.SteadfastClient', return_value=FakeClient(status='hold')):
            response = self.api.post(f'/api/v1/orders/admin/{self.order.pk}/shipment/refresh/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['shipment']['status_group'], 'hold')

    def test_public_tracking_includes_the_courier(self):
        book_shipment(self.order, self.staff, client=FakeClient())
        response = APIClient().post('/api/v1/orders/track/', {'order_number': self.order.order_number}, format='json')
        self.assertEqual(response.status_code, 200)
        shipment = response.json()['shipment']
        self.assertEqual(shipment['tracking_code'], 'SF123456789BD')
        self.assertEqual(shipment['courier_name'], 'Steadfast Courier')
        self.assertEqual(shipment['events'][0]['source'], 'booking')
        self.assertNotIn('cod_amount', shipment)

        by_code = APIClient().post('/api/v1/orders/track/', {'tracking_code': 'sf123456789bd'}, format='json')
        self.assertEqual(by_code.status_code, 200)
        self.assertEqual(by_code.json()['order_number'], self.order.order_number)


@override_settings(STEADFAST_SYNC_ORDER_STATUS=True)
class AdminShipmentDashboardTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.staff = make_user(role='seller')
        self.customer = make_user()
        self.api = APIClient()
        self.order_a = make_order(user=self.customer)
        self.order_b = make_order(user=make_user())
        self.ship_a = book_shipment(self.order_a, self.staff, client=FakeClient(consignment_id=1001, tracking_code='AAA111'))
        self.ship_b = book_shipment(self.order_b, self.staff, client=FakeClient(consignment_id=1002, tracking_code='BBB222'))
        Shipment.objects.filter(pk=self.ship_b.pk).update(status='delivered')

    def test_list_and_status_group_filter(self):
        self.api.force_authenticate(self.staff)
        listing = self.api.get('/api/v1/shipping/admin/shipments/')
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()['count'], 2)

        delivered = self.api.get('/api/v1/shipping/admin/shipments/', {'status_group': 'delivered'})
        self.assertEqual(delivered.status_code, 200)
        self.assertEqual(delivered.json()['count'], 1)
        self.assertEqual(delivered.json()['results'][0]['tracking_code'], 'BBB222')

        search = self.api.get('/api/v1/shipping/admin/shipments/', {'search': self.order_a.order_number})
        self.assertEqual(search.json()['count'], 1)
        self.assertEqual(search.json()['results'][0]['order']['order_number'], self.order_a.order_number)

    def test_summary_kpis(self):
        self.api.force_authenticate(self.staff)
        response = self.api.get('/api/v1/shipping/admin/shipments/summary/')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['total'], 2)
        self.assertEqual(body['by_status_group']['in_review'], 1)
        self.assertEqual(body['by_status_group']['delivered'], 1)
        self.assertEqual(body['open_count'], 1)

    def test_balance_endpoint(self):
        self.api.force_authenticate(self.staff)
        with mock.patch('apps.shipping.views.SteadfastClient', return_value=FakeClient(balance=990.25)):
            response = self.api.get('/api/v1/shipping/admin/steadfast/balance/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'configured': True, 'current_balance': 990.25})

    def test_refresh_and_bulk_refresh(self):
        self.api.force_authenticate(self.staff)
        with mock.patch('apps.shipping.services.SteadfastClient', return_value=FakeClient(status='pending')):
            single = self.api.post(f'/api/v1/shipping/admin/shipments/{self.ship_a.pk}/refresh/')
        self.assertEqual(single.status_code, 200)
        self.assertEqual(single.json()['status'], 'pending')
        self.ship_a.refresh_from_db()
        self.assertIsNotNone(self.ship_a.last_checked_at)

        open_ship = book_shipment(
            make_order(user=make_user()),
            self.staff,
            client=FakeClient(consignment_id=1003, tracking_code='CCC333'),
        )
        with mock.patch('apps.shipping.services.SteadfastClient', return_value=FakeClient(status='hold')):
            bulk = self.api.post(
                '/api/v1/shipping/admin/shipments/bulk-refresh/',
                {'ids': [str(self.ship_a.pk), str(open_ship.pk)], 'pause': 0},
                format='json',
            )
        self.assertEqual(bulk.status_code, 200)
        self.assertEqual(bulk.json()['checked'], 2)
        open_ship.refresh_from_db()
        self.assertEqual(open_ship.status, 'hold')

    def test_detail_can_include_live_trackings(self):
        self.api.force_authenticate(self.staff)
        steps = [{'status': 'pending', 'message': 'At hub'}]
        with mock.patch('apps.shipping.views.SteadfastClient', return_value=FakeClient(trackings=steps)):
            response = self.api.get(f'/api/v1/shipping/admin/shipments/{self.ship_a.pk}/', {'live': 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['live_trackings'], steps)

    def test_customers_cannot_access_admin_shipments(self):
        self.api.force_authenticate(self.customer)
        self.assertEqual(self.api.get('/api/v1/shipping/admin/shipments/').status_code, 403)
