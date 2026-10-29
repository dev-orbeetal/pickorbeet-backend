"""Current-position finance figures.

Completed sales are paid orders whose stock has been reduced. Remaining stock
is valued at current selling prices and is an estimate, not revenue.
"""
from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce

from apps.orders.models import Order, OrderItem
from apps.payments.models import Expense
from apps.products.models import Product
from apps.reports.models import StockMovement

MONEY = DecimalField(max_digits=14, decimal_places=2)
ZERO = Decimal('0.00')

OPENING_STOCK_NOTE = 'Stock valued from the cost already saved on each product.'
ESTIMATE_NOTE = (
    'Estimates value unsold stock at current selling prices. '
    'Unsold stock is not realized revenue or profit.'
)
AWAITING_NOTE = (
    'These units have left stock for orders that are not paid. '
    'They are not revenue and they are not remaining stock.'
)


def money(value):
    return Decimal(value or 0).quantize(Decimal('0.01'))


def text(value):
    return f'{money(value):.2f}'


def _line_cost():
    extended = ExpressionWrapper(
        Coalesce(F('unit_cost'), Value(ZERO)) * F('quantity'),
        output_field=MONEY,
    )
    return Coalesce(F('cost_total'), extended, output_field=MONEY)


def _sum(queryset, expression):
    return money(queryset.aggregate(total=Sum(expression))['total'])


def _completed_items():
    return OrderItem.objects.filter(order__payment_status='paid', order__stock_reduced=True)


def _awaiting_items():
    return OrderItem.objects.filter(order__stock_reduced=True).exclude(order__payment_status='paid')


def _grouped(queryset):
    buckets = {}
    items = queryset.values('product_id', 'quantity', 'total_price', 'cost_total', 'unit_cost')
    for item in items:
        product_id = item['product_id']
        if not product_id:
            continue
        bucket = buckets.setdefault(product_id, {'quantity': 0, 'revenue': ZERO, 'cost': ZERO})
        bucket['quantity'] += item['quantity'] or 0
        bucket['revenue'] += money(item['total_price'])
        if item['cost_total'] is not None:
            bucket['cost'] += money(item['cost_total'])
        elif item['unit_cost'] is not None:
            bucket['cost'] += money(Decimal(item['unit_cost']) * item['quantity'])
    return buckets


def finance_summary():
    completed_items = _completed_items()
    revenue = _sum(completed_items, 'total_price')
    cogs = _sum(completed_items, _line_cost())
    realized = revenue - cogs

    completed_orders = Order.objects.filter(payment_status='paid', stock_reduced=True)
    delivery = _sum(completed_orders, 'delivery_charge')
    discounts = _sum(completed_orders, 'discount')

    purchase_vouchers = _sum(Expense.objects.filter(category='inventory_purchase'), 'amount')
    opening = _sum(Product.objects.all(), 'opening_cost_value')
    additional = _sum(Expense.objects.exclude(category='inventory_purchase'), 'amount')
    losses = _sum(Product.objects.all(), 'shrinkage_cost')

    selling_value = ZERO
    remaining_cost = ZERO
    for product in Product.objects.prefetch_related('variants'):
        _remaining, estimated, _varies = _remaining_value(product)
        selling_value += estimated
        remaining_cost += money(product.inventory_cost_value)
    selling_value = money(selling_value)
    remaining_cost = money(remaining_cost)
    remaining_profit = selling_value - remaining_cost
    estimated_total = realized + remaining_profit - additional - losses

    awaiting_orders = Order.objects.filter(stock_reduced=True).exclude(payment_status='paid')
    awaiting_items = _awaiting_items()
    return {
        'actual': {
            'current_revenue': text(revenue),
            'cost_of_goods_sold': text(cogs),
            'realized_gross_profit': text(realized),
            'purchase_vouchers_total': text(purchase_vouchers),
            'opening_stock_cost': text(opening),
            'opening_stock_note': OPENING_STOCK_NOTE,
            'total_product_purchase_cost': text(purchase_vouchers + opening),
            'additional_expenses': text(additional),
            'inventory_losses': text(losses),
            'delivery_collected': text(delivery),
            'order_discounts': text(discounts),
        },
        'estimated': {
            'selling_value': text(selling_value),
            'remaining_cost': text(remaining_cost),
            'remaining_gross_profit': text(remaining_profit),
            'total_profit': text(estimated_total),
            'note': ESTIMATE_NOTE,
        },
        'awaiting_payment': {
            'order_count': awaiting_orders.count(),
            'quantity': int(awaiting_items.aggregate(total=Sum('quantity'))['total'] or 0),
            'merchandise_total': text(_sum(awaiting_items, 'total_price')),
            'cost': text(_sum(awaiting_items, _line_cost())),
            'note': AWAITING_NOTE,
        },
    }


def product_finance():
    products = Product.objects.prefetch_related('variants').order_by('name')
    purchased = {
        row['product_id']: int(row['qty'] or 0)
        for row in StockMovement.objects.filter(reason='purchase', quantity__gt=0)
        .values('product_id')
        .annotate(qty=Sum('quantity'))
    }
    purchase_cost = {
        row['product_id']: money(row['total'])
        for row in Expense.objects.filter(category='inventory_purchase')
        .exclude(product_id__isnull=True)
        .values('product_id')
        .annotate(total=Sum('amount'))
    }
    allocated = {
        row['product_id']: money(row['total'])
        for row in Expense.objects.exclude(category='inventory_purchase')
        .exclude(product_id__isnull=True)
        .values('product_id')
        .annotate(total=Sum('amount'))
    }
    sold = _grouped(_completed_items())
    awaiting = _grouped(_awaiting_items())

    rows = []
    for product in products:
        remaining, estimated_revenue, price_varies = _remaining_value(product)
        sold_row = sold.get(product.id, {})
        waiting_row = awaiting.get(product.id, {})
        quantity_sold = int(sold_row.get('quantity') or 0)
        revenue = money(sold_row.get('revenue') or 0)
        cogs = money(sold_row.get('cost') or 0)
        waiting_qty = int(waiting_row.get('quantity') or 0)
        quantity_purchased = int(product.opening_quantity or 0) + purchased.get(product.id, 0)
        product_purchase_cost = money(product.opening_cost_value) + purchase_cost.get(product.id, ZERO)
        remaining_cost = money(product.inventory_cost_value)
        allocated_cost = allocated.get(product.id, ZERO)
        gap = quantity_purchased - quantity_sold - remaining - waiting_qty
        rows.append({
            'product_id': str(product.id),
            'product_name': product.name,
            'quantity_purchased': quantity_purchased,
            'quantity_sold': quantity_sold,
            'remaining_stock': remaining,
            'total_purchase_cost': text(product_purchase_cost),
            'selling_price': text(product.price),
            'selling_price_varies': price_varies,
            'total_sales_revenue': text(revenue),
            'cost_of_goods_sold': text(cogs),
            'realized_profit': text(revenue - cogs),
            'estimated_remaining_revenue': text(estimated_revenue),
            'estimated_remaining_profit': text(estimated_revenue - remaining_cost),
            'allocated_additional_expenses': text(allocated_cost),
            'awaiting_payment_quantity': waiting_qty,
            'reconciliation_note': _note(gap, waiting_qty, price_varies, allocated_cost),
        })
    return rows


def _remaining_value(product):
    variants = list(product.variants.all())
    if variants:
        remaining = 0
        revenue = ZERO
        prices = set()
        for variant in variants:
            price = variant.price if variant.price is not None else product.price
            remaining += variant.stock_quantity or 0
            revenue += Decimal(price) * Decimal(variant.stock_quantity or 0)
            prices.add(money(price))
        return remaining, money(revenue), len(prices) > 1
    remaining = product.stock_quantity or 0
    return remaining, money(Decimal(product.price) * Decimal(remaining)), False


def _note(gap, awaiting_qty, price_varies, allocated_cost):
    notes = []
    if gap > 0:
        notes.append(
            f'{gap} units were removed from stock without a completed sale '
            '(losses or adjustments).'
        )
    elif gap < 0:
        notes.append(
            f'{abs(gap)} units on hand or sold were not recorded as a purchase.'
        )
    if awaiting_qty:
        notes.append(
            f'{awaiting_qty} units are on orders awaiting payment and are not counted '
            'as revenue or remaining stock.'
        )
    if price_varies:
        notes.append('Estimated revenue uses each variant’s current price.')
    if allocated_cost > 0:
        notes.append(
            f'Additional expenses linked to this product are {text(allocated_cost)}. '
            'They are counted once in the business total.'
        )
    return ' '.join(notes)
