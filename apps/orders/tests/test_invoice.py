import time
from smtplib import SMTPException
from unittest import mock

from django.core import mail
from django.test import override_settings
from rest_framework.test import APIClient

from apps.orders.emails import send_order_status_email
from apps.orders.invoice import (
    APP_LINK_SECONDS,
    build_invoice_pdf,
    invoice_available,
    invoice_token,
    order_id_from_token,
)
from apps.orders.models import Order
from apps.orders.services import change_order_status
from apps.shipping.services import book_shipment
from apps.shipping.tests.fakes import FakeClient

from .factories import ShopTestCase, make_order, make_product, make_user


def pdf_attachments(message):
    return [item for item in message.attachments if item[2] == 'application/pdf']


@override_settings(API_PUBLIC_URL='https://api.example.com')
class InvoiceTestCase(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_user(first_name='রাকিব', last_name='হাসান')
        product = make_product(name='Oraimo FreePods 4', price='1599.00')
        self.order = make_order(user=self.customer, products=[product])
        Order.objects.filter(pk=self.order.pk).update(
            shipping_name='রাকিবুল হাসান', coupon_code='SAVE50', discount='50.00')
        self.order.refresh_from_db()

    def ship(self, order=None):
        order = order or self.order
        with self.captureOnCommitCallbacks(execute=True):
            book_shipment(order, make_user(role='seller'), client=FakeClient())
        order.refresh_from_db()
        return order


class InvoicePdfTests(InvoiceTestCase):
    def test_pdf_renders_bangla_names_and_taka(self):
        self.ship()
        pdf = build_invoice_pdf(self.order)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreater(len(pdf), 5000)
        self.assertIn(b'NotoSansBengali', pdf)

    def test_invoice_is_only_ready_after_shipping(self):
        self.assertFalse(invoice_available(self.order))
        self.ship()
        self.assertTrue(invoice_available(self.order))
        in_shop = make_order(user=self.customer, order_type='in_shop', status='delivered')
        self.assertFalse(invoice_available(in_shop))


class InvoiceEmailTests(InvoiceTestCase):
    def test_shipping_mail_attaches_the_invoice_once(self):
        self.ship()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('on the way', mail.outbox[0].subject)
        attachments = pdf_attachments(mail.outbox[0])
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0][0], f'PickOrbeet-invoice-{self.order.order_number}.pdf')
        self.assertTrue(attachments[0][1].startswith(b'%PDF'))
        self.assertIn('Download invoice', mail.outbox[0].alternatives[0][0])
        self.assertIn('https://api.example.com/api/v1/orders/invoice/', mail.outbox[0].alternatives[0][0])
        self.assertIsNotNone(self.order.invoice_emailed_at)

        for status in ('out_for_delivery', 'delivered'):
            with self.captureOnCommitCallbacks(execute=True):
                change_order_status(self.order, status)
        self.assertEqual(len(mail.outbox), 3)
        self.assertEqual([len(pdf_attachments(message)) for message in mail.outbox], [1, 0, 0])

    def test_delivery_mail_carries_it_when_shipping_was_skipped(self):
        Order.objects.filter(pk=self.order.pk).update(order_status='processing')
        with self.captureOnCommitCallbacks(execute=True):
            change_order_status(self.order, 'delivered')
        self.assertEqual(len(pdf_attachments(mail.outbox[0])), 1)

    def test_a_failed_send_releases_the_invoice_for_the_retry(self):
        Order.objects.filter(pk=self.order.pk).update(order_status='shipped')
        self.order.refresh_from_db()
        with mock.patch('core.mailer.EmailMultiAlternatives.send', side_effect=SMTPException('down')):
            with self.assertRaises(SMTPException):
                send_order_status_email(self.order)
        self.order.refresh_from_db()
        self.assertIsNone(self.order.invoice_emailed_at)

        send_order_status_email(self.order)
        self.assertEqual(len(pdf_attachments(mail.outbox[0])), 1)

    def test_mail_still_goes_out_when_the_pdf_fails(self):
        with mock.patch('apps.orders.invoice.build_invoice_pdf', side_effect=RuntimeError('font missing')):
            self.ship()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(pdf_attachments(mail.outbox[0]), [])


class InvoiceLinkTests(InvoiceTestCase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()

    def test_signed_link_downloads_the_pdf(self):
        self.ship()
        response = self.api.get(f'/api/v1/orders/invoice/{invoice_token(self.order, 60)}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_expired_or_tampered_links_are_refused(self):
        token = invoice_token(self.order, 60)
        self.assertEqual(order_id_from_token(token), str(self.order.pk))
        with mock.patch('apps.orders.invoice.time.time', return_value=time.time() + 61):
            self.assertIsNone(order_id_from_token(token))
        self.assertIsNone(order_id_from_token(token[:-2] + 'xx'))
        self.assertEqual(self.api.get('/api/v1/orders/invoice/not-a-token/').status_code, 404)

    def test_customer_gets_a_ten_minute_link_for_their_own_shipped_order(self):
        url = f'/api/v1/orders/my-orders/{self.order.pk}/invoice/link/'
        self.api.force_authenticate(self.customer)
        self.assertEqual(self.api.post(url).json()['code'], 'invoice_not_ready')

        self.ship()
        response = self.api.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['expires_in'], APP_LINK_SECONDS)
        self.assertTrue(response.json()['url'].startswith('https://api.example.com/api/v1/orders/invoice/'))

        self.api.force_authenticate(make_user())
        self.assertEqual(self.api.post(url).status_code, 404)

    def test_order_detail_says_when_the_invoice_is_ready(self):
        self.api.force_authenticate(self.customer)
        url = f'/api/v1/orders/my-orders/{self.order.pk}/'
        self.assertFalse(self.api.get(url).json()['invoice_available'])
        self.ship()
        self.assertTrue(self.api.get(url).json()['invoice_available'])

    def test_staff_can_download_and_resend(self):
        self.ship()
        mail.outbox.clear()
        staff = make_user(role='seller')
        self.api.force_authenticate(staff)

        link = self.api.post(f'/api/v1/orders/admin/{self.order.pk}/invoice/link/')
        self.assertEqual(link.status_code, 200)

        response = self.api.post(f'/api/v1/orders/admin/{self.order.pk}/invoice/resend/')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(mail.outbox[0].subject, f'Invoice for order #{self.order.order_number}')
        self.assertEqual(len(pdf_attachments(mail.outbox[0])), 1)

        self.api.force_authenticate(self.customer)
        self.assertEqual(self.api.post(f'/api/v1/orders/admin/{self.order.pk}/invoice/resend/').status_code, 403)

    def test_resend_needs_a_customer_email(self):
        guest = make_order(user=None, guest_email='', status='shipped')
        self.api.force_authenticate(make_user(role='seller'))
        response = self.api.post(f'/api/v1/orders/admin/{guest.pk}/invoice/resend/')
        self.assertEqual(response.json()['code'], 'no_email')
