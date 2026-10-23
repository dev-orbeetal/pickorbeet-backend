"""Rendered mail matches the branded templates, and the send hooks fire once."""
from django.core import mail
from django.test import RequestFactory, override_settings
from django.http import Http404
from rest_framework.test import APIClient

from apps.accounts.emails import (
    send_google_welcome_email,
    send_otp_email,
    send_password_changed_email,
    send_password_reset_email,
    send_welcome_email,
)
from apps.orders.emails import (
    notify_order_placed_email,
    send_abandoned_cart_email,
    send_mega_sale_email,
    send_order_confirmed_email,
)
from apps.orders.models import Cart, CartItem
from apps.orders.services import change_order_status
from core.email_preview import email_preview
from core.mailer import format_taka

from .factories import ShopTestCase, make_order, make_product, make_user


def html_of(message):
    return message.alternatives[0][0]


class FormatTests(ShopTestCase):
    def test_taka_drops_empty_paise(self):
        self.assertEqual(format_taka('1080.00'), '৳1,080')
        self.assertEqual(format_taka('60'), '৳60')
        self.assertEqual(format_taka('1080.50'), '৳1,080.50')


class AccountEmailTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user(first_name='Rakibul', email='rakib@example.com')

    def test_otp_is_six_cells_in_the_new_card(self):
        send_otp_email(self.user, '482916')
        body = html_of(mail.outbox[0])
        self.assertEqual(mail.outbox[0].subject, 'Your PickOrbeet verification code')
        for digit in '482916':
            self.assertIn(f'>{digit}</td>', body)
        self.assertIn('10 minutes', body)
        self.assertIn('#FF791F', body)
        self.assertNotIn('#8B0000', body)
        self.assertNotIn('@keyframes', body)
        self.assertIn('482916', mail.outbox[0].body)

    def test_welcome_uses_the_sheet_copy_and_hides_empty_store_badges(self):
        send_welcome_email(self.user)
        body = html_of(mail.outbox[0])
        self.assertIn('Welcome to', body)
        self.assertIn('Pick<span style="color:#FF791F;">Orbeet!</span>', body)
        self.assertIn('Wide Range of Products', body)
        self.assertIn('Secure Payments', body)
        self.assertIn('Fast Delivery', body)
        self.assertIn('Start Shopping', body)
        self.assertNotIn('App Store', body)
        self.assertNotIn('@keyframes', body)

    def test_store_badges_render_only_when_configured(self):
        with override_settings(APP_STORE_URL='https://apps.example/pickorbeet', PLAY_STORE_URL=''):
            send_welcome_email(self.user)
        body = html_of(mail.outbox[0])
        self.assertIn('https://apps.example/pickorbeet', body)
        self.assertIn('App Store', body)
        self.assertNotIn('Google Play', body)

    def test_google_signup_uses_the_welcome_card(self):
        send_google_welcome_email(self.user)
        self.assertEqual(mail.outbox[0].subject, 'Welcome to PickOrbeet')
        self.assertIn('Glad to have you with us', html_of(mail.outbox[0]))

    def test_password_reset_keeps_the_one_hour_link(self):
        url = 'https://www.pickorbeet.com/reset-password?token=abc'
        send_password_reset_email(self.user, url)
        body = html_of(mail.outbox[0])
        self.assertIn(url, body)
        self.assertIn('1 hour', body)
        self.assertIn('Reset Password', body)

    def test_password_changed_stays_in_the_same_shell(self):
        send_password_changed_email(self.user)
        body = html_of(mail.outbox[0])
        self.assertIn('Password Changed', body)
        self.assertIn('/forgot-password', body)
        self.assertNotIn('#8B0000', body)


class OrderEmailTests(ShopTestCase):
    def test_confirmation_uses_taka_totals(self):
        user = make_user()
        product = make_product(name='Oraimo Necklace Lite', price='1080.00', compare_price='1500.00')
        order = make_order(user=user, products=[product])
        send_order_confirmed_email(order)
        body = html_of(mail.outbox[0])
        self.assertIn(f'#{order.order_number}', body)
        self.assertIn('Oraimo Necklace Lite', body)
        self.assertIn('৳1,080', body)
        self.assertIn('৳1,500', body)
        self.assertIn('৳60', body)
        self.assertIn('৳1,140', body)
        self.assertIn('Order Confirmed!', body)
        self.assertNotIn('@keyframes', body)

    def test_checkout_sends_one_confirmation(self):
        customer = make_user()
        api = APIClient()
        api.force_authenticate(customer)
        product = make_product(name='Oraimo Necklace Lite', price='1080.00', compare_price='1500.00', color='Black')
        cart = Cart.objects.create(user=customer)
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        response = api.post('/api/v1/orders/checkout/', {
            'shipping_name': 'Rakibul Hasan', 'shipping_phone': '01712345678',
            'shipping_address_line1': 'House 12, Road 4', 'shipping_city': 'Dhaka',
            'shipping_district': 'Dhaka', 'shipping_postal_code': '1217',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [customer.email])
        self.assertIn('Black | Qty: 1', html_of(mail.outbox[0]))

    def test_status_mail_follows_the_shipment_and_skips_confirmation(self):
        user = make_user()
        order = make_order(user=user)
        change_order_status(order, 'confirmed')
        self.assertEqual(len(mail.outbox), 0)

        change_order_status(order, 'shipped')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('on the way', mail.outbox[0].subject)
        shipped = html_of(mail.outbox[0])
        self.assertIn('On the Way', shipped)
        self.assertIn('Track Your Order', shipped)
        self.assertNotIn('@keyframes', shipped)

        change_order_status(order, 'out_for_delivery')
        self.assertIn('out for delivery', mail.outbox[1].subject)
        self.assertIn('out for delivery', html_of(mail.outbox[1]).lower())

        change_order_status(order, 'delivered')
        delivered = html_of(mail.outbox[2])
        self.assertIn('Delivered!', delivered)
        self.assertIn('Write a Review', delivered)

    def test_in_shop_and_missing_address_do_not_send(self):
        user = make_user()
        in_shop = make_order(user=user, order_type='in_shop')
        change_order_status(in_shop, 'shipped')
        self.assertFalse(notify_order_placed_email(in_shop))
        guest = make_order(user=None, guest_email='')
        self.assertFalse(notify_order_placed_email(guest))
        self.assertEqual(len(mail.outbox), 0)

    def test_guest_checkout_mail_uses_the_guest_address(self):
        order = make_order(user=None, guest_email='guest@example.com')
        self.assertTrue(notify_order_placed_email(order))
        self.assertEqual(mail.outbox[0].to, ['guest@example.com'])
        change_order_status(order, 'shipped')
        self.assertEqual(mail.outbox[1].to, ['guest@example.com'])

    def test_abandoned_cart_and_sale_are_callable_but_not_automatic(self):
        user = make_user()
        product = make_product(price='1080.00', compare_price='1500.00')
        cart = Cart.objects.create(user=user)
        self.assertFalse(send_abandoned_cart_email(cart))
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        self.assertTrue(send_abandoned_cart_email(cart))
        body = html_of(mail.outbox[0])
        self.assertIn('Still Thinking?', body)
        self.assertIn('৳1,080', body)
        self.assertIn('Go to My Cart', body)

        stranger = Cart.objects.create(session_key='guest-session')
        CartItem.objects.create(cart=stranger, product=product, quantity=1)
        self.assertFalse(send_abandoned_cart_email(stranger))

        self.assertTrue(send_mega_sale_email('shopper@example.com', discount='60'))
        sale = html_of(mail.outbox[1])
        self.assertIn('MEGA', sale)
        self.assertIn('UP TO 60% OFF', sale)
        self.assertIn('100% Genuine Products', sale)
        self.assertEqual(len(mail.outbox), 2)


class PreviewTests(ShopTestCase):
    def test_motion_is_preview_only(self):
        request = RequestFactory().get('/emails/preview/otp/?motion=1')
        with override_settings(DEBUG=True):
            response = email_preview(request, 'otp')
        self.assertContains(response, '@keyframes mailRise')
        self.assertContains(response, 'mailFloat')
        self.assertContains(response, 'prefers-reduced-motion')

        still = RequestFactory().get('/emails/preview/order-confirmed/?motion=0')
        with override_settings(DEBUG=True):
            response = email_preview(still, 'order-confirmed')
        self.assertNotContains(response, '@keyframes')
        self.assertContains(response, '#PO783256')
        self.assertContains(response, '৳1,140')

    def test_preview_is_hidden_outside_debug_and_rejects_unknown_slugs(self):
        request = RequestFactory().get('/emails/preview/otp/')
        with override_settings(DEBUG=False):
            with self.assertRaises(Http404):
                email_preview(request, 'otp')
        with override_settings(DEBUG=True):
            with self.assertRaises(Http404):
                email_preview(request, 'not-a-template')

    def test_preview_route_lists_every_card(self):
        with override_settings(DEBUG=True):
            index = self.client.get('/emails/preview/')
            self.assertEqual(index.status_code, 200)
            for slug in (
                'welcome', 'otp', 'password-reset', 'password-changed', 'order-confirmed',
                'order-on-the-way', 'order-out-for-delivery', 'order-delivered',
                'mega-sale', 'abandoned-cart',
            ):
                self.assertContains(index, f'/emails/preview/{slug}/')
            card = self.client.get('/emails/preview/order-delivered/?motion=1')
        self.assertEqual(card.status_code, 200)
        self.assertContains(card, 'Delivered!')
        self.assertContains(card, '@keyframes mailStar')
