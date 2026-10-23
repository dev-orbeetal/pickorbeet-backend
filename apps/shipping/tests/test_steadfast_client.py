from django.test import SimpleTestCase, override_settings

from apps.shipping.steadfast import (
    SteadfastAuthError,
    SteadfastClient,
    SteadfastConfigError,
    SteadfastDuplicateError,
    SteadfastError,
    SteadfastNetworkError,
    SteadfastNotFoundError,
    SteadfastValidationError,
)

from .fakes import CONNECTION_ERROR, TIMEOUT, FakeResponse, FakeSession

ORDER = dict(invoice='ORD-1', recipient_name='Rakibul Hasan', recipient_phone='01712345678',
             recipient_address='House 12, Road 4, Malibagh, Dhaka 1217', cod_amount=5657)


@override_settings(STEADFAST_BASE_URL='https://portal.packzy.com/api/v1')
class SteadfastClientTests(SimpleTestCase):
    def client_with(self, *responses):
        session = FakeSession(*responses)
        return SteadfastClient(api_key='key', secret_key='secret', session=session), session

    def test_create_order_sends_keys_and_returns_consignment(self):
        client, session = self.client_with(FakeResponse(200, {
            'status': 200,
            'message': 'Consignment has been created successfully.',
            'consignment': {'consignment_id': 1424107, 'tracking_code': '15BAEB8A', 'status': 'in_review'},
        }))
        consignment = client.create_order(**ORDER, note='Call first')

        self.assertEqual(consignment['tracking_code'], '15BAEB8A')
        call = session.calls[0]
        self.assertEqual(call['method'], 'POST')
        self.assertEqual(call['url'], 'https://portal.packzy.com/api/v1/create_order')
        self.assertEqual(call['headers']['Api-Key'], 'key')
        self.assertEqual(call['headers']['Secret-Key'], 'secret')
        self.assertFalse(call['allow_redirects'])
        self.assertEqual(call['timeout'], (5, 15))
        self.assertEqual(call['json']['cod_amount'], 5657)
        self.assertNotIn('alternative_phone', call['json'])

    def test_missing_keys_fail_before_any_request(self):
        session = FakeSession()
        client = SteadfastClient(api_key='', secret_key='', session=session)
        with self.assertRaises(SteadfastConfigError):
            client.status_by_cid(1)
        self.assertEqual(session.calls, [])

    def test_auth_failure(self):
        client, _ = self.client_with(FakeResponse(401, {'message': 'Unauthenticated.'}))
        with self.assertRaises(SteadfastAuthError):
            client.create_order(**ORDER)

    def test_validation_error_uses_first_field_message(self):
        client, _ = self.client_with(FakeResponse(422, {
            'status': 422, 'errors': {'recipient_phone': ['The recipient phone must be 11 digits.']},
        }))
        with self.assertRaises(SteadfastValidationError) as ctx:
            client.create_order(**ORDER)
        self.assertEqual(ctx.exception.message, 'The recipient phone must be 11 digits.')

    def test_duplicate_invoice_is_its_own_error(self):
        client, _ = self.client_with(FakeResponse(422, {
            'status': 422, 'errors': {'invoice': ['The invoice has already been taken.']},
        }))
        with self.assertRaises(SteadfastDuplicateError):
            client.create_order(**ORDER)

    def test_error_reported_inside_a_200_body(self):
        client, _ = self.client_with(FakeResponse(200, {'status': 400, 'message': 'Invalid COD amount'}))
        with self.assertRaises(SteadfastValidationError):
            client.create_order(**ORDER)

    def test_timeouts_and_connection_errors_are_retryable(self):
        for exc in (TIMEOUT, CONNECTION_ERROR):
            client, _ = self.client_with(exc)
            with self.assertRaises(SteadfastNetworkError) as ctx:
                client.status_by_cid(1)
            self.assertTrue(ctx.exception.retryable)

    def test_server_errors_are_retryable(self):
        client, _ = self.client_with(FakeResponse(502, None))
        with self.assertRaises(SteadfastNetworkError):
            client.status_by_cid(1)

    def test_redirects_are_not_followed(self):
        client, _ = self.client_with(FakeResponse(302, None))
        with self.assertRaises(SteadfastError):
            client.status_by_cid(1)

    def test_not_json(self):
        client, _ = self.client_with(FakeResponse(200, None, text='<html>'))
        with self.assertRaises(SteadfastError):
            client.status_by_cid(1)

    def test_not_found(self):
        client, _ = self.client_with(FakeResponse(404, {'status': 404, 'message': 'Consignment not found'}))
        with self.assertRaises(SteadfastNotFoundError):
            client.status_by_cid(99)

    def test_status_lookups(self):
        client, session = self.client_with(
            FakeResponse(200, {'status': 200, 'delivery_status': 'pending'}),
            FakeResponse(200, {'status': 200, 'delivery_status': 'delivered'}),
            FakeResponse(200, {'status': 200, 'delivery_status': 'hold'}),
        )
        self.assertEqual(client.status_by_cid(1424107), 'pending')
        self.assertEqual(client.status_by_invoice('ORD-1'), 'delivered')
        self.assertEqual(client.status_by_tracking_code('15BAEB8A'), 'hold')
        self.assertEqual([c['url'].rsplit('/', 2)[-2] for c in session.calls],
                         ['status_by_cid', 'status_by_invoice', 'status_by_trackingcode'])

    def test_create_order_without_consignment_is_an_error(self):
        client, _ = self.client_with(FakeResponse(200, {'status': 200, 'message': 'ok'}))
        with self.assertRaises(SteadfastError):
            client.create_order(**ORDER)
