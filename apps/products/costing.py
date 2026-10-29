"""Weighted-average cost for purchases, sales, and other stock changes.

One product has one cost pool. Variants share it and keep their own quantities
and selling prices. Each purchase stock-in creates one expense voucher.
"""
from decimal import Decimal, ROUND_HALF_UP

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.payments.models import Expense
from apps.payments.serializers import next_voucher_number
from apps.reports.models import StockMovement

from .models import Product, ProductVariant

TWOPLACES = Decimal('0.01')
PAYMENT_METHODS = {choice for choice, _label in Expense.PAYMENT_METHOD_CHOICES}


class StockError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def money(value):
    return Decimal(value or 0).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def units_on_hand(product):
    """Units that share this product's cost pool.

    When a product has variants, every variant's quantity is on hand.
    Otherwise the product's own quantity is on hand.
    """
    quantities = list(product.variants.values_list('stock_quantity', flat=True))
    if quantities:
        return sum(quantities)
    return product.stock_quantity or 0


def _average(product):
    quantity = units_on_hand(product)
    pool = money(product.inventory_cost_value)
    if quantity > 0:
        product.cost_price = money(pool / Decimal(quantity))
    product.inventory_cost_value = pool


def cost_to_remove(product, quantity):
    """Cost of ``quantity`` units. The last units take the remaining pool."""
    quantity = int(quantity or 0)
    if quantity <= 0:
        return Decimal('0.00'), Decimal('0.00')
    on_hand = units_on_hand(product)
    pool = money(product.inventory_cost_value)
    if on_hand <= 0:
        unit = money(product.cost_price)
        return unit, money(unit * quantity)
    if quantity >= on_hand:
        unit = money(pool / Decimal(quantity)) if quantity else Decimal('0.00')
        return unit, pool
    unit = money(pool / Decimal(on_hand))
    total = money(unit * quantity)
    if total > pool:
        total = pool
    return unit, total


def _movement(product, variant, *, movement_type, reason, quantity, previous, new_stock,
              unit_cost, total_cost, order=None, note='', user=None):
    return StockMovement.objects.create(
        product=product,
        variant=variant,
        movement_type=movement_type,
        reason=reason,
        quantity=quantity,
        previous_stock=previous,
        new_stock=new_stock,
        unit_cost=unit_cost,
        total_cost=total_cost,
        reference_order=order,
        note=note or '',
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )


def _lock(product, variant):
    product = Product.objects.select_for_update().get(pk=product.pk)
    if variant is None:
        return product, None, product.stock_quantity
    variant = ProductVariant.objects.select_for_update().get(pk=variant.pk, product=product)
    return product, variant, variant.stock_quantity


def _store_stock(product, variant, new_stock):
    if variant is not None:
        variant.stock_quantity = new_stock
        variant.save(update_fields=['stock_quantity'])
    else:
        product.stock_quantity = new_stock


def _save_pool(product):
    _average(product)
    product.save(update_fields=['stock_quantity', 'inventory_cost_value', 'cost_price', 'shrinkage_cost'])


def _variant_label(variant):
    if variant is None:
        return ''
    parts = [part for part in (variant.size, variant.color) if part]
    return ' / '.join(parts)


def _create_purchase_voucher(product, variant, movement, quantity, unit_cost, total, user,
                             payment_method, payee, note):
    label = product.name
    variant_label = _variant_label(variant)
    if variant_label:
        label = f'{label} ({variant_label})'
    description = f'Purchase of {quantity} {label} at {unit_cost} each.'
    if note:
        description = f'{description} {note}'
    method = payment_method if payment_method in PAYMENT_METHODS else ''
    expense_date = timezone.localdate()
    for _attempt in range(5):
        try:
            with transaction.atomic():
                return Expense.objects.create(
                    voucher_number=next_voucher_number(expense_date),
                    expense_date=expense_date,
                    category='inventory_purchase',
                    description=description,
                    amount=total,
                    quantity=quantity,
                    unit_cost=unit_cost,
                    payment_method=method,
                    payee=payee or '',
                    product=product,
                    stock_movement=movement,
                    created_by=user if getattr(user, 'is_authenticated', False) else None,
                )
        except IntegrityError:
            continue
    raise StockError('Could not assign a voucher number.')


def record_purchase(*, product, variant=None, quantity, unit_cost, user=None, note='',
                    payment_method='', payee=''):
    """Receive purchased units and create the one voucher for that receipt."""
    quantity = int(quantity)
    if quantity <= 0:
        raise StockError('Purchase quantity must be greater than zero.')
    unit_cost = money(unit_cost)
    if unit_cost <= 0:
        raise StockError('Enter the unit cost for this purchase.')
    if payment_method and payment_method not in PAYMENT_METHODS:
        raise StockError('Choose a valid payment method.')

    with transaction.atomic():
        product, variant, previous = _lock(product, variant)
        if product.variants.exists() and variant is None:
            raise StockError('This product has variants. Record the purchase on a variant.')
        new_stock = previous + quantity
        _store_stock(product, variant, new_stock)
        total = money(unit_cost * quantity)
        product.inventory_cost_value = money(product.inventory_cost_value) + total
        _save_pool(product)
        movement = _movement(
            product, variant,
            movement_type='in', reason='purchase', quantity=quantity,
            previous=previous, new_stock=new_stock,
            unit_cost=unit_cost, total_cost=total,
            note=note, user=user,
        )
        expense = _create_purchase_voucher(
            product, variant, movement, quantity, unit_cost, total, user,
            payment_method, payee, note,
        )
        return movement, expense


def receive_at_average(*, product, variant=None, quantity, reason, note='', user=None, movement_type='in'):
    """Bring units in without a purchase voucher, keeping the current average."""
    quantity = int(quantity)
    if quantity <= 0:
        return None
    with transaction.atomic():
        product, variant, previous = _lock(product, variant)
        if product.variants.exists() and variant is None:
            raise StockError('This product has variants. Adjust a variant instead.')
        on_hand = units_on_hand(product)
        pool = money(product.inventory_cost_value)
        if on_hand > 0 and pool > 0:
            unit = money(pool / Decimal(on_hand))
        else:
            unit = money(product.cost_price)
        total = money(unit * quantity)
        new_stock = previous + quantity
        _store_stock(product, variant, new_stock)
        product.inventory_cost_value = pool + total
        _save_pool(product)
        return _movement(
            product, variant,
            movement_type=movement_type, reason=reason, quantity=quantity,
            previous=previous, new_stock=new_stock,
            unit_cost=unit, total_cost=total, note=note, user=user,
        )


def remove_units(*, product, variant=None, quantity, reason, note='', user=None, movement_type='out'):
    """Remove units that were not sold, and record the cost as an inventory loss."""
    quantity = int(quantity)
    if quantity <= 0:
        return None
    with transaction.atomic():
        product, variant, previous = _lock(product, variant)
        if product.variants.exists() and variant is None:
            raise StockError('This product has variants. Adjust a variant instead.')
        if previous < quantity:
            raise StockError('Insufficient stock')
        unit, total = cost_to_remove(product, quantity)
        new_stock = previous - quantity
        _store_stock(product, variant, new_stock)
        product.inventory_cost_value = money(product.inventory_cost_value) - total
        product.shrinkage_cost = money(product.shrinkage_cost) + total
        _save_pool(product)
        return _movement(
            product, variant,
            movement_type=movement_type, reason=reason, quantity=-quantity,
            previous=previous, new_stock=new_stock,
            unit_cost=unit, total_cost=total, note=note, user=user,
        )


def apply_stock_operation(*, product, variant=None, quantity, operation, reason='adjustment',
                          note='', user=None, unit_cost=None, payment_method='', payee=''):
    """Apply an inventory adjustment. Purchases also create one expense voucher."""
    quantity = int(quantity)
    if operation not in {'add', 'subtract', 'set'}:
        raise StockError('Choose a valid stock operation.')
    if operation != 'set' and quantity <= 0:
        raise StockError('Enter a quantity greater than zero.')
    if operation == 'set' and quantity < 0:
        raise StockError('Quantity cannot be negative.')

    with transaction.atomic():
        product, variant, current = _lock(product, variant)
        if operation == 'add':
            delta = quantity
        elif operation == 'subtract':
            delta = -quantity
        else:
            delta = quantity - current
        if delta == 0:
            return {'new_stock': current, 'expense': None}
        if delta > 0 and reason == 'purchase':
            _movement_row, expense = record_purchase(
                product=product, variant=variant, quantity=delta, unit_cost=unit_cost,
                user=user, note=note, payment_method=payment_method, payee=payee,
            )
            holder = variant or product
            holder.refresh_from_db()
            return {'new_stock': holder.stock_quantity, 'expense': expense}
        if delta > 0:
            receive_at_average(
                product=product, variant=variant, quantity=delta, reason=reason or 'adjustment',
                note=note, user=user, movement_type='in' if operation == 'add' else 'adjustment',
            )
        else:
            remove_units(
                product=product, variant=variant, quantity=abs(delta),
                reason=reason or 'adjustment', note=note, user=user,
                movement_type='out' if operation == 'subtract' else 'adjustment',
            )
        holder = variant or product
        holder.refresh_from_db()
        return {'new_stock': holder.stock_quantity, 'expense': None}


def issue_units(*, product, variant, quantity, order, note='', user=None):
    """Take sold units out of stock and return the cost snapshot for the line."""
    quantity = int(quantity)
    if quantity <= 0:
        return Decimal('0.00'), Decimal('0.00')
    with transaction.atomic():
        product, variant, previous = _lock(product, variant)
        unit, total = cost_to_remove(product, quantity)
        new_stock = max(0, previous - quantity)
        _store_stock(product, variant, new_stock)
        product.inventory_cost_value = money(product.inventory_cost_value) - total
        if product.inventory_cost_value < 0:
            product.inventory_cost_value = Decimal('0.00')
        _save_pool(product)
        _movement(
            product, variant,
            movement_type='out', reason='sale', quantity=-quantity,
            previous=previous, new_stock=new_stock,
            unit_cost=unit, total_cost=total, order=order, note=note, user=user,
        )
        return unit, total


def restore_units(*, product, variant, quantity, cost_total, order, note='', user=None):
    """Put units back. Cost is restored only when the caller passes the amount removed."""
    quantity = int(quantity)
    if quantity <= 0 or product is None:
        return
    with transaction.atomic():
        product, variant, previous = _lock(product, variant)
        new_stock = previous + quantity
        _store_stock(product, variant, new_stock)
        restored = money(cost_total)
        product.inventory_cost_value = money(product.inventory_cost_value) + restored
        _save_pool(product)
        unit = money(restored / Decimal(quantity)) if quantity else Decimal('0.00')
        _movement(
            product, variant,
            movement_type='return', reason='return', quantity=quantity,
            previous=previous, new_stock=new_stock,
            unit_cost=unit, total_cost=restored, order=order, note=note, user=user,
        )
