from unittest import mock

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient

from apps.orders.tests.factories import ShopTestCase, make_order, make_product, make_user
from apps.shipping.models import SteadfastPoliceStation
from apps.shipping.services import (
    ShipmentError,
    book_shipment,
    recipient_address_for,
    refresh_police_stations,
)
from apps.shipping.thanas import MATCHED, SADAR, district_key, match_police_station, text_key

from .fakes import POLICE_STATIONS, FakeClient

NOAKHALI = {
    'shipping_address_line1': 'Vill: Uttar Char Matua',
    'shipping_address_line2': 'Near Matua Bazar',
    'shipping_division': 'Chattogram',
    'shipping_city': 'Maijdee',
    'shipping_district': 'Noakhali',
    'shipping_post_office': 'Maijdee Court',
    'shipping_postal_code': '3800',
}


class SpellingTests(SimpleTestCase):
    def test_old_and_new_spellings_share_a_key(self):
        self.assertEqual(district_key('Chittagong'), district_key('Chattogram'))
        self.assertEqual(district_key('Comilla'), district_key('Cumilla'))
        self.assertEqual(district_key("Cox's Bazar"), district_key('Coxsbazar'))
        self.assertEqual(district_key('Chapai Nawabganj'), district_key('Nawabganj'))
        self.assertEqual(district_key('Sirajgonj'), district_key('Sirajganj'))
        self.assertEqual(district_key('Moulvi Bazar'), district_key('Maulvibazar'))
        self.assertEqual(text_key('Kotowali, Sador'), 'kotwali sadar')


class PoliceStationTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        refresh_police_stations(client=FakeClient())

    def test_refresh_saves_every_station_and_retires_missing_ones(self):
        self.assertEqual(SteadfastPoliceStation.objects.count(), 11)
        station = SteadfastPoliceStation.objects.get(pk=301)
        self.assertEqual((station.name, station.district_name), ('Kotwali', 'Chittagong'))
        self.assertEqual(station.district_key, 'chattogram')

        client = FakeClient()
        feni = {'id': 9, 'name': 'Feni', 'police_stations': [{'id': 901, 'name': 'Feni Sadar'}]}
        client.police_stations = lambda: [*POLICE_STATIONS[:3], feni]
        result = refresh_police_stations(client=client)
        self.assertEqual(result, {'districts': 4, 'stations': 10})
        self.assertEqual(SteadfastPoliceStation.objects.get(pk=901).district_name, 'Feni')
        self.assertFalse(SteadfastPoliceStation.objects.get(pk=401).is_active)
        self.assertTrue(SteadfastPoliceStation.objects.get(pk=301).is_active)

    def test_an_empty_list_keeps_the_cache(self):
        client = FakeClient()
        client.police_stations = lambda: []
        with self.assertRaises(ShipmentError):
            refresh_police_stations(client=client)
        self.assertEqual(SteadfastPoliceStation.objects.filter(is_active=True).count(), 11)

    def test_post_office_or_street_names_the_thana(self):
        order = make_order(**{**NOAKHALI, 'shipping_post_office': 'Begumganj'})
        station, how = match_police_station(order)
        self.assertEqual((station.name, how), ('Begumganj', MATCHED))

        order = make_order(shipping_city='Dhaka', shipping_post_office='', shipping_address_line2='Mirpur Model Town')
        station, how = match_police_station(order)
        self.assertEqual((station.name, how), ('Mirpur Model', MATCHED))

    def test_unmatched_areas_fall_back_to_the_district_sadar(self):
        station, how = match_police_station(make_order(**NOAKHALI))
        self.assertEqual((station.name, how), ('Noakhali Sadar', SADAR))

        cumilla = make_order(shipping_division='Chattogram', shipping_district='Cumilla', shipping_city='Cumilla',
                             shipping_post_office='', shipping_address_line2='')
        station, how = match_police_station(cumilla)
        self.assertEqual((station.name, how), ('Comilla Sadar Dakshin', SADAR))

    def test_spelling_variants_still_match(self):
        order = make_order(shipping_division='Chattogram', shipping_district='Chattogram',
                           shipping_city='Chattogram', shipping_post_office='Kotowali', shipping_address_line2='')
        station, how = match_police_station(order)
        self.assertEqual((station.id, how), (301, MATCHED))

    def test_districts_without_cached_stations_get_no_thana(self):
        order = make_order(shipping_district='Sylhet', shipping_city='Sylhet', shipping_division='Sylhet')
        self.assertEqual(match_police_station(order), (None, ''))


class RecipientAddressTests(ShopTestCase):
    def test_names_thana_and_district_after_the_street(self):
        order = make_order(**NOAKHALI)
        station = SteadfastPoliceStation(id=1, name='Noakhali Sadar', district_name='Noakhali')
        self.assertEqual(
            recipient_address_for(order, station),
            'Vill: Uttar Char Matua, Near Matua Bazar, Maijdee, Maijdee Court, Noakhali Sadar, Noakhali, 3800',
        )

    def test_long_streets_are_cut_before_the_district(self):
        order = make_order(**{**NOAKHALI, 'shipping_address_line1': 'House 7, ' + 'Long lane ' * 24})
        station = SteadfastPoliceStation(id=1, name='Noakhali Sadar', district_name='Noakhali')
        address = recipient_address_for(order, station)
        self.assertLessEqual(len(address), 250)
        self.assertTrue(address.startswith('House 7, Long lane'))
        self.assertTrue(address.endswith('Maijdee, Maijdee Court, Noakhali Sadar, Noakhali, 3800'))

    def test_repeated_parts_appear_once(self):
        order = make_order(shipping_city='Dhaka', shipping_district='Dhaka', shipping_post_office='',
                           shipping_address_line2='Dhaka')
        self.assertEqual(recipient_address_for(order), 'House 12, Road 4, Dhaka, 1212')


@override_settings(STEADFAST_SYNC_ORDER_STATUS=True)
class BookingOverrideTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        refresh_police_stations(client=FakeClient())
        self.staff = make_user(role='seller', is_staff=True)
        self.order = make_order(user=make_user(), products=[make_product()], **NOAKHALI)

    def test_booking_names_the_matched_thana(self):
        client = FakeClient()
        shipment = book_shipment(self.order, self.staff, client=client)
        self.assertIn('Noakhali Sadar, Noakhali, 3800', client.created[0]['recipient_address'])
        self.assertEqual(shipment.police_station_id, 201)

    def test_staff_can_choose_the_thana(self):
        client = FakeClient()
        shipment = book_shipment(self.order, self.staff, client=client, police_station_id=203)
        self.assertIn('Companiganj, Noakhali', client.created[0]['recipient_address'])
        self.assertEqual(shipment.police_station_id, 203)

    def test_staff_can_send_their_own_address_text(self):
        client = FakeClient()
        book_shipment(self.order, self.staff, client=client,
                      recipient_address='  Matua Bazar,   Companiganj, Noakhali ')
        self.assertEqual(client.created[0]['recipient_address'], 'Matua Bazar, Companiganj, Noakhali')

    def test_an_unknown_thana_is_refused(self):
        with self.assertRaises(ShipmentError) as caught:
            book_shipment(self.order, self.staff, client=FakeClient(), police_station_id=99999)
        self.assertEqual(caught.exception.code, 'unknown_police_station')

    def test_preview_shows_the_address_and_the_district_thanas(self):
        api = APIClient()
        api.force_authenticate(self.staff)
        url = f'/api/v1/shipping/admin/orders/{self.order.pk}/booking-preview/'

        body = api.get(url).json()
        self.assertEqual(body['police_station'], {'id': 201, 'name': 'Noakhali Sadar', 'district_name': 'Noakhali'})
        self.assertEqual(body['police_station_match'], SADAR)
        self.assertEqual([row['name'] for row in body['police_stations']],
                         ['Begumganj', 'Companiganj', 'Noakhali Sadar'])
        self.assertTrue(body['recipient_address'].endswith('Noakhali Sadar, Noakhali, 3800'))
        self.assertEqual(body['recipient_phone'], '01712345678')

        chosen = api.get(url, {'police_station_id': 202}).json()
        self.assertEqual(chosen['police_station_match'], 'chosen')
        self.assertIn('Begumganj, Noakhali', chosen['recipient_address'])

        self.assertEqual(APIClient().get(url).status_code, 401)

    def test_booking_endpoint_accepts_the_overrides(self):
        api = APIClient()
        api.force_authenticate(self.staff)
        client = FakeClient()
        with mock.patch('apps.shipping.services.SteadfastClient', return_value=client):
            response = api.post(f'/api/v1/orders/admin/{self.order.pk}/shipment/',
                                {'police_station_id': 202}, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertIn('Begumganj, Noakhali', client.created[0]['recipient_address'])
