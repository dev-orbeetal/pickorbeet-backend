from decimal import Decimal

from rest_framework.test import APIClient

from apps.orders.models import Cart, CartItem, Order, OrderStatusHistory
from apps.shipping.services import book_shipment
from apps.shipping.tests.fakes import FakeClient

from .factories import ShopTestCase, make_order, make_product, make_user


class DeliveryEditTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_user()
        self.order = make_order(user=self.customer)
        self.api = APIClient()
        self.api.force_authenticate(self.customer)

    def url(self, order=None):
        return f'/api/v1/orders/my-orders/{(order or self.order).pk}/delivery/'

    def test_pending_order_can_move_outside_dhaka(self):
        self.assertTrue(self.api.get(f'/api/v1/orders/my-orders/{self.order.pk}/').json()['can_edit_delivery'])
        response = self.api.patch(self.url(), {
            'shipping_address_line1': 'Holding 7, College Road',
            'shipping_city': 'Chattogram',
            'shipping_district': 'Chattogram',
            'shipping_phone': '+880 1812-345678',
        }, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body['shipping_city'], 'Chattogram')
        self.assertEqual(body['shipping_phone'], '01812345678')
        self.assertFalse(body['is_inside_dhaka'])
        self.assertEqual(body['delivery_charge'], '120.00')
        self.assertEqual(body['total'], '1719.00')  # 1599 + 120
        self.assertTrue(OrderStatusHistory.objects.filter(
            order=self.order, note__icontains='Delivery details updated').exists())

    def test_locked_once_confirmed_or_booked(self):
        confirmed = make_order(user=self.customer, status='confirmed')
        self.assertEqual(self.api.patch(self.url(confirmed), {'shipping_city': 'Dhaka'},
                                        format='json').status_code, 400)
        book_shipment(self.order, make_user(role='seller'), client=FakeClient())
        self.order.refresh_from_db()
        self.assertEqual(self.api.patch(self.url(), {'shipping_name': 'R. Hasan'},
                                        format='json').status_code, 400)

    def test_paid_order_cannot_change_zone(self):
        self.order.payment_status = 'paid'
        self.order.save()
        blocked = self.api.patch(self.url(), {'shipping_city': 'Sylhet', 'shipping_district': 'Sylhet'},
                                 format='json')
        self.assertEqual(blocked.status_code, 400)
        allowed = self.api.patch(self.url(), {'shipping_address_line2': 'Shantinagar'}, format='json')
        self.assertEqual(allowed.status_code, 200)

    def test_other_customers_and_bad_input(self):
        intruder = APIClient()
        intruder.force_authenticate(make_user())
        self.assertEqual(intruder.patch(self.url(), {'shipping_name': 'X'}, format='json').status_code, 404)
        self.assertEqual(self.api.patch(self.url(), {'shipping_phone': '123'}, format='json').status_code, 400)
        self.assertEqual(self.api.patch(self.url(), {}, format='json').status_code, 400)


class CheckoutSelectionTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_user()
        self.api = APIClient()
        self.api.force_authenticate(self.customer)
        self.earbuds = make_product(name='boAt Airdopes 141', price='1599.00', compare_price='1999.00')
        self.powerbank = make_product(name='Mi Power Bank 20000mAh', price='2099.00', compare_price='2499.00')
        cart = Cart.objects.create(user=self.customer)
        self.line_a = CartItem.objects.create(cart=cart, product=self.earbuds, quantity=2)
        self.line_b = CartItem.objects.create(cart=cart, product=self.powerbank, quantity=1)
        self.address = {
            'shipping_name': 'Rakibul Hasan', 'shipping_phone': '01712345678',
            'shipping_address_line1': 'House 12, Road 4', 'shipping_city': 'Dhaka',
            'shipping_district': 'Dhaka', 'shipping_postal_code': '1217',
        }

    def test_cart_lines_expose_pricing_and_stock(self):
        item = self.api.get('/api/v1/orders/cart/').json()['items'][0]
        for key in ('product_slug', 'compare_price', 'discount_percentage', 'short_description',
                    'stock_quantity', 'is_out_of_stock'):
            self.assertIn(key, item)
        line = next(i for i in self.api.get('/api/v1/orders/cart/').json()['items']
                    if i['product_name'] == 'boAt Airdopes 141')
        self.assertEqual(line['discount_percentage'], 20)
        self.assertEqual(line['compare_price'], '1999.00')

    def test_only_selected_lines_are_ordered(self):
        response = self.api.post('/api/v1/orders/checkout/',
                                 {**self.address, 'item_ids': [str(self.line_b.id)]}, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        order = response.json()['order']
        self.assertEqual(order['subtotal'], '2099.00')
        self.assertEqual(len(order['items']), 1)
        self.assertEqual(order['items'][0]['compare_price'], '2499.00')
        self.assertEqual(order['items'][0]['product_slug'], self.powerbank.slug)
        self.assertEqual(order['items'][0]['discount_percentage'], 16)
        self.assertEqual(list(CartItem.objects.values_list('id', flat=True)), [self.line_a.id])

    def test_whole_cart_when_no_selection(self):
        response = self.api.post('/api/v1/orders/checkout/', self.address, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['order']['subtotal'], '5297.00')
        self.assertFalse(CartItem.objects.exists())

    def test_unknown_selection_is_rejected(self):
        other = make_product()
        stranger_cart = Cart.objects.create(session_key='someone-else')
        foreign = CartItem.objects.create(cart=stranger_cart, product=other, quantity=1)
        response = self.api.post('/api/v1/orders/checkout/',
                                 {**self.address, 'item_ids': [str(self.line_a.id), str(foreign.id)]},
                                 format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)


class StatusServiceRegressionTests(ShopTestCase):
    """The staff status endpoint behaves exactly as before the service extraction."""

    def setUp(self):
        super().setUp()
        self.staff = make_user(role='super_admin')
        self.product = make_product(stock=5)
        self.order = make_order(user=make_user(), products=[self.product])
        self.api = APIClient()
        self.api.force_authenticate(self.staff)

    def change(self, status, note=''):
        return self.api.post(f'/api/v1/orders/admin/{self.order.pk}/status/',
                             {'status': status, 'note': note}, format='json')

    def test_confirm_cancel_deliver_cycle(self):
        self.assertEqual(self.change('confirmed', 'Called the customer').status_code, 200)
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertIsNotNone(self.order.confirmed_at)
        self.assertTrue(self.order.stock_reduced)
        self.assertEqual(self.product.stock_quantity, 4)
        history = OrderStatusHistory.objects.filter(order=self.order, status='confirmed').first()
        self.assertEqual(history.note, 'Called the customer')
        self.assertEqual(history.changed_by, self.staff)

        self.change('cancelled')
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertFalse(self.order.stock_reduced)
        self.assertEqual(self.product.stock_quantity, 5)

        body = self.change('delivered').json()
        self.assertEqual(body['order_status'], 'delivered')
        self.assertEqual(body['payment_status'], 'paid')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 4)

    def test_refund_marks_payment_refunded(self):
        self.change('confirmed')
        body = self.change('refunded').json()
        self.assertEqual(body['payment_status'], 'refunded')


class MyOrdersTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_user()
        self.api = APIClient()
        self.api.force_authenticate(self.customer)
        self.shipped = make_order(user=self.customer)
        book_shipment(self.shipped, make_user(role='seller'), client=FakeClient())
        make_order(user=self.customer, status='delivered')
        make_order(user=self.customer, status='delivered')
        make_order(user=self.customer, status='cancelled')
        make_order(user=self.customer, status='refunded')
        make_order(user=make_user(), status='pending')  # someone else's

    def test_summary_counts(self):
        body = self.api.get('/api/v1/orders/my-orders/summary/').json()
        self.assertEqual(body['total'], 5)
        self.assertEqual(body['open'], 1)
        self.assertEqual(body['delivered'], 2)
        self.assertEqual(body['cancelled'], 1)
        self.assertEqual(body['returned'], 1)
        self.assertEqual(body['counts']['shipped'], 1)

    def test_status_filter_and_list_fields(self):
        delivered = self.api.get('/api/v1/orders/my-orders/?order_status=delivered').json()
        self.assertEqual(delivered['count'], 2)
        open_orders = self.api.get('/api/v1/orders/my-orders/?order_status=open').json()
        self.assertEqual(open_orders['count'], 1)
        row = open_orders['results'][0]
        self.assertEqual(row['tracking_code'], 'SF123456789BD')
        self.assertEqual(row['shipment_status_group'], 'in_review')
        self.assertEqual(row['preview_images'], [])
        everything = self.api.get('/api/v1/orders/my-orders/').json()
        self.assertEqual(everything['count'], 5)

    def test_search_and_preview_item(self):
        body = self.api.get('/api/v1/orders/my-orders/', {'search': self.shipped.order_number}).json()
        self.assertEqual(body['count'], 1)
        row = body['results'][0]
        self.assertEqual(row['extra_item_count'], 0)
        self.assertEqual(row['preview_item']['quantity'], 1)
        self.assertTrue(row['preview_item']['product_name'])
        self.assertIn('unit_price', row['preview_item'])
        self.assertIn('shipped_at', row)
        self.assertEqual(self.api.get('/api/v1/orders/my-orders/', {'search': 'no-such-order'}).json()['count'], 0)

    def test_customer_cancels_a_processing_order(self):
        order = make_order(user=self.customer, status='processing')
        response = self.api.post(f'/api/v1/orders/my-orders/{order.pk}/cancel/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['order_status'], 'cancelled')
        order.refresh_from_db()
        self.assertEqual(order.order_status, 'cancelled')

    def test_cannot_cancel_a_shipped_order(self):
        self.assertEqual(self.api.post(f'/api/v1/orders/my-orders/{self.shipped.pk}/cancel/').status_code, 400)

    def test_cannot_cancel_someone_elses_order(self):
        other = make_order(user=make_user(), status='pending')
        self.assertEqual(self.api.post(f'/api/v1/orders/my-orders/{other.pk}/cancel/').status_code, 404)

    def test_summary_requires_login(self):
        self.assertEqual(APIClient().get('/api/v1/orders/my-orders/summary/').status_code, 401)

    def test_detail_of_another_customer_is_404(self):
        other = make_order(user=make_user())
        self.assertEqual(self.api.get(f'/api/v1/orders/my-orders/{other.pk}/').status_code, 404)
