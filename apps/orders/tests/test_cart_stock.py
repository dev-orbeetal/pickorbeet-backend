from decimal import Decimal

from rest_framework.test import APIClient

from apps.orders.models import Cart, CartItem
from apps.orders.services import MAX_DEALER_QUANTITY, change_order_status
from apps.products.models import ProductVariant

from .factories import ShopTestCase, make_product, make_user

ADDRESS = {
    'shipping_name': 'Rakibul Hasan', 'shipping_phone': '01712345678',
    'shipping_address_line1': 'House 12, Road 4',
    'shipping_division': 'Dhaka', 'shipping_city': 'Gulshan',
    'shipping_district': 'Dhaka', 'shipping_post_office': 'Gulshan Model Town',
    'shipping_postal_code': '1212',
}


class CartOwnershipTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        owner = make_user()
        self.owner_api = APIClient()
        self.owner_api.force_authenticate(owner)
        self.line = CartItem.objects.create(
            cart=Cart.objects.create(user=owner), product=make_product(stock=5), quantity=1,
        )
        self.url = f'/api/v1/orders/cart/item/{self.line.id}/'

    def assert_untouched(self, api):
        self.assertEqual(api.patch(self.url, {'quantity': 3}, format='json').status_code, 404)
        self.assertEqual(api.delete(self.url).status_code, 404)
        self.line.refresh_from_db()
        self.assertEqual(self.line.quantity, 1)

    def test_another_customer_cannot_touch_the_line(self):
        stranger = APIClient()
        stranger.force_authenticate(make_user())
        self.assert_untouched(stranger)

    def test_a_guest_cannot_touch_the_line(self):
        self.assert_untouched(APIClient())

    def test_another_guest_session_cannot_touch_a_guest_line(self):
        guest = APIClient()
        added = guest.post('/api/v1/orders/cart/add/', {'product_id': str(make_product(stock=5).id)}, format='json')
        line_id = added.json()['items'][0]['id']
        url = f'/api/v1/orders/cart/item/{line_id}/'
        self.assertEqual(APIClient().patch(url, {'quantity': 2}, format='json').status_code, 404)
        self.assertEqual(guest.patch(url, {'quantity': 2}, format='json').status_code, 200)
        self.assertEqual(guest.delete(url).status_code, 200)

    def test_the_owner_can_update_and_remove_the_line(self):
        self.assertEqual(self.owner_api.patch(self.url, {'quantity': 3}, format='json').status_code, 200)
        self.line.refresh_from_db()
        self.assertEqual(self.line.quantity, 3)
        self.assertEqual(self.owner_api.delete(self.url).status_code, 200)
        self.assertFalse(CartItem.objects.filter(id=self.line.id).exists())


class CartStockValidationTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_user()
        self.api = APIClient()
        self.api.force_authenticate(self.customer)

    def add(self, product, quantity=1, variant=None):
        body = {'product_id': str(product.id), 'quantity': quantity}
        if variant:
            body['variant_id'] = str(variant.id)
        return self.api.post('/api/v1/orders/cart/add/', body, format='json')

    def assert_rejected(self, response, message):
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()['error'], message)

    def test_add_follows_the_availability_rules(self):
        self.assertEqual(self.add(make_product(stock=5, dealer_available=False)).status_code, 200)
        self.assertEqual(self.add(make_product(stock=0, dealer_available=True)).status_code, 200)
        self.assert_rejected(
            self.add(make_product(stock=0, dealer_available=False)),
            'This product is not available',
        )

    def test_variants_are_checked_individually(self):
        product = make_product(stock=0, dealer_available=False)
        sold_out = ProductVariant.objects.create(product=product, sku='CS-OUT', size='M')
        stocked = ProductVariant.objects.create(
            product=product, sku='CS-IN', size='L', stock_quantity=2, warehouse_stock=2,
        )
        self.assert_rejected(self.add(product, variant=sold_out), 'This option is not available')
        self.assert_rejected(self.add(product), 'Choose an available option')
        self.assertEqual(self.add(product, variant=stocked).status_code, 200)

    def test_quantity_is_capped_by_stock_without_revealing_it(self):
        product = make_product(stock=3, dealer_available=False)
        response = self.add(product, quantity=4)
        self.assert_rejected(response, 'Insufficient stock')
        self.assertNotIn(b'3', response.content)

    def test_dealer_available_items_can_exceed_recorded_stock(self):
        self.assertEqual(self.add(make_product(stock=2, dealer_available=True), quantity=9).status_code, 200)

    def test_dealer_quantity_beyond_stock_has_a_ceiling(self):
        limit = f'You can order up to {MAX_DEALER_QUANTITY} of this item'
        product = make_product(stock=0, dealer_available=True)
        self.assertEqual(self.add(product, quantity=MAX_DEALER_QUANTITY).status_code, 200)
        self.assert_rejected(self.add(product), limit)
        self.assert_rejected(
            self.add(make_product(stock=2, dealer_available=True), quantity=MAX_DEALER_QUANTITY + 1),
            limit,
        )

    def test_real_stock_is_not_limited_by_the_dealer_ceiling(self):
        product = make_product(stock=150, dealer_available=True)
        self.assertEqual(self.add(product, quantity=120).status_code, 200)

    def test_repeat_adds_count_what_is_already_in_the_cart(self):
        product = make_product(stock=3, dealer_available=False)
        self.assertEqual(self.add(product, quantity=2).status_code, 200)
        self.assert_rejected(self.add(product, quantity=2), 'Insufficient stock')
        self.assertEqual(CartItem.objects.get(product=product).quantity, 2)

    def test_cart_lines_carry_a_purchase_ceiling_not_the_stock(self):
        stocked = make_product(stock=3, dealer_available=False)
        fading = make_product(stock=1, dealer_available=False)
        self.add(stocked)
        self.add(fading)
        fading.stock_quantity = 0
        fading.save(update_fields=['stock_quantity'])

        lines = {
            line['product']: line
            for line in self.api.get('/api/v1/orders/cart/').json()['items']
        }
        self.assertEqual(lines[str(stocked.id)]['max_quantity'], MAX_DEALER_QUANTITY)
        self.assertEqual(lines[str(stocked.id)]['stock_quantity'], MAX_DEALER_QUANTITY)
        self.assertFalse(lines[str(stocked.id)]['is_out_of_stock'])
        self.assertEqual(lines[str(fading.id)]['max_quantity'], 0)
        self.assertEqual(lines[str(fading.id)]['stock_quantity'], 0)
        self.assertTrue(lines[str(fading.id)]['is_out_of_stock'])

    def test_quantity_updates_are_validated(self):
        product = make_product(stock=3, dealer_available=False)
        self.add(product)
        line = CartItem.objects.get(product=product)
        url = f'/api/v1/orders/cart/item/{line.id}/'
        self.assert_rejected(self.api.patch(url, {'quantity': 4}, format='json'), 'Insufficient stock')
        line.refresh_from_db()
        self.assertEqual(line.quantity, 1)
        self.assertEqual(self.api.patch(url, {'quantity': 3}, format='json').status_code, 200)

    def test_quantity_can_always_be_lowered(self):
        product = make_product(stock=3, dealer_available=False)
        self.add(product, quantity=3)
        line = CartItem.objects.get(product=product)
        product.stock_quantity = 0
        product.save(update_fields=['stock_quantity'])
        url = f'/api/v1/orders/cart/item/{line.id}/'

        self.assertEqual(self.api.patch(url, {'quantity': 2}, format='json').status_code, 200)
        self.assert_rejected(
            self.api.patch(url, {'quantity': 3}, format='json'), 'This product is not available',
        )
        line.refresh_from_db()
        self.assertEqual(line.quantity, 2)

    def test_checkout_rejects_stock_that_ran_out_after_adding(self):
        product = make_product(name='Fading Item', stock=2, dealer_available=False)
        self.add(product, quantity=2)
        product.stock_quantity = 1
        product.save(update_fields=['stock_quantity'])

        response = self.api.post('/api/v1/orders/checkout/', ADDRESS, format='json')

        self.assert_rejected(response, 'Fading Item: Insufficient stock')
        self.assertEqual(self.customer.orders.count(), 0)
        self.assertTrue(Cart.objects.get(user=self.customer).items.exists())

    def test_stocked_item_without_a_dealer_keeps_its_cost_through_confirmation(self):
        product = make_product(
            stock=5, dealer_available=False,
            cost_price=Decimal('800.00'), inventory_cost_value=Decimal('4000.00'),
        )
        self.add(product, quantity=2)
        response = self.api.post('/api/v1/orders/checkout/', ADDRESS, format='json')
        self.assertEqual(response.status_code, 201, response.content)

        order = self.customer.orders.get()
        change_order_status(order, 'confirmed', changed_by=make_user(role='super_admin', is_staff=True))

        item = order.items.get()
        product.refresh_from_db()
        self.assertEqual(item.unit_cost, Decimal('800.00'))
        self.assertEqual(item.cost_total, Decimal('1600.00'))
        self.assertEqual(product.stock_quantity, 3)
