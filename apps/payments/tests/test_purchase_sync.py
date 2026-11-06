import threading
import uuid
from datetime import date
from decimal import Decimal
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TransactionTestCase
from PIL import Image
from rest_framework.test import APIClient

from apps.orders.tests.factories import ShopTestCase, make_product, make_user
from apps.payments.models import Expense, PurchaseReceipt
from apps.payments.purchases import cancel_purchase_receipt, create_purchase_receipt
from apps.products.costing import StockError
from apps.products.models import Category, Product
from apps.reports.models import StockMovement

RECEIPTS = '/api/v1/payments/admin/purchase-receipts/'


def _png(name='proof.png'):
    buffer = BytesIO()
    Image.new('RGB', (16, 16), 'blue').save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


def _in_threads(*calls):
    """Run calls at the same moment, each on its own database connection."""
    barrier = threading.Barrier(len(calls))
    results = [None] * len(calls)

    def run(index, call):
        barrier.wait()
        try:
            results[index] = call()
        except StockError as exc:
            results[index] = exc
        finally:
            connection.close()

    threads = [
        threading.Thread(target=run, args=(index, call))
        for index, call in enumerate(calls)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


class PurchaseSyncTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.api.force_authenticate(make_user(role='accountant'))
        self.category = Category.objects.create(name='Kitchen', slug='kitchen')
        self.product = make_product(name='Steel Bottle', category=self.category, stock=0)

    def _payload(self, **fields):
        return {
            'purchase_date': date.today().isoformat(),
            'payee': 'City Wholesale',
            'stock_location': 'warehouse',
            'line_inputs': [{
                'product': str(self.product.id),
                'quantity': 10,
                'unit_cost': '100.00',
            }],
            **fields,
        }

    def _post(self, **fields):
        response = self.api.post(RECEIPTS, self._payload(**fields), format='json')
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def test_retried_submit_posts_stock_and_expense_once(self):
        key = str(uuid.uuid4())
        first = self._post(idempotency_key=key)
        retried = self._post(idempotency_key=key)

        self.assertEqual(retried['id'], first['id'])
        self.assertEqual(retried['voucher_number'], first['voucher_number'])
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(self.product.inventory_cost_value, Decimal('1000.00'))
        self.assertEqual(PurchaseReceipt.objects.count(), 1)
        self.assertEqual(Expense.objects.filter(purchase_receipt_id=first['id']).count(), 1)
        self.assertEqual(
            StockMovement.objects.filter(product=self.product, reason='purchase').count(), 1,
        )

    def test_different_keys_are_separate_purchases(self):
        self._post(idempotency_key=str(uuid.uuid4()))
        self._post(idempotency_key=str(uuid.uuid4()))
        self._post()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 30)
        self.assertEqual(PurchaseReceipt.objects.count(), 3)

    def test_rejected_submit_leaves_the_key_free_for_the_corrected_form(self):
        key = str(uuid.uuid4())
        rejected = self.api.post(RECEIPTS, self._payload(
            idempotency_key=key,
            additional_discount_type='fixed',
            additional_discount_value='5000.00',
        ), format='json')
        self.assertEqual(rejected.status_code, 400, rejected.content)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 0)

        self._post(idempotency_key=key)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)

    def test_retry_with_a_proof_keeps_the_first_upload(self):
        key = str(uuid.uuid4())
        first = self.api.post(RECEIPTS, {
            'purchase_date': date.today().isoformat(),
            'payee': 'City Wholesale',
            'idempotency_key': key,
            'line_inputs': (
                f'[{{"product": "{self.product.id}", "quantity": 1, "unit_cost": "100.00"}}]'
            ),
            'payment_proof': _png('first.png'),
        }, format='multipart')
        self.assertEqual(first.status_code, 201, first.content)
        original = Expense.objects.get(purchase_receipt_id=first.json()['id']).payment_proof.name

        again = self.api.post(RECEIPTS, {
            'purchase_date': date.today().isoformat(),
            'payee': 'City Wholesale',
            'idempotency_key': key,
            'line_inputs': (
                f'[{{"product": "{self.product.id}", "quantity": 1, "unit_cost": "100.00"}}]'
            ),
            'payment_proof': _png('second.png'),
        }, format='multipart')
        self.assertEqual(again.status_code, 201, again.content)
        self.assertEqual(
            Expense.objects.get(purchase_receipt_id=first.json()['id']).payment_proof.name,
            original,
        )

    def test_retry_of_a_cancelled_receipt_does_not_post_again(self):
        key = str(uuid.uuid4())
        first = self._post(idempotency_key=key)
        self.assertEqual(self.api.delete(f"{RECEIPTS}{first['id']}/").status_code, 204)

        retried = self._post(idempotency_key=key)
        self.assertEqual(retried['status'], 'cancelled')
        self.assertIsNone(retried['expense_id'])
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 0)

    def test_editing_a_discounted_receipt_keeps_stock_and_cost_in_step(self):
        body = self._post(additional_discount_type='fixed', additional_discount_value='50.00')
        self.product.refresh_from_db()
        self.assertEqual(self.product.inventory_cost_value, Decimal('950.00'))

        for _attempt in range(2):
            edited = self.api.patch(f"{RECEIPTS}{body['id']}/", self._payload(
                additional_discount_type='fixed',
                additional_discount_value='50.00',
            ), format='json')
            self.assertEqual(edited.status_code, 200, edited.content)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(self.product.inventory_cost_value, Decimal('950.00'))
        self.assertEqual(Expense.objects.get(purchase_receipt_id=body['id']).amount, Decimal('950.00'))

    def test_cancelling_a_discounted_receipt_returns_only_what_it_added(self):
        self._post()
        body = self._post(additional_discount_type='fixed', additional_discount_value='50.00')
        self.product.refresh_from_db()
        self.assertEqual(self.product.inventory_cost_value, Decimal('1950.00'))

        self.assertEqual(self.api.delete(f"{RECEIPTS}{body['id']}/").status_code, 204)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(self.product.inventory_cost_value, Decimal('1000.00'))

    def test_second_cancel_is_refused_and_reverses_nothing(self):
        self._post()
        body = self._post()
        receipts = f"{RECEIPTS}{body['id']}/"
        self.assertEqual(self.api.delete(receipts).status_code, 204)
        self.assertEqual(self.api.delete(receipts).status_code, 400)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)

    def test_purchase_never_creates_a_product(self):
        before = Product.objects.count()
        self._post()
        self.assertEqual(Product.objects.count(), before)

        unknown = self.api.post(RECEIPTS, self._payload(line_inputs=[{
            'product': str(uuid.uuid4()),
            'quantity': 1,
            'unit_cost': '10.00',
        }]), format='json')
        self.assertEqual(unknown.status_code, 400, unknown.content)
        self.assertEqual(Product.objects.count(), before)

    def test_admin_product_rows_show_purchased_stock(self):
        self._post()
        rows = self.api.get(
            '/api/v1/products/admin/products/', {'category': str(self.category.id)},
        ).json()['results']
        self.assertEqual(rows[0]['stock_quantity'], 10)
        self.assertEqual(rows[0]['warehouse_stock'], 10)
        categories = self.api.get('/api/v1/products/admin/categories/').json()
        category = next(row for row in categories if row['id'] == str(self.category.id))
        self.assertEqual(category['product_count'], 1)


class ConcurrentPurchaseTests(TransactionTestCase):
    """Real connections, because these races only exist across transactions."""

    def setUp(self):
        self.user = make_user(role='accountant')
        self.category = Category.objects.create(name='Kitchen', slug='kitchen')
        self.product = make_product(name='Steel Bottle', category=self.category, stock=0)

    def _create(self, key):
        return create_purchase_receipt(
            purchase_date=date.today(),
            payee='City Wholesale',
            lines=[{'product': self.product.id, 'quantity': 10, 'unit_cost': '100.00'}],
            idempotency_key=key,
            user=self.user,
        )

    def test_simultaneous_submits_post_once(self):
        key = uuid.uuid4()
        first, second = _in_threads(lambda: self._create(key), lambda: self._create(key))

        self.assertEqual(first[0].pk, second[0].pk)
        self.assertEqual(sum(1 for _receipt, expense in (first, second) if expense is None), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(PurchaseReceipt.objects.count(), 1)
        self.assertEqual(Expense.objects.count(), 1)

    def test_simultaneous_cancels_reverse_once(self):
        self._create(uuid.uuid4())
        receipt, _expense = self._create(uuid.uuid4())

        results = _in_threads(
            lambda: cancel_purchase_receipt(PurchaseReceipt.objects.get(pk=receipt.pk)),
            lambda: cancel_purchase_receipt(PurchaseReceipt.objects.get(pk=receipt.pk)),
        )

        self.assertEqual(sum(isinstance(result, StockError) for result in results), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(self.product.inventory_cost_value, Decimal('1000.00'))
