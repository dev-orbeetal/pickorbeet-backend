from decimal import Decimal

from django.test import TestCase

from apps.orders.tests.factories import ShopTestCase, make_product
from apps.products.costing import StockError, apply_stock_operation, transfer_stock
from apps.reports.models import StockMovement


class LocationStockTests(ShopTestCase):
    def test_purchase_lands_in_warehouse_by_default(self):
        product = make_product(name='Charger', price='1000.00', stock=0)
        apply_stock_operation(
            product=product,
            quantity=10,
            operation='add',
            reason='purchase',
            unit_cost=Decimal('200.00'),
        )
        product.refresh_from_db()
        self.assertEqual(product.warehouse_stock, 10)
        self.assertEqual(product.dealer_stock, 0)
        self.assertEqual(product.stock_quantity, 10)

    def test_transfer_moves_units_between_locations(self):
        product = make_product(name='Power bank', price='1500.00', stock=0)
        apply_stock_operation(
            product=product,
            quantity=8,
            operation='add',
            reason='purchase',
            unit_cost=Decimal('500.00'),
            location='warehouse',
        )
        result = transfer_stock(
            product=product,
            quantity=3,
            from_location='warehouse',
            to_location='dealer',
        )
        product.refresh_from_db()
        self.assertEqual(result['warehouse_stock'], 5)
        self.assertEqual(result['dealer_stock'], 3)
        self.assertEqual(product.stock_quantity, 8)
        self.assertEqual(
            StockMovement.objects.filter(product=product, reason='transfer').count(),
            2,
        )

    def test_cannot_transfer_more_than_available(self):
        product = make_product(name='Earbuds', price='900.00', stock=0)
        apply_stock_operation(
            product=product,
            quantity=2,
            operation='add',
            reason='purchase',
            unit_cost=Decimal('300.00'),
        )
        with self.assertRaises(StockError):
            transfer_stock(
                product=product,
                quantity=5,
                from_location='warehouse',
                to_location='dealer',
            )
