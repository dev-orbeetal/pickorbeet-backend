from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from apps.orders.models import Order
from apps.products.models import Product
from apps.shipping.models import Shipment

from .factories import ShopTestCase


class SeedDemoStoreTests(ShopTestCase):
    def run_seed(self, *args):
        call_command('seed_demo_store', *args, stdout=StringIO())

    @override_settings(DEBUG=False)
    def test_refuses_outside_debug(self):
        with self.assertRaises(CommandError):
            self.run_seed()

    @override_settings(DEBUG=True)
    def test_seed_is_idempotent_and_covers_every_courier_status(self):
        self.run_seed()
        self.run_seed()
        self.assertEqual(Product.objects.filter(sku__startswith='DEMO-').count(), 7)
        self.assertEqual(Order.objects.filter(user__email='rakib@example.com').count(), 16)
        statuses = set(Shipment.objects.values_list('status', flat=True))
        self.assertEqual(statuses, {
            'in_review', 'pending', 'hold', 'delivered', 'partial_delivered', 'cancelled', 'unknown',
            'delivered_approval_pending', 'partial_delivered_approval_pending',
            'cancelled_approval_pending', 'unknown_approval_pending',
        })
        design = Order.objects.get(order_number='PO1234567')
        self.assertEqual(str(design.total), '5657.00')
        self.assertEqual(design.shipment.tracking_code, 'SF123456789BD')

    @override_settings(DEBUG=True)
    def test_fresh_orders_rebuilds(self):
        self.run_seed()
        first = Order.objects.get(order_number='PO1234567').pk
        self.run_seed('--fresh-orders')
        self.assertNotEqual(Order.objects.get(order_number='PO1234567').pk, first)
