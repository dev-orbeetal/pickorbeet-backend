from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from apps.orders.services import change_order_status, record_online_payment
from apps.orders.tests.factories import ShopTestCase, make_order, make_product, make_user
from apps.payments.models import Expense, Payment, Refund
from apps.products.models import Category
from apps.reports.models import StockMovement


class FinanceApiTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.accountant = make_user(role='accountant', is_staff=True)
        self.seller = make_user(role='seller', is_staff=True)
        self.api = APIClient()
        self.api.force_authenticate(self.accountant)
        self.category = Category.objects.create(name='Shop Goods')
        self.product = make_product(name='Canvas Tote', category=self.category, price='500.00')

    def test_public_catalog_hides_supply_classification(self):
        detail = APIClient().get(f'/api/v1/products/{self.product.slug}/')
        self.assertEqual(detail.status_code, 200, detail.content)
        self.assertNotIn('supply_type', detail.json())
        self.assertNotIn('supplied_by', detail.json())

    def test_seller_provided_product_requires_a_seller_and_stays_off_the_public_payload(self):
        missing = self.api.post('/api/v1/products/admin/products/', {
            'name': 'Campaign Scarf',
            'category': str(self.category.id),
            'price': '100.00',
            'supply_type': 'seller_provided',
        }, format='json')
        self.assertEqual(missing.status_code, 400, missing.content)

        created = self.api.post('/api/v1/products/admin/products/', {
            'name': 'Campaign Scarf',
            'category': str(self.category.id),
            'price': '100.00',
            'supply_type': 'seller_provided',
            'supplied_by': str(self.seller.id),
        }, format='json')
        self.assertEqual(created.status_code, 201, created.content)

        public = APIClient().get(f"/api/v1/products/{created.json()['slug']}/")
        self.assertNotIn('supply_type', public.json())
        admin = self.api.get(f"/api/v1/products/admin/products/{created.json()['id']}/")
        self.assertEqual(admin.json()['supply_type'], 'seller_provided')
        self.assertEqual(admin.json()['supplied_by_name'], self.seller.full_name)

    def test_sales_summary_uses_real_order_counts(self):
        today = date.today().isoformat()
        make_order(products=[self.product], status='delivered', payment_status='paid')
        make_order(products=[make_product(category=self.category)], status='pending', payment_status='pending')
        make_order(products=[make_product(category=self.category)], status='cancelled', payment_status='pending')
        response = self.api.post('/api/v1/reports/sales/', {
            'start_date': today,
            'end_date': today,
        }, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        summary = response.json()['summary']
        self.assertEqual(summary['orders_excluding_cancelled'], 2)
        self.assertEqual(summary['completed_orders'], 1)
        self.assertEqual(summary['pending_orders'], 1)
        self.assertEqual(summary['total_sales'], 1)
        self.assertGreater(summary['total_revenue'], 0)

    def test_expense_vouchers_are_unique_and_grouped_by_product(self):
        seller_api = APIClient()
        seller_api.force_authenticate(self.seller)
        denied = seller_api.post('/api/v1/payments/admin/expenses/', {
            'expense_date': date.today().isoformat(),
            'category': 'rent',
            'description': 'Stall rent',
            'amount': '50.00',
        }, format='json')
        self.assertEqual(denied.status_code, 403)

        first = self._expense('Bags', self.product.id, '120.00')
        second = self._expense('Tea', None, '30.00')
        self.assertNotEqual(first['voucher_number'], second['voucher_number'])
        self.assertTrue(first['voucher_number'].startswith(f"EV-{date.today().strftime('%Y%m%d')}-"))

        grouped = self.api.get('/api/v1/payments/admin/expenses/by-product/')
        self.assertEqual(grouped.status_code, 200, grouped.content)
        names = {row['product_name']: row['total_amount'] for row in grouped.json()}
        self.assertEqual(names['Canvas Tote'], 120.0)
        self.assertEqual(names['Unassigned'], 30.0)

    def test_paid_order_with_a_completed_payment_is_income_once(self):
        paid = make_order(products=[self.product], payment_status='paid', status='confirmed')
        paid.total = Decimal('1000.00')
        paid.save(update_fields=['total'])
        Payment.objects.create(
            order=paid,
            payment_method='sslcommerz',
            status='completed',
            amount=Decimal('1000.00'),
        )
        cash = make_order(products=[make_product(price='500.00')], payment_status='paid', status='confirmed')
        cash.total = Decimal('500.00')
        cash.payment_method = 'cash'
        cash.save(update_fields=['total', 'payment_method'])

        refunded = make_order(products=[make_product(price='800.00')], payment_status='refunded', status='refunded')
        refunded.total = Decimal('800.00')
        refunded.save(update_fields=['total'])
        refund_payment = Payment.objects.create(
            order=refunded,
            payment_method='sslcommerz',
            status='refunded',
            amount=Decimal('800.00'),
        )
        Refund.objects.create(
            payment=refund_payment,
            amount=Decimal('800.00'),
            reason='Returned',
            status='approved',
            requested_by=self.accountant,
        )

        response = self.api.get('/api/v1/payments/admin/income/')
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        by_order = {row['reference']: row['amount'] for row in body['income']}
        cash.refresh_from_db()
        self.assertEqual(by_order[paid.order_number], 1000.0)
        self.assertEqual(by_order[cash.order_number], float(cash.total))
        self.assertNotIn(refunded.order_number, by_order)
        self.assertEqual(body['income_total'], 1000.0 + float(cash.total))
        self.assertEqual(len(body['refunds']), 1)
        self.assertFalse(body['refunds'][0]['subtracted'])
        self.assertEqual(body['net_income'], body['income_total'])

    def test_purchases_update_average_cost_and_create_one_voucher_each(self):
        self._clear_stock()
        first = self._purchase(10, '100.00', payee='Mill')
        second = self._purchase(10, '300.00')
        self.product.refresh_from_db()

        self.assertEqual(self.product.stock_quantity, 20)
        self.assertEqual(self.product.inventory_cost_value, Decimal('4000.00'))
        self.assertEqual(self.product.cost_price, Decimal('200.00'))
        self.assertNotEqual(first['voucher_number'], second['voucher_number'])
        self.assertEqual(first['quantity'], 10)
        self.assertEqual(str(first['unit_cost']), '100.00')
        self.assertEqual(Expense.objects.filter(product=self.product, category='inventory_purchase').count(), 2)
        movement = StockMovement.objects.get(product=self.product, reason='purchase', quantity=10, unit_cost=Decimal('100.00'))
        self.assertEqual(movement.expense.voucher_number, first['voucher_number'])
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Expense.objects.create(
                    voucher_number='EV-DUP-1',
                    expense_date=date.today(),
                    category='inventory_purchase',
                    description='Duplicate',
                    amount=Decimal('1.00'),
                    stock_movement=movement,
                )

        missing_cost = self.api.post(self._stock_url(), {
            'quantity': 1, 'operation': 'add', 'reason': 'purchase',
        }, format='json')
        self.assertEqual(missing_cost.status_code, 400, missing_cost.content)
        self.assertIn('unit cost', missing_cost.json()['error'].lower())

        removed = self.api.delete(f"/api/v1/payments/admin/expenses/{first['id']}/")
        self.assertEqual(removed.status_code, 400, removed.content)
        changed = self.api.patch(f"/api/v1/payments/admin/expenses/{first['id']}/", {
            'amount': '5.00',
        }, format='json')
        self.assertEqual(changed.status_code, 400, changed.content)
        self.assertTrue(Expense.objects.filter(pk=first['id']).exists())

    def test_opening_stock_is_a_purchase_and_later_edits_do_not_rewrite_it(self):
        created = self.api.post('/api/v1/products/admin/products/', {
            'name': 'Opening Scarf',
            'category': str(self.category.id),
            'price': '80.00',
            'cost_price': '25.00',
            'stock_quantity': 4,
        }, format='json')
        self.assertEqual(created.status_code, 201, created.content)
        product_id = created.json()['id']
        self.assertEqual(created.json()['stock_quantity'], 4)
        self.assertEqual(Expense.objects.filter(product_id=product_id).count(), 1)

        updated = self.api.patch(f'/api/v1/products/admin/products/{product_id}/', {
            'stock_quantity': 99,
            'cost_price': '1.00',
        }, format='json')
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertEqual(updated.json()['stock_quantity'], 4)
        self.assertEqual(updated.json()['cost_price'], '25.00')

    def test_sale_refund_and_unpaid_orders_keep_one_cost_snapshot(self):
        self._clear_stock()
        self._purchase(10, '80.00')
        order = make_order(products=[self.product], status='pending', payment_status='pending')
        change_order_status(order, 'confirmed', changed_by=self.accountant)
        change_order_status(order, 'confirmed', changed_by=self.accountant)
        order.refresh_from_db()
        item = order.items.get()
        self.product.refresh_from_db()
        self.assertTrue(order.stock_reduced)
        self.assertTrue(item.cost_applied)
        self.assertEqual(item.unit_cost, Decimal('80.00'))
        self.assertEqual(item.cost_total, Decimal('80.00'))
        self.assertEqual(self.product.stock_quantity, 9)
        self.assertEqual(self.product.inventory_cost_value, Decimal('720.00'))
        self.assertEqual(StockMovement.objects.filter(reference_order=order, reason='sale').count(), 1)

        summary = self.api.get('/api/v1/payments/admin/finance/summary/').json()
        self.assertEqual(summary['actual']['current_revenue'], '0.00')
        self.assertEqual(summary['actual']['cost_of_goods_sold'], '0.00')
        self.assertEqual(summary['awaiting_payment']['quantity'], 1)
        self.assertEqual(summary['awaiting_payment']['cost'], '80.00')

        change_order_status(order, 'delivered', changed_by=self.accountant)
        order.refresh_from_db()
        summary = self.api.get('/api/v1/payments/admin/finance/summary/').json()
        self.assertEqual(summary['actual']['current_revenue'], '500.00')
        self.assertEqual(summary['actual']['cost_of_goods_sold'], '80.00')
        self.assertEqual(summary['actual']['realized_gross_profit'], '420.00')
        self.assertEqual(summary['awaiting_payment']['quantity'], 0)
        self.assertEqual(summary['actual']['delivery_collected'], f'{order.delivery_charge:.2f}')
        self.assertEqual(summary['estimated']['selling_value'], '4500.00')
        self.assertEqual(summary['estimated']['remaining_gross_profit'], '3780.00')
        self.assertEqual(summary['estimated']['total_profit'], '4200.00')

        rows = self.api.get('/api/v1/payments/admin/finance/products/').json()
        row = next(entry for entry in rows if entry['product_id'] == str(self.product.id))
        self.assertEqual(row['quantity_purchased'], 10)
        self.assertEqual(row['quantity_sold'], 1)
        self.assertEqual(row['remaining_stock'], 9)
        self.assertEqual(row['total_sales_revenue'], '500.00')
        self.assertEqual(row['realized_profit'], '420.00')
        self.assertEqual(row['estimated_remaining_revenue'], '4500.00')
        self.assertEqual(row['estimated_remaining_profit'], '3780.00')

        change_order_status(order, 'refunded', changed_by=self.accountant)
        self.product.refresh_from_db()
        item.refresh_from_db()
        self.assertFalse(item.cost_applied)
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(self.product.inventory_cost_value, Decimal('800.00'))
        summary = self.api.get('/api/v1/payments/admin/finance/summary/').json()
        self.assertEqual(summary['actual']['current_revenue'], '0.00')
        self.assertEqual(summary['actual']['cost_of_goods_sold'], '0.00')

    def test_in_shop_sale_uses_the_same_cost_snapshot(self):
        self._clear_stock()
        self._purchase(4, '25.00')
        seller = APIClient()
        seller.force_authenticate(self.seller)
        response = seller.post('/api/v1/orders/admin/in-shop/', {
            'items': [{'product_id': str(self.product.id), 'quantity': 2}],
            'payment_method': 'cash',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 2)
        self.assertEqual(self.product.inventory_cost_value, Decimal('50.00'))
        summary = self.api.get('/api/v1/payments/admin/finance/summary/').json()
        self.assertEqual(summary['actual']['current_revenue'], '1000.00')
        self.assertEqual(summary['actual']['cost_of_goods_sold'], '50.00')
        self.assertEqual(summary['actual']['realized_gross_profit'], '950.00')

    def test_failed_payment_does_not_record_revenue_or_cost(self):
        self._clear_stock()
        self._purchase(5, '40.00')
        order = make_order(products=[self.product], status='pending', payment_status='pending')
        payment = Payment.objects.create(
            order=order,
            payment_method='sslcommerz',
            status='pending',
            amount=order.total,
        )
        record_online_payment(payment, 'failed')
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(order.payment_status, 'pending')
        self.assertFalse(order.stock_reduced)
        self.assertEqual(self.product.stock_quantity, 5)
        self.assertEqual(self.product.inventory_cost_value, Decimal('200.00'))

    def test_manual_expenses_are_counted_once_and_not_as_purchases(self):
        self._clear_stock()
        self._purchase(2, '50.00')
        shipping = self.api.post('/api/v1/payments/admin/expenses/', {
            'expense_date': date.today().isoformat(),
            'category': 'shipping',
            'description': 'Courier',
            'amount': '40.00',
        }, format='json')
        packaging = self.api.post('/api/v1/payments/admin/expenses/', {
            'expense_date': date.today().isoformat(),
            'category': 'packaging',
            'description': 'Boxes',
            'amount': '15.00',
            'product': str(self.product.id),
        }, format='json')
        self.assertEqual(shipping.status_code, 201, shipping.content)
        self.assertEqual(packaging.status_code, 201, packaging.content)

        summary = self.api.get('/api/v1/payments/admin/finance/summary/').json()
        self.assertEqual(summary['actual']['additional_expenses'], '55.00')
        self.assertEqual(summary['actual']['purchase_vouchers_total'], '100.00')
        self.assertEqual(summary['actual']['total_product_purchase_cost'], '100.00')
        self.assertEqual(summary['estimated']['total_profit'], '845.00')

        row = next(
            entry for entry in self.api.get('/api/v1/payments/admin/finance/products/').json()
            if entry['product_id'] == str(self.product.id)
        )
        self.assertEqual(row['allocated_additional_expenses'], '15.00')
        self.assertIn('15.00', row['reconciliation_note'])

        damaged = self.api.post(self._stock_url(), {
            'quantity': 1, 'operation': 'subtract', 'reason': 'damaged',
        }, format='json')
        self.assertEqual(damaged.status_code, 200, damaged.content)
        self.assertIsNone(damaged.json()['voucher_number'])
        self.product.refresh_from_db()
        self.assertEqual(self.product.shrinkage_cost, Decimal('50.00'))
        self.assertEqual(self.product.inventory_cost_value, Decimal('50.00'))
        summary = self.api.get('/api/v1/payments/admin/finance/summary/').json()
        self.assertEqual(summary['actual']['inventory_losses'], '50.00')
        self.assertEqual(summary['actual']['additional_expenses'], '55.00')

    def test_variant_purchases_share_one_cost_pool(self):
        created = self.api.post('/api/v1/products/admin/products/', {
            'name': 'Sized Shawl',
            'category': str(self.category.id),
            'price': '100.00',
            'cost_price': '40.00',
            'stock_quantity': 0,
        }, format='json')
        self.assertEqual(created.status_code, 201, created.content)
        product_id = created.json()['id']
        variant = self.api.post(f'/api/v1/products/admin/products/{product_id}/variants/', {
            'sku': 'SHAWL-M',
            'size': 'M',
            'stock_quantity': 4,
        }, format='json')
        self.assertEqual(variant.status_code, 201, variant.content)
        self.assertEqual(variant.json()['stock_quantity'], 4)

        added = self.api.post(f"/api/v1/products/admin/variants/{variant.json()['id']}/stock/", {
            'quantity': 4,
            'operation': 'add',
            'reason': 'purchase',
            'unit_cost': '80.00',
        }, format='json')
        self.assertEqual(added.status_code, 200, added.content)
        product = Category.objects.get(pk=self.category.id).products.get(pk=product_id)
        self.assertEqual(product.inventory_cost_value, Decimal('480.00'))
        self.assertEqual(product.cost_price, Decimal('60.00'))
        self.assertEqual(Expense.objects.filter(product_id=product_id).count(), 2)

        blocked = self.api.post(f'/api/v1/products/admin/products/{product_id}/stock/', {
            'quantity': 1, 'operation': 'add', 'reason': 'purchase', 'unit_cost': '10.00',
        }, format='json')
        self.assertEqual(blocked.status_code, 400, blocked.content)

    def test_public_payloads_omit_cost_fields(self):
        self._clear_stock()
        self._purchase(2, '15.00')
        order = make_order(user=self.seller, products=[self.product], status='pending')
        change_order_status(order, 'confirmed', changed_by=self.accountant)

        detail = APIClient().get(f'/api/v1/products/{self.product.slug}/')
        self.assertEqual(detail.status_code, 200, detail.content)
        body = detail.json()
        self.assertNotIn('inventory_cost_value', body)
        self.assertNotIn('opening_cost_value', body)
        self.assertNotIn('opening_quantity', body)
        self.assertNotIn('shrinkage_cost', body)
        self.assertNotIn('cost_price', body)

        customer = APIClient()
        customer.force_authenticate(self.seller)
        order_body = customer.get(f'/api/v1/orders/my-orders/{order.id}/').json()
        self.assertNotIn('unit_cost', order_body['items'][0])
        self.assertNotIn('cost_total', order_body['items'][0])
        self.assertNotIn('cost_applied', order_body['items'][0])

    def _clear_stock(self):
        self.product.stock_quantity = 0
        self.product.cost_price = None
        self.product.inventory_cost_value = Decimal('0.00')
        self.product.opening_cost_value = Decimal('0.00')
        self.product.opening_quantity = 0
        self.product.shrinkage_cost = Decimal('0.00')
        self.product.save()

    def _stock_url(self):
        return f'/api/v1/products/admin/products/{self.product.id}/stock/'

    def _purchase(self, quantity, unit_cost, payee=''):
        response = self.api.post(self._stock_url(), {
            'quantity': quantity,
            'operation': 'add',
            'reason': 'purchase',
            'unit_cost': unit_cost,
            'payment_method': 'cash',
            'payee': payee,
        }, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        voucher = response.json()['voucher_number']
        expense = Expense.objects.get(voucher_number=voucher)
        return {
            'id': str(expense.id),
            'voucher_number': voucher,
            'quantity': expense.quantity,
            'unit_cost': expense.unit_cost,
        }

    def _expense(self, description, product_id, amount):
        payload = {
            'expense_date': date.today().isoformat(),
            'category': 'inventory_purchase',
            'description': description,
            'amount': amount,
            'payment_method': 'cash',
            'payee': 'City Supplier',
        }
        if product_id:
            payload['product'] = str(product_id)
        response = self.api.post('/api/v1/payments/admin/expenses/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()
