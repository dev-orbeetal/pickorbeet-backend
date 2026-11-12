"""Admin users directory: every customer, and the fields staff may change."""
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Address, AuthSession
from apps.orders.models import Order
from apps.orders.tests.factories import ShopTestCase, make_order, make_user

LIST = '/api/v1/auth/customers/'
SUMMARY = '/api/v1/auth/customers/summary/'


def auth(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def detail(user):
    return f'/api/v1/auth/customers/{user.id}/'


def addresses(user):
    return f'/api/v1/auth/customers/{user.id}/addresses/'


def address_detail(user, address):
    return f'/api/v1/auth/customers/{user.id}/addresses/{address.id}/'


def priced_order(user, amount, status='delivered'):
    order = make_order(user=user, products=[], order_type='external', status=status)
    order.subtotal = Decimal(amount)
    order.delivery_charge = Decimal('0')
    order.discount = Decimal('0')
    order.save()
    return order


def saved_address(**fields):
    defaults = {
        'full_name': 'Rakibul Hasan',
        'phone': '01712345678',
        'address_line1': 'House 12, Road 4',
        'division': 'Dhaka',
        'city': 'Dhaka',
        'district': 'Dhaka',
        'post_office': 'Gulshan Model Town',
        'postal_code': '1212',
    }
    defaults.update(fields)
    return Address.objects.create(**defaults)


class AdminCustomerApiTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.seller = make_user(role='seller', email='seller@example.com')
        self.api = auth(self.seller)

    def test_lists_customers_with_no_orders_and_hides_staff(self):
        quiet = make_user(email='quiet@example.com', first_name='Quiet', last_name='Buyer')
        buyer = make_user(email='buyer@example.com', first_name='Busy', last_name='Buyer')
        priced_order(buyer, '80.00', status='delivered')
        priced_order(buyer, '40.00', status='cancelled')
        make_user(role='accountant', email='books@example.com')

        response = self.api.get(LIST)

        self.assertEqual(response.status_code, 200, response.data)
        by_email = {row['email']: row for row in response.data['results']}
        self.assertIn(quiet.email, by_email)
        self.assertNotIn('seller@example.com', by_email)
        self.assertNotIn('books@example.com', by_email)
        self.assertEqual(by_email[quiet.email]['order_count'], 0)
        self.assertEqual(by_email[quiet.email]['total_spent'], '0.00')
        self.assertEqual(by_email[buyer.email]['order_count'], 2)
        self.assertEqual(by_email[buyer.email]['total_spent'], '80.00')
        self.assertGreaterEqual(response.data['count'], 2)

    def test_search_filters_and_ordering(self):
        make_user(
            email='zarina@example.com', first_name='Zarina', last_name='Ahmed',
            phone='01812345678', is_verified=False,
        )
        inactive = make_user(
            email='inactive@example.com', first_name='Kabir', last_name='Hossain',
            is_active=False,
        )
        buyer = make_user(email='buyer@example.com', first_name='Busy', last_name='Buyer')
        priced_order(buyer, '500.00')
        small = make_user(email='small@example.com', first_name='Mina', last_name='Buyer')
        priced_order(small, '20.00')

        found = self.api.get(LIST, {'search': 'zarina'})
        self.assertEqual(
            [row['email'] for row in found.data['results']],
            ['zarina@example.com'],
        )
        by_phone = self.api.get(LIST, {'search': '01812345678'})
        self.assertEqual(by_phone.data['results'][0]['email'], 'zarina@example.com')

        inactive_only = self.api.get(LIST, {'is_active': 'false'})
        self.assertEqual(
            [row['email'] for row in inactive_only.data['results']],
            [inactive.email],
        )
        unverified = self.api.get(LIST, {'is_verified': 'false'})
        self.assertEqual(
            [row['email'] for row in unverified.data['results']],
            ['zarina@example.com'],
        )
        no_orders = self.api.get(LIST, {'has_orders': 'false'})
        self.assertCountEqual(
            [row['email'] for row in no_orders.data['results']],
            ['zarina@example.com', inactive.email],
        )

        ranked = self.api.get(LIST, {'ordering': '-total_spent'})
        self.assertEqual(ranked.data['results'][0]['email'], buyer.email)
        ignored = self.api.get(LIST, {'ordering': 'email'})
        self.assertEqual(ignored.status_code, 200)

    def test_summary_counts_customers_only(self):
        make_user(email='active@example.com')
        make_user(email='inactive@example.com', is_active=False)
        buyer = make_user(email='buyer@example.com')
        priced_order(buyer, '15.00')

        response = self.api.get(SUMMARY)

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['total'], 3)
        self.assertEqual(response.data['active'], 2)
        self.assertEqual(response.data['new_this_month'], 3)
        self.assertEqual(response.data['with_orders'], 1)

    def test_seller_updates_contact_details_and_cannot_change_role_or_password(self):
        customer = make_user(email='member@example.com', phone='01712345678')

        saved = self.api.patch(detail(customer), {
            'first_name': '  Nabila ',
            'last_name': 'Karim',
            'phone': '+880 1712-345678',
            'email': 'nabila@example.com',
            'address': 'House 4',
            'city': 'Dhaka',
            'postal_code': '1212',
        }, format='json')

        self.assertEqual(saved.status_code, 200, saved.data)
        customer.refresh_from_db()
        self.assertEqual(customer.first_name, 'Nabila')
        self.assertEqual(customer.last_name, 'Karim')
        self.assertEqual(customer.phone, '01712345678')
        self.assertEqual(customer.email, 'nabila@example.com')
        self.assertEqual(customer.address, 'House 4')
        self.assertEqual(customer.role, 'customer')
        self.assertTrue(customer.check_password('Str0ng-pass!'))

        role = self.api.patch(detail(customer), {'role': 'super_admin'}, format='json')
        self.assertEqual(role.status_code, 400)
        self.assertIn('role', role.data)
        password = self.api.patch(detail(customer), {'password': 'Another-pass-1'}, format='json')
        self.assertEqual(password.status_code, 400)
        self.assertIn('password', password.data)
        blank = self.api.patch(detail(customer), {'first_name': '   '}, format='json')
        self.assertEqual(blank.status_code, 400)
        landline = self.api.patch(detail(customer), {'phone': '021234567'}, format='json')
        self.assertEqual(landline.status_code, 400)

        customer.refresh_from_db()
        self.assertEqual(customer.role, 'customer')
        self.assertEqual(customer.first_name, 'Nabila')
        self.assertTrue(customer.check_password('Str0ng-pass!'))
        self.assertFalse(customer.check_password('Another-pass-1'))

    def test_duplicate_email_is_rejected(self):
        customer = make_user(email='member@example.com')
        make_user(email='taken@example.com')

        response = self.api.patch(detail(customer), {'email': 'taken@example.com'}, format='json')

        self.assertEqual(response.status_code, 400)
        customer.refresh_from_db()
        self.assertEqual(customer.email, 'member@example.com')

    def test_deactivating_a_customer_revokes_sessions(self):
        customer = make_user(email='member@example.com')
        session = AuthSession.objects.create(user=customer, device_name='iPhone')
        other = AuthSession.objects.create(user=make_user(), device_name='Other phone')

        kept = self.api.patch(detail(customer), {'first_name': 'Nabila'}, format='json')
        self.assertEqual(kept.status_code, 200, kept.data)
        session.refresh_from_db()
        self.assertIsNone(session.revoked_at)

        closed = self.api.patch(detail(customer), {'is_active': False}, format='json')
        self.assertEqual(closed.status_code, 200, closed.data)
        session.refresh_from_db()
        other.refresh_from_db()
        customer.refresh_from_db()
        self.assertIsNotNone(session.revoked_at)
        self.assertIsNone(other.revoked_at)
        self.assertFalse(customer.is_active)

    def test_detail_returns_eight_newest_orders(self):
        customer = make_user(email='member@example.com')
        base = timezone.now()
        created = []
        for index in range(9):
            order = priced_order(customer, '10.00')
            Order.objects.filter(pk=order.pk).update(created_at=base + timedelta(minutes=index))
            created.append(order)

        response = self.api.get(detail(customer))

        self.assertEqual(response.status_code, 200, response.data)
        shown = response.data['recent_orders']
        self.assertEqual(len(shown), 8)
        self.assertEqual(shown[0]['id'], str(created[-1].id))
        self.assertNotIn(str(created[0].id), [row['id'] for row in shown])
        self.assertEqual(response.data['total_spent'], '90.00')
        self.assertEqual(response.data['order_count'], 9)

    def test_address_update_uses_the_location_catalog(self):
        customer = make_user(email='member@example.com', first_name='Nabila', last_name='Karim')
        created = self.api.post(addresses(customer), {
            'full_name': 'Nabila Karim',
            'phone': '01712345678',
            'address_line1': 'House 12',
            'division': 'Dhaka',
            'district': 'Dhaka',
            'city': 'Dhaka',
            'post_office': 'Gulshan Model Town',
            'postal_code': '1212',
            'is_default': True,
        }, format='json')
        self.assertEqual(created.status_code, 201, created.data)

        address = Address.objects.get(pk=created.data['id'])
        renamed = self.api.patch(address_detail(customer, address), {'city': 'Banani'}, format='json')
        self.assertEqual(renamed.status_code, 200, renamed.data)
        address.refresh_from_db()
        self.assertEqual(address.city, 'Banani')

        invalid = self.api.patch(address_detail(customer, address), {'division': 'Nowhere'}, format='json')
        self.assertEqual(invalid.status_code, 400)
        address.refresh_from_db()
        self.assertEqual(address.division, 'Dhaka')

        someone = make_user(email='someone@example.com')
        foreign = saved_address(user=someone, full_name='Other Person')
        missing = self.api.patch(address_detail(customer, foreign), {'city': 'Banani'}, format='json')
        self.assertEqual(missing.status_code, 404)

        removed = self.api.delete(address_detail(customer, address))
        self.assertEqual(removed.status_code, 204)
        self.assertFalse(Address.objects.filter(pk=address.id).exists())

    def test_customers_and_accountants_cannot_manage_users(self):
        customer = make_user(email='member@example.com')
        accountant = make_user(role='accountant', email='books@example.com')

        for user in (customer, accountant):
            client = auth(user)
            self.assertEqual(client.get(LIST).status_code, 403)
            self.assertEqual(client.get(detail(customer)).status_code, 403)
            self.assertEqual(client.post(addresses(customer), {}, format='json').status_code, 403)

        self.assertEqual(APIClient().get(LIST).status_code, 401)
