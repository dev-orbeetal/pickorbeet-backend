from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.models import BdDistrict, BdDivision, BdPostOffice
from apps.orders.tests.factories import ShopTestCase, make_user


class BdGeoCatalogTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.user = make_user()
        self.api.force_authenticate(self.user)

    def test_public_cascade_endpoints(self):
        guest = APIClient()
        divisions = guest.get('/api/v1/geo/divisions/')
        self.assertEqual(divisions.status_code, 200, divisions.content)
        self.assertGreaterEqual(len(divisions.json()), 3)
        dhaka = next(row for row in divisions.json() if row['slug'] == 'dhaka')

        districts = guest.get('/api/v1/geo/districts/', {'division': dhaka['slug']})
        self.assertEqual(districts.status_code, 200, districts.content)
        self.assertTrue(any(row['slug'] == 'dhaka' for row in districts.json()))

        offices = guest.get('/api/v1/geo/post-offices/', {'district': 'dhaka'})
        self.assertEqual(offices.status_code, 200, offices.content)
        self.assertTrue(any(row['postal_code'] == '1212' for row in offices.json()))

    def test_address_create_validates_cascade(self):
        bad = self.api.post('/api/v1/auth/addresses/', {
            'full_name': 'Rakibul Hasan',
            'phone': '01712345678',
            'address_line1': 'House 1',
            'division': 'Dhaka',
            'city': 'Gulshan',
            'district': 'Chattogram',
            'post_office': 'Gulshan Model Town',
            'postal_code': '1212',
        }, format='json')
        self.assertEqual(bad.status_code, 400, bad.content)

        good = self.api.post('/api/v1/auth/addresses/', {
            'full_name': 'Rakibul Hasan',
            'phone': '01712345678',
            'address_line1': 'House 1',
            'division': 'Dhaka',
            'city': 'Gulshan',
            'district': 'Dhaka',
            'post_office': 'Gulshan Model Town',
            'postal_code': '1212',
            'is_default': True,
        }, format='json')
        self.assertEqual(good.status_code, 201, good.content)
        body = good.json()
        self.assertEqual(body['division'], 'Dhaka')
        self.assertEqual(body['district'], 'Dhaka')
        self.assertEqual(body['post_office'], 'Gulshan Model Town')
        self.assertEqual(body['postal_code'], '1212')
        self.assertTrue(body['is_inside_dhaka'])

    def test_seed_command_upserts_fixture(self):
        before_div = BdDivision.objects.count()
        before_dist = BdDistrict.objects.count()
        before_po = BdPostOffice.objects.count()
        call_command('seed_bd_locations')
        self.assertGreaterEqual(BdDivision.objects.count(), max(before_div, 8))
        self.assertGreaterEqual(BdDistrict.objects.count(), max(before_dist, 64))
        self.assertGreater(BdPostOffice.objects.count(), before_po)
        call_command('seed_bd_locations')
        self.assertEqual(BdDivision.objects.filter(slug='dhaka').count(), 1)
