from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APIClient

from apps.orders.models import Coupon, CouponUsage

from .factories import ShopTestCase, make_order, make_user


def _make_coupon(**fields):
    now = timezone.now()
    defaults = {
        'code': 'SAVE10',
        'name': 'Ten percent off',
        'description': 'Save on electronics',
        'discount_type': 'percentage',
        'discount_value': Decimal('10.00'),
        'minimum_order_amount': Decimal('500.00'),
        'valid_from': now - timedelta(days=1),
        'valid_until': now + timedelta(days=30),
        'is_active': True,
    }
    defaults.update(fields)
    return Coupon.objects.create(**defaults)


class CustomerCouponListTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.url = '/api/v1/orders/coupons/'

    def test_empty_db_returns_empty_list(self):
        response = self.api.get(self.url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), [])

    def test_active_coupon_is_available(self):
        coupon = _make_coupon()
        response = self.api.get(self.url)
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(len(body), 1)
        row = body[0]
        self.assertEqual(row['id'], str(coupon.id))
        self.assertEqual(row['code'], 'SAVE10')
        self.assertEqual(row['name'], 'Ten percent off')
        self.assertEqual(row['state'], 'available')
        self.assertIsNone(row['used_at'])
        self.assertEqual(row['discount_type'], 'percentage')
        self.assertEqual(row['discount_value'], '10.00')
        self.assertEqual(row['minimum_order_amount'], '500.00')

    def test_usage_appears_as_used_for_that_customer_only(self):
        coupon = _make_coupon(code='USED1')
        owner = make_user()
        stranger = make_user()
        order = make_order(user=owner)
        CouponUsage.objects.create(
            coupon=coupon,
            user=owner,
            order=order,
            discount_amount=Decimal('50.00'),
        )

        owner_api = APIClient()
        owner_api.force_authenticate(owner)
        owner_body = owner_api.get(self.url).json()
        self.assertEqual(len(owner_body), 1)
        self.assertEqual(owner_body[0]['code'], 'USED1')
        self.assertEqual(owner_body[0]['state'], 'used')
        self.assertIsNotNone(owner_body[0]['used_at'])

        stranger_api = APIClient()
        stranger_api.force_authenticate(stranger)
        stranger_body = stranger_api.get(self.url).json()
        self.assertEqual(len(stranger_body), 1)
        self.assertEqual(stranger_body[0]['code'], 'USED1')
        self.assertEqual(stranger_body[0]['state'], 'available')

        guest_body = self.api.get(self.url).json()
        self.assertEqual(len(guest_body), 1)
        self.assertEqual(guest_body[0]['state'], 'available')
