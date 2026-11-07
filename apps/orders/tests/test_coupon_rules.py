from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APIClient

from apps.orders.models import CartItem, Coupon, CouponUsage

from .factories import ShopTestCase, make_product, make_user
from .test_cart_stock import ADDRESS


def make_coupon(**fields):
    now = timezone.now()
    defaults = {
        'code': 'GADGET10',
        'name': 'Ten percent off gadgets',
        'discount_type': 'percentage',
        'discount_value': Decimal('10.00'),
        'minimum_order_amount': Decimal('0.00'),
        'valid_from': now - timedelta(days=1),
        'valid_until': now + timedelta(days=30),
        'usage_limit_per_user': 5,
    }
    defaults.update(fields)
    return Coupon.objects.create(**defaults)


class CouponRuleTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_user()
        self.api = APIClient()
        self.api.force_authenticate(self.customer)
        self.gadget = make_product(name='Earbuds', price='1000.00', compare_price=None)
        self.cable = make_product(name='Cable', price='2000.00', compare_price=None)
        for product in (self.gadget, self.cable):
            self.api.post('/api/v1/orders/cart/add/', {'product_id': str(product.id)}, format='json')
        self.gadget_line = CartItem.objects.get(product=self.gadget)
        self.cable_line = CartItem.objects.get(product=self.cable)

    def validate(self, code, lines=None, **extra):
        body = {'code': code, **extra}
        if lines is not None:
            body['item_ids'] = [str(line.id) for line in lines]
        return self.api.post('/api/v1/orders/coupons/validate/', body, format='json')

    def checkout(self, code, lines):
        return self.api.post('/api/v1/orders/checkout/', {
            **ADDRESS, 'coupon_code': code, 'item_ids': [str(line.id) for line in lines],
        }, format='json')

    def test_category_coupon_discounts_only_covered_lines(self):
        coupon = make_coupon()
        coupon.applicable_categories.add(self.gadget.category)

        response = self.validate('gadget10', [self.gadget_line, self.cable_line])
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Decimal(response.json()['discount_amount']), Decimal('100.00'))

        response = self.validate('GADGET10', [self.cable_line])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], "This voucher doesn't apply to the items you selected.")

    def test_product_coupon_minimum_counts_only_covered_lines(self):
        coupon = make_coupon(minimum_order_amount=Decimal('1500.00'))
        coupon.applicable_products.add(self.gadget)
        response = self.validate('GADGET10', [self.gadget_line, self.cable_line])
        self.assertEqual(response.status_code, 400)
        self.assertIn('Minimum order amount', response.json()['error'])

    def test_subtotal_from_older_apps_still_prices_shop_wide_coupons(self):
        make_coupon()
        response = self.validate('GADGET10', subtotal='3000.00')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Decimal(response.json()['discount_amount']), Decimal('300.00'))

    def test_restricted_coupon_ignores_a_client_subtotal(self):
        coupon = make_coupon()
        coupon.applicable_products.add(self.gadget)
        response = self.validate('GADGET10', subtotal='90000.00')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Decimal(response.json()['discount_amount']), Decimal('100.00'))

    def test_checkout_charges_the_server_quote_and_counts_the_use(self):
        coupon = make_coupon()
        coupon.applicable_categories.add(self.gadget.category)

        response = self.checkout('GADGET10', [self.gadget_line, self.cable_line])
        self.assertEqual(response.status_code, 201, response.content)
        order = self.customer.orders.get()
        self.assertEqual(order.discount, Decimal('100.00'))
        self.assertEqual(order.total, order.subtotal + order.delivery_charge - Decimal('100.00'))
        coupon.refresh_from_db()
        self.assertEqual(coupon.times_used, 1)
        self.assertEqual(CouponUsage.objects.get().discount_amount, Decimal('100.00'))

    def test_checkout_rejects_a_coupon_that_does_not_cover_the_lines(self):
        coupon = make_coupon()
        coupon.applicable_products.add(self.gadget)
        response = self.checkout('GADGET10', [self.cable_line])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.customer.orders.count(), 0)
        coupon.refresh_from_db()
        self.assertEqual(coupon.times_used, 0)

    def test_usage_limit_is_checked_at_checkout(self):
        make_coupon(usage_limit=1, times_used=1)
        response = self.checkout('GADGET10', [self.gadget_line])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.customer.orders.count(), 0)

    def test_wallet_prices_vouchers_for_the_selected_lines(self):
        covered = make_coupon(code='GADGETS')
        covered.applicable_categories.add(self.gadget.category)
        make_coupon(code='BIGSPEND', minimum_order_amount=Decimal('5000.00'))

        url = f'/api/v1/orders/coupons/?item_ids={self.gadget_line.id},{self.cable_line.id}'
        rows = {row['code']: row for row in self.api.get(url).json()}
        self.assertTrue(rows['GADGETS']['applies'])
        self.assertEqual(Decimal(rows['GADGETS']['estimated_discount']), Decimal('100.00'))
        self.assertFalse(rows['BIGSPEND']['applies'])
        self.assertIn('Minimum order amount', rows['BIGSPEND']['reason'])

        plain = {row['code']: row for row in self.api.get('/api/v1/orders/coupons/').json()}
        self.assertIsNone(plain['GADGETS']['applies'])
