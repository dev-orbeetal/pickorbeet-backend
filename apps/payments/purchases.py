"""Multi-product purchase receipts: stock + one Product Buying expense."""
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.products.costing import StockError, money, record_purchase, reverse_purchase
from apps.products.models import Product, ProductVariant

from .models import Expense, PurchaseReceipt, PurchaseReceiptLine
from .serializers import next_expense_voucher_number, next_voucher_number

TWOPLACES = Decimal('0.01')
PAYMENT_METHODS = {choice for choice, _label in PurchaseReceipt.PAYMENT_METHOD_CHOICES}
DISCOUNT_TYPES = {
    PurchaseReceiptLine.DISCOUNT_NONE,
    PurchaseReceiptLine.DISCOUNT_FIXED,
    PurchaseReceiptLine.DISCOUNT_PERCENT,
}


def next_purchase_receipt_number(purchase_date):
    return next_voucher_number(PurchaseReceipt, purchase_date, 'PR', field_name='receipt_number')


def compute_line_amounts(*, quantity, unit_cost, discount_type='none', discount_value=0):
    quantity = int(quantity)
    unit_cost = money(unit_cost)
    discount_type = (discount_type or PurchaseReceiptLine.DISCOUNT_NONE).strip().lower()
    if discount_type not in DISCOUNT_TYPES:
        raise StockError('Discount must be none, fixed, or percent.')
    discount_value = money(discount_value)
    if quantity <= 0:
        raise StockError('Purchase quantity must be greater than zero.')
    if unit_cost <= 0:
        raise StockError('Enter the unit buying price for each product.')
    if discount_value < 0:
        raise StockError('Discount cannot be negative.')

    line_subtotal = money(unit_cost * quantity)
    if discount_type == PurchaseReceiptLine.DISCOUNT_NONE or discount_value == 0:
        discount_amount = Decimal('0.00')
        discount_type = PurchaseReceiptLine.DISCOUNT_NONE
        discount_value = Decimal('0.00')
    elif discount_type == PurchaseReceiptLine.DISCOUNT_PERCENT:
        if discount_value > Decimal('100.00'):
            raise StockError('Percentage discount cannot exceed 100.')
        discount_amount = money(line_subtotal * discount_value / Decimal('100'))
    else:
        if discount_value > line_subtotal:
            raise StockError('Fixed discount cannot exceed the line subtotal.')
        discount_amount = discount_value

    line_total = money(line_subtotal - discount_amount)
    if line_total <= 0:
        raise StockError('Line total after discount must be greater than zero.')
    effective_unit_cost = money(line_total / Decimal(quantity))
    return {
        'quantity': quantity,
        'unit_cost': unit_cost,
        'discount_type': discount_type,
        'discount_value': discount_value,
        'line_subtotal': line_subtotal,
        'discount_amount': discount_amount,
        'line_total': line_total,
        'effective_unit_cost': effective_unit_cost,
    }


def _normalize_location(location):
    value = (location or PurchaseReceipt.LOCATION_WAREHOUSE).strip().lower()
    allowed = {PurchaseReceipt.LOCATION_WAREHOUSE, PurchaseReceipt.LOCATION_DEALER}
    if value not in allowed:
        raise StockError('Choose warehouse or dealer as the stock location.')
    return value


def _resolve_product_variant(product_id, variant_id=None):
    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist as exc:
        raise StockError('Product not found.') from exc
    variant = None
    if variant_id:
        try:
            variant = ProductVariant.objects.get(pk=variant_id, product=product)
        except ProductVariant.DoesNotExist as exc:
            raise StockError('Variant not found for this product.') from exc
    elif product.variants.exists():
        raise StockError(f'{product.name} has variants. Select a variant for each line.')
    return product, variant


def _prepare_lines(raw_lines):
    if not raw_lines:
        raise StockError('Add at least one product to the purchase receipt.')
    prepared = []
    for index, raw in enumerate(raw_lines):
        product, variant = _resolve_product_variant(
            raw.get('product'),
            raw.get('variant') or None,
        )
        amounts = compute_line_amounts(
            quantity=raw.get('quantity'),
            unit_cost=raw.get('unit_cost'),
            discount_type=raw.get('discount_type', 'none'),
            discount_value=raw.get('discount_value', 0),
        )
        prepared.append({
            'product': product,
            'variant': variant,
            'sort_order': index,
            **amounts,
        })
    return prepared


def compute_additional_discount(lines_total, discount_type='none', discount_value=0):
    lines_total = money(lines_total)
    discount_type = (discount_type or PurchaseReceipt.DISCOUNT_NONE).strip().lower()
    discount_value = money(discount_value)
    if discount_type not in {
        PurchaseReceipt.DISCOUNT_NONE,
        PurchaseReceipt.DISCOUNT_FIXED,
        PurchaseReceipt.DISCOUNT_PERCENT,
    }:
        raise StockError('Additional discount must be none, fixed, or percent.')
    if discount_value < 0:
        raise StockError('Additional discount cannot be negative.')
    if discount_type == PurchaseReceipt.DISCOUNT_NONE or discount_value == 0 or lines_total <= 0:
        return PurchaseReceipt.DISCOUNT_NONE, Decimal('0.00'), Decimal('0.00')
    if discount_type == PurchaseReceipt.DISCOUNT_PERCENT:
        if discount_value > Decimal('100.00'):
            raise StockError('Additional percentage discount cannot exceed 100.')
        amount = money(lines_total * discount_value / Decimal('100'))
    else:
        if discount_value > lines_total:
            raise StockError('Additional discount cannot exceed the purchase total after line discounts.')
        amount = discount_value
    if amount >= lines_total:
        raise StockError('Additional discount must leave a grand total greater than zero.')
    return discount_type, discount_value, amount


def _allocate_additional_discount(prepared_lines, additional_amount):
    """Reduce line totals proportionally so inventory cost matches the paid grand total."""
    additional_amount = money(additional_amount)
    if additional_amount <= 0:
        for line in prepared_lines:
            line['stock_total'] = line['line_total']
            line['stock_unit_cost'] = line['effective_unit_cost']
        return prepared_lines

    lines_total = money(sum((line['line_total'] for line in prepared_lines), Decimal('0.00')))
    remaining_discount = additional_amount
    last_index = len(prepared_lines) - 1
    for index, line in enumerate(prepared_lines):
        if index == last_index:
            share = remaining_discount
        else:
            share = money(line['line_total'] * additional_amount / lines_total) if lines_total else Decimal('0.00')
            remaining_discount = money(remaining_discount - share)
        stock_total = money(line['line_total'] - share)
        if stock_total <= 0:
            raise StockError('Additional discount must leave each product line with a positive cost.')
        line['stock_total'] = stock_total
        line['stock_unit_cost'] = money(stock_total / Decimal(line['quantity']))
    return prepared_lines


def _totals(prepared_lines, additional_discount_type='none', additional_discount_value=0):
    total_quantity = sum(line['quantity'] for line in prepared_lines)
    subtotal = money(sum((line['line_subtotal'] for line in prepared_lines), Decimal('0.00')))
    total_discount = money(sum((line['discount_amount'] for line in prepared_lines), Decimal('0.00')))
    lines_total = money(sum((line['line_total'] for line in prepared_lines), Decimal('0.00')))
    discount_type, discount_value, additional_amount = compute_additional_discount(
        lines_total,
        discount_type=additional_discount_type,
        discount_value=additional_discount_value,
    )
    grand_total = money(lines_total - additional_amount)
    return (
        total_quantity,
        subtotal,
        total_discount,
        discount_type,
        discount_value,
        additional_amount,
        grand_total,
    )


def _description(prepared_lines, invoice_number='', payee=''):
    parts = []
    for line in prepared_lines:
        label = line['product'].name
        variant = line['variant']
        if variant is not None:
            bits = [part for part in (variant.size, variant.color) if part]
            if bits:
                label = f'{label} ({" / ".join(bits)})'
        parts.append(f'{label} × {line["quantity"]}')
    text = f'Product buying from {payee}: ' + '; '.join(parts)
    if invoice_number:
        text = f'{text}. Invoice {invoice_number}'
    return text[:2000]


def _create_expense_for_receipt(receipt, prepared_lines, user):
    expense_date = receipt.purchase_date
    primary_product = prepared_lines[0]['product'] if len(prepared_lines) == 1 else None
    description = _description(
        prepared_lines,
        invoice_number=receipt.invoice_number,
        payee=receipt.payee,
    )
    method = receipt.payment_method if receipt.payment_method in PAYMENT_METHODS else ''
    for _attempt in range(5):
        try:
            with transaction.atomic():
                return Expense.objects.create(
                    voucher_number=next_expense_voucher_number(expense_date),
                    expense_date=expense_date,
                    category='product_buying',
                    description=description,
                    comments=receipt.comments or '',
                    amount=receipt.grand_total,
                    quantity=receipt.total_quantity,
                    unit_cost=None,
                    payment_method=method,
                    payee=receipt.payee,
                    product=primary_product,
                    purchase_receipt=receipt,
                    created_by=user if getattr(user, 'is_authenticated', False) else None,
                )
        except IntegrityError:
            continue
    raise StockError('Could not assign an expense voucher number.')


def _apply_stock_lines(receipt, prepared_lines, user):
    note = f'Purchase receipt {receipt.receipt_number}'
    created_lines = []
    for prepared in prepared_lines:
        stock_total = prepared.get('stock_total', prepared['line_total'])
        stock_unit = prepared.get('stock_unit_cost', prepared['effective_unit_cost'])
        movement, _expense = record_purchase(
            product=prepared['product'],
            variant=prepared['variant'],
            quantity=prepared['quantity'],
            unit_cost=stock_unit,
            user=user,
            note=note,
            payment_method='',
            payee=receipt.payee,
            location=receipt.stock_location,
            create_voucher=False,
            total_cost=stock_total,
        )
        created_lines.append(PurchaseReceiptLine.objects.create(
            receipt=receipt,
            product=prepared['product'],
            variant=prepared['variant'],
            quantity=prepared['quantity'],
            unit_cost=prepared['unit_cost'],
            discount_type=prepared['discount_type'],
            discount_value=prepared['discount_value'],
            line_subtotal=prepared['line_subtotal'],
            discount_amount=prepared['discount_amount'],
            line_total=prepared['line_total'],
            effective_unit_cost=prepared['effective_unit_cost'],
            stock_movement=movement,
            sort_order=prepared['sort_order'],
        ))
    return created_lines


def _reverse_stock_lines(receipt, user):
    note = f'Cancelled purchase receipt {receipt.receipt_number}'
    lines = receipt.lines.select_related('product', 'variant', 'stock_movement').order_by('-sort_order')
    for line in lines:
        # The movement holds the cost that entered the pool, after any receipt discount.
        movement = line.stock_movement
        reverse_purchase(
            product=line.product,
            variant=line.variant,
            quantity=line.quantity,
            total_cost=movement.total_cost if movement else line.line_total,
            user=user,
            note=note,
            location=receipt.stock_location,
        )


def _lock_receipt(receipt):
    """Serialize edits and cancels, so two requests cannot both reverse the same stock."""
    return PurchaseReceipt.objects.select_for_update().get(pk=receipt.pk)


def create_purchase_receipt(*, purchase_date, payee, lines, stock_location='warehouse',
                            invoice_number='', comments='', payment_method='', user=None,
                            additional_discount_type='none', additional_discount_value=0,
                            idempotency_key=None):
    """Post a receipt, its stock, and its expense.

    A repeated ``idempotency_key`` returns ``(receipt, None)`` for the receipt
    already posted, and changes nothing.
    """
    if idempotency_key:
        existing = PurchaseReceipt.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            return existing, None

    payee = (payee or '').strip()
    if not payee:
        raise StockError('Dealer/seller name is required for Product Buying.')
    if payment_method and payment_method not in PAYMENT_METHODS:
        raise StockError('Choose a valid payment method.')
    location = _normalize_location(stock_location)
    prepared = _prepare_lines(lines)
    (
        total_quantity, subtotal, total_discount, discount_type, discount_value,
        additional_amount, grand_total,
    ) = _totals(
        prepared,
        additional_discount_type=additional_discount_type,
        additional_discount_value=additional_discount_value,
    )
    prepared = _allocate_additional_discount(prepared, additional_amount)

    with transaction.atomic():
        for _attempt in range(5):
            try:
                with transaction.atomic():
                    receipt = PurchaseReceipt.objects.create(
                        receipt_number=next_purchase_receipt_number(purchase_date),
                        idempotency_key=idempotency_key,
                        purchase_date=purchase_date,
                        payee=payee,
                        invoice_number=(invoice_number or '').strip(),
                        comments=(comments or '').strip(),
                        payment_method=payment_method or '',
                        stock_location=location,
                        status=PurchaseReceipt.STATUS_POSTED,
                        total_quantity=total_quantity,
                        subtotal=subtotal,
                        total_discount=total_discount,
                        additional_discount_type=discount_type,
                        additional_discount_value=discount_value,
                        additional_discount=additional_amount,
                        grand_total=grand_total,
                        created_by=user if getattr(user, 'is_authenticated', False) else None,
                    )
                break
            except IntegrityError:
                if idempotency_key:
                    existing = PurchaseReceipt.objects.filter(idempotency_key=idempotency_key).first()
                    if existing is not None:
                        return existing, None
                if _attempt == 4:
                    raise StockError('Could not assign a receipt number.')
                continue
        else:
            raise StockError('Could not assign a receipt number.')

        _apply_stock_lines(receipt, prepared, user)
        expense = _create_expense_for_receipt(receipt, prepared, user)
        return receipt, expense


@transaction.atomic
def update_purchase_receipt(receipt, *, purchase_date=None, payee=None, lines=None,
                            stock_location=None, invoice_number=None, comments=None,
                            payment_method=None, user=None,
                            additional_discount_type=None, additional_discount_value=None):
    receipt = _lock_receipt(receipt)
    if receipt.status != PurchaseReceipt.STATUS_POSTED:
        raise StockError('Only posted purchase receipts can be edited.')
    expense = getattr(receipt, 'expense', None)
    if expense is None:
        raise StockError('Purchase receipt is missing its expense voucher.')

    payee_value = (payee if payee is not None else receipt.payee) or ''
    payee_value = payee_value.strip()
    if not payee_value:
        raise StockError('Dealer/seller name is required for Product Buying.')
    method = payment_method if payment_method is not None else receipt.payment_method
    if method and method not in PAYMENT_METHODS:
        raise StockError('Choose a valid payment method.')
    location = _normalize_location(
        stock_location if stock_location is not None else receipt.stock_location
    )
    date_value = purchase_date or receipt.purchase_date
    invoice = receipt.invoice_number if invoice_number is None else (invoice_number or '').strip()
    comments_value = receipt.comments if comments is None else (comments or '').strip()
    prepared = _prepare_lines(lines if lines is not None else [
        {
            'product': line.product_id,
            'variant': line.variant_id,
            'quantity': line.quantity,
            'unit_cost': line.unit_cost,
            'discount_type': line.discount_type,
            'discount_value': line.discount_value,
        }
        for line in receipt.lines.all()
    ])
    discount_type_in = (
        additional_discount_type
        if additional_discount_type is not None
        else receipt.additional_discount_type
    )
    discount_value_in = (
        additional_discount_value
        if additional_discount_value is not None
        else receipt.additional_discount_value
    )
    (
        total_quantity, subtotal, total_discount, discount_type, discount_value,
        additional_amount, grand_total,
    ) = _totals(
        prepared,
        additional_discount_type=discount_type_in,
        additional_discount_value=discount_value_in,
    )
    prepared = _allocate_additional_discount(prepared, additional_amount)

    with transaction.atomic():
        _reverse_stock_lines(receipt, user)
        receipt.lines.all().delete()
        receipt.purchase_date = date_value
        receipt.payee = payee_value
        receipt.invoice_number = invoice
        receipt.comments = comments_value
        receipt.payment_method = method or ''
        receipt.stock_location = location
        receipt.total_quantity = total_quantity
        receipt.subtotal = subtotal
        receipt.total_discount = total_discount
        receipt.additional_discount_type = discount_type
        receipt.additional_discount_value = discount_value
        receipt.additional_discount = additional_amount
        receipt.grand_total = grand_total
        receipt.save()

        _apply_stock_lines(receipt, prepared, user)

        expense.expense_date = date_value
        expense.description = _description(prepared, invoice_number=invoice, payee=payee_value)
        expense.comments = comments_value
        expense.amount = grand_total
        expense.quantity = total_quantity
        expense.payment_method = method or ''
        expense.payee = payee_value
        expense.product = prepared[0]['product'] if len(prepared) == 1 else None
        expense.save()
        return receipt, expense


@transaction.atomic
def cancel_purchase_receipt(receipt, *, user=None):
    receipt = _lock_receipt(receipt)
    if receipt.status != PurchaseReceipt.STATUS_POSTED:
        raise StockError('This purchase receipt is already cancelled.')

    with transaction.atomic():
        _reverse_stock_lines(receipt, user)
        expense = getattr(receipt, 'expense', None)
        receipt.status = PurchaseReceipt.STATUS_CANCELLED
        receipt.cancelled_at = timezone.now()
        receipt.save(update_fields=['status', 'cancelled_at', 'updated_at'])
        if expense is not None:
            expense.delete()
        return receipt
