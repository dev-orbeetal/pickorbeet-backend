"""Weighted-average cost for purchases, sales, and other stock changes.

One product has one cost pool. Variants share it and keep their own quantities
and selling prices. Each purchase stock-in creates one expense voucher.

Stock is tracked in two locations: warehouse and dealer. ``stock_quantity`` is
always the sum of those two balances.
"""
from decimal import Decimal, ROUND_HALF_UP

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.payments.models import Expense
from apps.payments.serializers import next_expense_voucher_number
from apps.reports.models import StockMovement

from .models import Product, ProductVariant

TWOPLACES = Decimal('0.01')
PAYMENT_METHODS = {choice for choice, _label in Expense.PAYMENT_METHOD_CHOICES}
LOCATION_WAREHOUSE = StockMovement.LOCATION_WAREHOUSE
LOCATION_DEALER = StockMovement.LOCATION_DEALER
LOCATIONS = {LOCATION_WAREHOUSE, LOCATION_DEALER}


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


def _normalize_location(location):
    value = (location or LOCATION_WAREHOUSE).strip().lower()
    if value not in LOCATIONS:
        raise StockError('Choose warehouse or dealer as the stock location.')
    return value


def _location_qty(holder, location):
    if location == LOCATION_DEALER:
        return int(holder.dealer_stock or 0)
    return int(holder.warehouse_stock or 0)


def _set_location_qty(holder, location, quantity):
    quantity = max(0, int(quantity))
    if location == LOCATION_DEALER:
        holder.dealer_stock = quantity
    else:
        holder.warehouse_stock = quantity
    holder.stock_quantity = int(holder.warehouse_stock or 0) + int(holder.dealer_stock or 0)


def _sync_total(holder):
    holder.stock_quantity = int(holder.warehouse_stock or 0) + int(holder.dealer_stock or 0)


def _movement(product, variant, *, movement_type, reason, quantity, previous, new_stock,
              unit_cost, total_cost, order=None, note='', user=None, location='',
              from_location='', to_location=''):
    return StockMovement.objects.create(
        product=product,
        variant=variant,
        movement_type=movement_type,
        reason=reason,
        location=location or '',
        from_location=from_location or '',
        to_location=to_location or '',
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
        return product, None
    variant = ProductVariant.objects.select_for_update().get(pk=variant.pk, product=product)
    return product, variant


def _holder(product, variant):
    return variant if variant is not None else product


def _store_holder(product, variant):
    holder = _holder(product, variant)
    _sync_total(holder)
    if variant is not None:
        variant.save(update_fields=[
            'stock_quantity', 'warehouse_stock', 'dealer_stock', 'updated_at',
        ])
    # Product totals and cost pool are saved by `_save_pool` for product-level rows.


def _save_pool(product, *, product_stock_changed=False):
    _average(product)
    fields = ['inventory_cost_value', 'cost_price', 'shrinkage_cost']
    if product_stock_changed:
        _sync_total(product)
        fields.extend(['stock_quantity', 'warehouse_stock', 'dealer_stock'])
    product.save(update_fields=fields)


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
                    voucher_number=next_expense_voucher_number(expense_date),
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
                    payment_method='', payee='', location=LOCATION_WAREHOUSE,
                    create_voucher=True, total_cost=None):
    """Receive purchased units. Optionally create one inventory_purchase voucher.

    Pass ``create_voucher=False`` when a multi-line purchase receipt owns the
    finance voucher. ``total_cost`` overrides quantity × unit_cost when a line
    discount changes what was paid.
    """
    quantity = int(quantity)
    if quantity <= 0:
        raise StockError('Purchase quantity must be greater than zero.')
    unit_cost = money(unit_cost)
    if unit_cost <= 0:
        raise StockError('Enter the unit cost for this purchase.')
    if payment_method and payment_method not in PAYMENT_METHODS:
        raise StockError('Choose a valid payment method.')
    location = _normalize_location(location)
    total = money(total_cost) if total_cost is not None else money(unit_cost * quantity)
    if total <= 0:
        raise StockError('Purchase line total must be greater than zero.')
    # Cost pool uses what was actually paid per unit after discounts.
    pool_unit = money(total / Decimal(quantity)) if quantity else unit_cost

    with transaction.atomic():
        product, variant = _lock(product, variant)
        if product.variants.exists() and variant is None:
            raise StockError('This product has variants. Record the purchase on a variant.')
        holder = _holder(product, variant)
        previous = _location_qty(holder, location)
        new_stock = previous + quantity
        _set_location_qty(holder, location, new_stock)
        _store_holder(product, variant)
        product.inventory_cost_value = money(product.inventory_cost_value) + total
        _save_pool(product, product_stock_changed=variant is None)
        movement = _movement(
            product, variant,
            movement_type='in', reason='purchase', quantity=quantity,
            previous=previous, new_stock=new_stock,
            unit_cost=pool_unit, total_cost=total,
            note=note, user=user, location=location,
        )
        expense = None
        if create_voucher:
            expense = _create_purchase_voucher(
                product, variant, movement, quantity, pool_unit, total, user,
                payment_method, payee, note,
            )
        return movement, expense


def reverse_purchase(*, product, variant=None, quantity, total_cost, user=None, note='',
                     location=LOCATION_WAREHOUSE):
    """Undo a purchase: remove stock and reverse the cost that was added."""
    quantity = int(quantity)
    if quantity <= 0:
        raise StockError('Reverse quantity must be greater than zero.')
    total = money(total_cost)
    if total <= 0:
        raise StockError('Reverse cost must be greater than zero.')
    location = _normalize_location(location)
    unit = money(total / Decimal(quantity)) if quantity else Decimal('0.00')

    with transaction.atomic():
        product, variant = _lock(product, variant)
        if product.variants.exists() and variant is None:
            raise StockError('This product has variants. Reverse the purchase on a variant.')
        holder = _holder(product, variant)
        previous = _location_qty(holder, location)
        if previous < quantity:
            raise StockError(
                f'Cannot reverse purchase: only {previous} units remain in {location} stock '
                f'(need {quantity}). Move or restore stock first.'
            )
        new_stock = previous - quantity
        _set_location_qty(holder, location, new_stock)
        _store_holder(product, variant)
        pool = money(product.inventory_cost_value) - total
        if pool < 0:
            pool = Decimal('0.00')
        product.inventory_cost_value = pool
        _save_pool(product, product_stock_changed=variant is None)
        return _movement(
            product, variant,
            movement_type='out', reason='adjustment', quantity=-quantity,
            previous=previous, new_stock=new_stock,
            unit_cost=unit, total_cost=total,
            note=note or 'Purchase receipt reversed', user=user, location=location,
        )


def receive_at_average(*, product, variant=None, quantity, reason, note='', user=None,
                       movement_type='in', location=LOCATION_WAREHOUSE):
    """Bring units in without a purchase voucher, keeping the current average."""
    quantity = int(quantity)
    if quantity <= 0:
        return None
    location = _normalize_location(location)
    with transaction.atomic():
        product, variant = _lock(product, variant)
        if product.variants.exists() and variant is None:
            raise StockError('This product has variants. Adjust a variant instead.')
        holder = _holder(product, variant)
        on_hand = units_on_hand(product)
        pool = money(product.inventory_cost_value)
        if on_hand > 0 and pool > 0:
            unit = money(pool / Decimal(on_hand))
        else:
            unit = money(product.cost_price)
        total = money(unit * quantity)
        previous = _location_qty(holder, location)
        new_stock = previous + quantity
        _set_location_qty(holder, location, new_stock)
        _store_holder(product, variant)
        product.inventory_cost_value = pool + total
        _save_pool(product, product_stock_changed=variant is None)
        return _movement(
            product, variant,
            movement_type=movement_type, reason=reason, quantity=quantity,
            previous=previous, new_stock=new_stock,
            unit_cost=unit, total_cost=total, note=note, user=user, location=location,
        )


def remove_units(*, product, variant=None, quantity, reason, note='', user=None,
                 movement_type='out', location=LOCATION_WAREHOUSE):
    """Remove units that were not sold, and record the cost as an inventory loss."""
    quantity = int(quantity)
    if quantity <= 0:
        return None
    location = _normalize_location(location)
    with transaction.atomic():
        product, variant = _lock(product, variant)
        if product.variants.exists() and variant is None:
            raise StockError('This product has variants. Adjust a variant instead.')
        holder = _holder(product, variant)
        previous = _location_qty(holder, location)
        if previous < quantity:
            raise StockError(f'Insufficient {location} stock')
        unit, total = cost_to_remove(product, quantity)
        new_stock = previous - quantity
        _set_location_qty(holder, location, new_stock)
        _store_holder(product, variant)
        product.inventory_cost_value = money(product.inventory_cost_value) - total
        product.shrinkage_cost = money(product.shrinkage_cost) + total
        _save_pool(product, product_stock_changed=variant is None)
        return _movement(
            product, variant,
            movement_type=movement_type, reason=reason, quantity=-quantity,
            previous=previous, new_stock=new_stock,
            unit_cost=unit, total_cost=total, note=note, user=user, location=location,
        )


def apply_stock_operation(*, product, variant=None, quantity, operation, reason='adjustment',
                          note='', user=None, unit_cost=None, payment_method='', payee='',
                          location=LOCATION_WAREHOUSE):
    """Apply an inventory adjustment. Purchases also create one expense voucher."""
    quantity = int(quantity)
    if operation not in {'add', 'subtract', 'set'}:
        raise StockError('Choose a valid stock operation.')
    if operation != 'set' and quantity <= 0:
        raise StockError('Enter a quantity greater than zero.')
    if operation == 'set' and quantity < 0:
        raise StockError('Quantity cannot be negative.')
    location = _normalize_location(location)

    with transaction.atomic():
        product, variant = _lock(product, variant)
        holder = _holder(product, variant)
        current = _location_qty(holder, location)
        if operation == 'add':
            delta = quantity
        elif operation == 'subtract':
            delta = -quantity
        else:
            delta = quantity - current
        if delta == 0:
            return {
                'new_stock': holder.stock_quantity,
                'warehouse_stock': holder.warehouse_stock,
                'dealer_stock': holder.dealer_stock,
                'location_stock': current,
                'expense': None,
            }
        if delta > 0 and reason == 'purchase':
            _movement_row, expense = record_purchase(
                product=product, variant=variant, quantity=delta, unit_cost=unit_cost,
                user=user, note=note, payment_method=payment_method, payee=payee,
                location=location,
            )
            product, variant = _lock(product, variant)
            holder = _holder(product, variant)
            return {
                'new_stock': holder.stock_quantity,
                'warehouse_stock': holder.warehouse_stock,
                'dealer_stock': holder.dealer_stock,
                'location_stock': _location_qty(holder, location),
                'expense': expense,
            }
        if delta > 0:
            receive_at_average(
                product=product, variant=variant, quantity=delta, reason=reason or 'adjustment',
                note=note, user=user, movement_type='in' if operation == 'add' else 'adjustment',
                location=location,
            )
        else:
            remove_units(
                product=product, variant=variant, quantity=abs(delta),
                reason=reason or 'adjustment', note=note, user=user,
                movement_type='out' if operation == 'subtract' else 'adjustment',
                location=location,
            )
        product, variant = _lock(product, variant)
        holder = _holder(product, variant)
        return {
            'new_stock': holder.stock_quantity,
            'warehouse_stock': holder.warehouse_stock,
            'dealer_stock': holder.dealer_stock,
            'location_stock': _location_qty(holder, location),
            'expense': None,
        }


def transfer_stock(*, product, variant=None, quantity, from_location, to_location,
                   note='', user=None):
    """Move units between warehouse and dealer without changing total stock or cost."""
    quantity = int(quantity)
    if quantity <= 0:
        raise StockError('Transfer quantity must be greater than zero.')
    from_location = _normalize_location(from_location)
    to_location = _normalize_location(to_location)
    if from_location == to_location:
        raise StockError('Choose two different locations for a transfer.')

    with transaction.atomic():
        product, variant = _lock(product, variant)
        if product.variants.exists() and variant is None:
            raise StockError('This product has variants. Transfer stock on a variant.')
        holder = _holder(product, variant)
        source_previous = _location_qty(holder, from_location)
        if source_previous < quantity:
            raise StockError(f'Insufficient {from_location} stock to transfer')
        dest_previous = _location_qty(holder, to_location)
        _set_location_qty(holder, from_location, source_previous - quantity)
        _set_location_qty(holder, to_location, dest_previous + quantity)
        _store_holder(product, variant)
        if variant is None:
            _save_pool(product, product_stock_changed=True)
        else:
            # Cost pool unchanged; still refresh average metadata.
            _save_pool(product, product_stock_changed=False)

        unit = money(product.cost_price)
        total = money(unit * quantity)
        transfer_note = note or f'Transfer {quantity} from {from_location} to {to_location}'
        out_movement = _movement(
            product, variant,
            movement_type='transfer', reason='transfer', quantity=-quantity,
            previous=source_previous, new_stock=source_previous - quantity,
            unit_cost=unit, total_cost=total, note=transfer_note, user=user,
            location=from_location, from_location=from_location, to_location=to_location,
        )
        _movement(
            product, variant,
            movement_type='transfer', reason='transfer', quantity=quantity,
            previous=dest_previous, new_stock=dest_previous + quantity,
            unit_cost=unit, total_cost=total, note=transfer_note, user=user,
            location=to_location, from_location=from_location, to_location=to_location,
        )
        holder.refresh_from_db()
        return {
            'new_stock': holder.stock_quantity,
            'warehouse_stock': holder.warehouse_stock,
            'dealer_stock': holder.dealer_stock,
            'from_location': from_location,
            'to_location': to_location,
            'quantity': quantity,
            'movement_id': str(out_movement.id),
        }


def _deduct_across_locations(holder, quantity, location=None):
    """Deduct stock. With ``location``, take only from that place; otherwise
    prefer warehouse, then dealer. Returns list of (location, qty) deductions."""
    remaining = int(quantity)
    plan = []
    locations = (_normalize_location(location),) if location else (LOCATION_WAREHOUSE, LOCATION_DEALER)
    for loc in locations:
        available = _location_qty(holder, loc)
        take = min(available, remaining)
        if take:
            plan.append((loc, take))
            remaining -= take
        if remaining == 0:
            break
    if remaining > 0:
        if location:
            raise StockError(f'Insufficient {location} stock')
        raise StockError('Insufficient stock')
    for loc, take in plan:
        _set_location_qty(holder, loc, _location_qty(holder, loc) - take)
    return plan


def issue_units(*, product, variant, quantity, order, note='', user=None, location=None):
    """Take sold units out of stock and return the cost snapshot for the line."""
    quantity = int(quantity)
    if quantity <= 0:
        return Decimal('0.00'), Decimal('0.00')
    with transaction.atomic():
        product, variant = _lock(product, variant)
        holder = _holder(product, variant)
        # Cost must be taken from the pool before quantities change.
        unit, total = cost_to_remove(product, quantity)
        plan = _deduct_across_locations(holder, quantity, location=location)
        _store_holder(product, variant)
        product.inventory_cost_value = money(product.inventory_cost_value) - total
        if product.inventory_cost_value < 0:
            product.inventory_cost_value = Decimal('0.00')
        _save_pool(product, product_stock_changed=variant is None)
        for location, take in plan:
            current = _location_qty(holder, location)
            previous = current + take
            _movement(
                product, variant,
                movement_type='out', reason='sale', quantity=-take,
                previous=previous, new_stock=current,
                unit_cost=unit, total_cost=money(unit * take), order=order,
                note=note, user=user, location=location,
            )
        return unit, total


def restore_units(*, product, variant, quantity, cost_total, order, note='', user=None):
    """Put units back into warehouse. Cost is restored only when the caller passes it."""
    quantity = int(quantity)
    if quantity <= 0 or product is None:
        return
    with transaction.atomic():
        product, variant = _lock(product, variant)
        holder = _holder(product, variant)
        previous = _location_qty(holder, LOCATION_WAREHOUSE)
        new_stock = previous + quantity
        _set_location_qty(holder, LOCATION_WAREHOUSE, new_stock)
        _store_holder(product, variant)
        restored = money(cost_total)
        product.inventory_cost_value = money(product.inventory_cost_value) + restored
        _save_pool(product, product_stock_changed=variant is None)
        unit = money(restored / Decimal(quantity)) if quantity else Decimal('0.00')
        _movement(
            product, variant,
            movement_type='return', reason='return', quantity=quantity,
            previous=previous, new_stock=new_stock,
            unit_cost=unit, total_cost=restored, order=order, note=note, user=user,
            location=LOCATION_WAREHOUSE,
        )


def record_opening_cost(*, product, unit_cost, user=None, note=''):
    """Value existing on-hand/sold units that were never recorded as a purchase.

    Does not change stock quantities. Records opening quantity/cost (kept
    separate from later purchase vouchers), fills the on-hand cost pool when
    empty, and backfills sold line costs that were blank.
    """
    from django.db.models import Sum as DjSum

    from apps.orders.models import OrderItem

    unit_cost = money(unit_cost)
    if unit_cost <= 0:
        raise StockError('Enter a unit cost greater than zero.')

    with transaction.atomic():
        product, _variant = _lock(product, None)
        on_hand = units_on_hand(product)
        sold_items = list(
            OrderItem.objects.select_for_update()
            .filter(product=product, order__stock_reduced=True)
        )
        sold_qty = sum(int(item.quantity or 0) for item in sold_items)
        missing_cost_items = [
            item for item in sold_items
            if item.cost_total is None and item.unit_cost is None
        ]
        already_purchased = int(
            StockMovement.objects.filter(product=product, reason='purchase', quantity__gt=0)
            .aggregate(total=DjSum('quantity'))['total'] or 0
        )
        already_opening = int(product.opening_quantity or 0)
        recorded = already_purchased + already_opening
        needed = on_hand + sold_qty
        unrecorded = max(0, needed - recorded)

        if unrecorded <= 0 and not missing_cost_items and money(product.inventory_cost_value) > 0:
            raise StockError('Purchase cost for this product is already recorded.')
        if unrecorded <= 0 and not missing_cost_items:
            raise StockError('No units need a purchase cost on this product.')

        if unrecorded > 0:
            opening_total = money(unit_cost * Decimal(unrecorded))
            product.opening_quantity = already_opening + unrecorded
            product.opening_cost_value = money(product.opening_cost_value) + opening_total

        product.cost_price = unit_cost
        if on_hand > 0 and money(product.inventory_cost_value) <= 0:
            product.inventory_cost_value = money(unit_cost * Decimal(on_hand))
        product.save(update_fields=[
            'cost_price', 'opening_quantity', 'opening_cost_value', 'inventory_cost_value',
        ])

        for item in missing_cost_items:
            line_total = money(unit_cost * Decimal(item.quantity or 0))
            OrderItem.objects.filter(pk=item.pk).update(
                unit_cost=unit_cost,
                cost_total=line_total,
                cost_applied=True,
            )

        return {
            'product_id': str(product.id),
            'unit_cost': str(unit_cost),
            'units_recorded': unrecorded,
            'opening_quantity': product.opening_quantity,
            'opening_cost_value': str(money(product.opening_cost_value)),
            'inventory_cost_value': str(money(product.inventory_cost_value)),
            'note': note or 'Opening purchase cost recorded from Finance',
        }
