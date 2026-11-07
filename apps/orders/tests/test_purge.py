from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APIClient

from apps.notifications.models import Notification
from apps.orders.models import Coupon, CouponUsage, Order, OrderDeletionLog, OrderItem
from apps.orders.services import change_order_status
from apps.reports.models import DailySalesReport, StockMovement
from apps.reports.services import generate_daily_sales_report
from apps.shipping.models import Shipment
from apps.shipping.services import book_shipment
from apps.shipping.tests.fakes import FakeClient

from .factories import ShopTestCase, make_order, make_product, make_user
from .test_coupon_rules import make_coupon


class PurgeTestCase(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.admin = make_user(role='super_admin')
        self.api = APIClient()
        self.api.force_authenticate(self.admin)
        self.customer = make_user()
        self.product = make_product(price='800.00', stock=10)
        self.order = make_order(user=self.customer, products=[self.product], order_type='in_shop')
        with self.captureOnCommitCallbacks(execute=True):
            change_order_status(self.order, 'delivered')
        self.order.refresh_from_db()

    def purge(self, order=None, number=None, reason='Demo order placed while testing the shop'):
        order = order or self.order
        return self.api.post(
            f'/api/v1/orders/admin/{order.pk}/purge/',
            {'order_number': order.order_number if number is None else number, 'reason': reason},
            format='json',
        )


class PurgePermissionTests(PurgeTestCase):
    def test_only_a_super_admin_can_purge(self):
        for role in ('seller', 'accountant'):
            self.api.force_authenticate(make_user(role=role))
            self.assertEqual(self.purge().status_code, 403)
        self.assertTrue(Order.objects.filter(pk=self.order.pk).exists())

    def test_the_typed_number_and_a_reason_are_required(self):
        response = self.purge(number='ORD-WRONG')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'confirmation_mismatch')

        response = self.purge(reason='  ')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'reason_required')

        self.assertTrue(Order.objects.filter(pk=self.order.pk).exists())
        self.assertFalse(OrderDeletionLog.objects.exists())

    def test_unknown_order_is_404(self):
        response = self.api.post(
            '/api/v1/orders/admin/00000000-0000-0000-0000-000000000000/purge/',
            {'order_number': 'X', 'reason': 'Demo order'},
            format='json',
        )
        self.assertEqual(response.status_code, 404)


class PurgeTests(PurgeTestCase):
    def test_delivered_paid_order_is_deleted_with_stock_back_and_a_log(self):
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 9)
        self.assertEqual(self.order.payment_status, 'paid')
        number = self.order.order_number

        response = self.purge(number=number.lower())

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['stock_restored'])
        self.assertFalse(Order.objects.filter(pk=self.order.pk).exists())
        self.assertFalse(OrderItem.objects.filter(order_id=self.order.pk).exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertTrue(
            StockMovement.objects.filter(note=f'Order #{number} deleted permanently', quantity=1).exists()
        )

        log = OrderDeletionLog.objects.get()
        self.assertEqual(log.order_id, self.order.pk)
        self.assertEqual(log.order_number, number)
        self.assertEqual(log.order_status, 'delivered')
        self.assertEqual(log.payment_status, 'paid')
        self.assertEqual(log.total, self.order.total)
        self.assertEqual(log.deleted_by, self.admin)
        self.assertEqual(log.deleted_by_name, 'Rakibul Hasan')
        self.assertEqual(log.reason, 'Demo order placed while testing the shop')
        models = [row['model'] for row in log.snapshot]
        self.assertIn('orders.order', models)
        self.assertIn('orders.orderitem', models)
        self.assertIn('orders.orderstatushistory', models)

    def test_order_notifications_go_with_it(self):
        self.assertTrue(Notification.objects.filter(data__order_id=str(self.order.pk)).exists())
        self.assertEqual(self.purge().status_code, 200)
        self.assertFalse(Notification.objects.filter(data__order_id=str(self.order.pk)).exists())

    def test_coupon_use_count_drops(self):
        coupon = make_coupon(code='DEMO50')
        Coupon.objects.filter(pk=coupon.pk).update(times_used=2)
        CouponUsage.objects.create(coupon=coupon, user=self.customer, order=self.order, discount_amount=Decimal('50'))

        self.assertEqual(self.purge().status_code, 200)

        coupon.refresh_from_db()
        self.assertEqual(coupon.times_used, 1)
        self.assertFalse(CouponUsage.objects.filter(coupon=coupon).exists())

    def test_stored_daily_report_is_rebuilt_without_the_order(self):
        report = generate_daily_sales_report(timezone.localdate(self.order.created_at))
        self.assertEqual(report.gross_revenue, self.order.total)

        self.assertEqual(self.purge().status_code, 200)

        report = DailySalesReport.objects.get(pk=report.pk)
        self.assertEqual(report.total_orders, 0)
        self.assertEqual(report.gross_revenue, 0)

    def test_pending_order_without_stock_purges_cleanly(self):
        order = make_order(user=self.customer, products=[make_product(stock=3)])
        response = self.purge(order=order)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['stock_restored'])
        self.assertFalse(Order.objects.filter(pk=order.pk).exists())


class PurgeParcelTests(PurgeTestCase):
    def setUp(self):
        super().setUp()
        self.online = make_order(user=self.customer, products=[make_product(stock=5)])
        with self.captureOnCommitCallbacks(execute=True):
            book_shipment(self.online, make_user(role='seller'), client=FakeClient())
        self.online.refresh_from_db()

    def test_parcel_still_at_steadfast_blocks_the_purge(self):
        response = self.purge(order=self.online)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'active_parcel')
        self.assertTrue(Order.objects.filter(pk=self.online.pk).exists())
        self.assertFalse(OrderDeletionLog.objects.exists())

    def test_cancelled_parcel_is_deleted_with_the_order(self):
        Shipment.objects.filter(order=self.online).update(status='cancelled')
        response = self.purge(order=self.online)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(Shipment.objects.filter(order_id=self.online.pk).exists())
        models = [row['model'] for row in OrderDeletionLog.objects.get().snapshot]
        self.assertIn('shipping.shipment', models)
