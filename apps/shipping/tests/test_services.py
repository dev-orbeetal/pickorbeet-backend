from datetime import timedelta
from decimal import Decimal

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from apps.orders.models import Order
from apps.orders.tests.factories import ShopTestCase, make_order, make_product, make_user
from apps.shipping.models import Shipment, ShipmentEvent
from apps.shipping.services import (
    ShipmentCooldown,
    ShipmentError,
    apply_courier_status,
    book_shipment,
    cod_amount_for,
    normalize_phone,
    normalize_status,
    refresh_shipment,
    status_group,
)
from apps.shipping.steadfast import SteadfastDuplicateError, SteadfastNetworkError

from .fakes import FakeClient


class HelperTests(SimpleTestCase):
    def test_phone_normalization(self):
        for raw in ['01712345678', '+880 1712 345678', '8801712345678', '1712345678', '017-1234-5678']:
            self.assertEqual(normalize_phone(raw), '01712345678', raw)

    def test_invalid_phones(self):
        for raw in ['', '12345', '01212345678', '+1 415 555 0100']:
            with self.assertRaises(ShipmentError, msg=raw):
                normalize_phone(raw)

    def test_status_groups_fold_approval_pending_variants(self):
        self.assertEqual(status_group('delivered_approval_pending'), 'delivered')
        self.assertEqual(status_group('Partial Delivered'), 'partial_delivered')
        self.assertEqual(status_group('cancelled_approval_pending'), 'cancelled')
        self.assertEqual(status_group('in_review'), 'in_review')
        self.assertEqual(status_group('something_new'), 'unknown')
        self.assertEqual(normalize_status('Canceled'), 'cancelled')


@override_settings(STEADFAST_SYNC_ORDER_STATUS=True, STEADFAST_TRACKING_URL='https://steadfast.com.bd/t/{code}')
class BookShipmentTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.staff = make_user(role='seller')
        self.product = make_product(stock=10)
        self.order = make_order(user=make_user(), products=[self.product])

    def test_booking_creates_shipment_and_ships_the_order(self):
        client = FakeClient()
        shipment = book_shipment(self.order, self.staff, note='Handle with care', client=client)

        self.assertEqual(shipment.consignment_id, '1424107')
        self.assertEqual(shipment.tracking_code, 'SF123456789BD')
        self.assertEqual(shipment.tracking_url, 'https://steadfast.com.bd/t/SF123456789BD')
        self.assertEqual(shipment.status, 'in_review')
        self.assertEqual(shipment.booked_by, self.staff)
        sent = client.created[0]
        self.assertEqual(sent['invoice'], self.order.order_number)
        self.assertEqual(sent['recipient_phone'], '01712345678')
        self.assertEqual(sent['recipient_address'], 'House 12, Road 4, Malibagh, Dhaka, 1217')
        self.assertEqual(sent['cod_amount'], 1659)  # 1599 + 60 delivery, unpaid
        self.assertEqual(sent['note'], 'Handle with care')

        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.order.order_status, 'shipped')
        self.assertIsNotNone(self.order.shipped_at)
        self.assertTrue(self.order.stock_reduced)
        self.assertEqual(self.product.stock_quantity, 9)
        self.assertEqual(shipment.events.filter(source='booking').count(), 1)

    def test_paid_orders_collect_nothing(self):
        self.order.payment_status = 'paid'
        self.order.save()
        client = FakeClient()
        book_shipment(self.order, self.staff, client=client)
        self.assertEqual(client.created[0]['cod_amount'], 0)
        self.assertEqual(cod_amount_for(self.order), 0)

    def test_booking_twice_is_rejected_without_calling_steadfast(self):
        client = FakeClient()
        book_shipment(self.order, self.staff, client=client)
        with self.assertRaises(ShipmentError) as ctx:
            book_shipment(self.order, self.staff, client=client)
        self.assertEqual(ctx.exception.code, 'already_booked')
        self.assertEqual(ctx.exception.http_status, 409)
        self.assertEqual(len(client.created), 1)
        self.assertEqual(Shipment.objects.count(), 1)

    def test_cancelled_and_in_shop_orders_cannot_be_booked(self):
        cancelled = make_order(status='cancelled')
        in_shop = make_order(order_type='in_shop', status='delivered')
        for order in (cancelled, in_shop):
            with self.assertRaises(ShipmentError):
                book_shipment(order, self.staff, client=FakeClient())

    def test_duplicate_invoice_at_steadfast_is_reported(self):
        client = FakeClient(error=SteadfastDuplicateError('The invoice has already been taken.'))
        with self.assertRaises(ShipmentError) as ctx:
            book_shipment(self.order, self.staff, client=client)
        self.assertEqual(ctx.exception.code, 'courier_duplicate_invoice')
        self.assertFalse(Shipment.objects.exists())
        self.order.refresh_from_db()
        self.assertEqual(self.order.order_status, 'pending')

    def test_bad_phone_stops_booking(self):
        self.order.shipping_phone = '12345'
        self.order.save()
        client = FakeClient()
        with self.assertRaises(ShipmentError):
            book_shipment(self.order, self.staff, client=client)
        self.assertEqual(client.created, [])

    @override_settings(STEADFAST_SYNC_ORDER_STATUS=False)
    def test_status_sync_can_be_disabled(self):
        book_shipment(self.order, self.staff, client=FakeClient())
        self.order.refresh_from_db()
        self.assertEqual(self.order.order_status, 'pending')


@override_settings(STEADFAST_SYNC_ORDER_STATUS=True)
class RefreshShipmentTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.order = make_order(user=make_user())
        self.shipment = book_shipment(self.order, make_user(role='seller'), client=FakeClient())

    def age(self, seconds):
        Shipment.objects.filter(pk=self.shipment.pk).update(
            last_checked_at=timezone.now() - timedelta(seconds=seconds))
        self.shipment.refresh_from_db()

    def test_cooldown_applies_unless_forced(self):
        with self.assertRaises(ShipmentCooldown) as ctx:
            refresh_shipment(self.shipment, client=FakeClient(status='pending'))
        self.assertTrue(1 <= ctx.exception.retry_after <= 60)

        shipment, changed = refresh_shipment(self.shipment, force=True, client=FakeClient(status='pending'))
        self.assertTrue(changed)
        self.assertEqual(shipment.status, 'pending')

    def test_delivered_marks_the_order_delivered_and_paid(self):
        self.age(120)
        refresh_shipment(self.shipment, client=FakeClient(status='delivered'))
        self.order.refresh_from_db()
        self.assertEqual(self.order.order_status, 'delivered')
        self.assertEqual(self.order.payment_status, 'paid')
        self.assertIsNotNone(self.order.delivered_at)

    def test_approval_pending_does_not_close_the_order(self):
        self.age(120)
        refresh_shipment(self.shipment, client=FakeClient(status='delivered_approval_pending'))
        self.order.refresh_from_db()
        self.assertEqual(self.order.order_status, 'shipped')

    def test_unchanged_status_records_no_event(self):
        self.age(120)
        before = ShipmentEvent.objects.count()
        _, changed = refresh_shipment(self.shipment, client=FakeClient(status='in_review'))
        self.assertFalse(changed)
        self.assertEqual(ShipmentEvent.objects.count(), before)

    def test_courier_failure_still_starts_the_cooldown(self):
        self.age(120)
        with self.assertRaises(ShipmentError) as ctx:
            refresh_shipment(self.shipment, client=FakeClient(error=SteadfastNetworkError('down')))
        self.assertEqual(ctx.exception.http_status, 503)
        self.shipment.refresh_from_db()
        with self.assertRaises(ShipmentCooldown):
            refresh_shipment(self.shipment, client=FakeClient(status='pending'))

    def test_idempotent_reports(self):
        apply_courier_status(self.shipment, 'hold', source='webhook', idempotency_key='abc')
        _, changed = apply_courier_status(self.shipment, 'pending', source='webhook', idempotency_key='abc')
        self.assertFalse(changed)
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.status, 'hold')
        self.assertEqual(ShipmentEvent.objects.filter(idempotency_key='abc').count(), 1)

    def test_order_totals_untouched_by_tracking(self):
        total = Order.objects.get(pk=self.order.pk).total
        apply_courier_status(self.shipment, 'pending', source='poll', delivery_charge=Decimal('70'))
        self.assertEqual(Order.objects.get(pk=self.order.pk).total, total)
