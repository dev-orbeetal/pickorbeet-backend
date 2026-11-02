"""Current-position finance figures.

Completed sales are paid orders whose stock has been reduced. Remaining stock
is valued at current selling prices and is an estimate, not revenue.
"""
from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce

from apps.orders.models import Order, OrderItem
from apps.payments.models import Expense, ManualIncome
from apps.products.models import Product
from apps.reports.models import StockMovement

# Purchase-linked expense categories (counted with product purchase cost, not "additional").
PURCHASE_CATEGORIES = ('inventory_purchase', 'product_buying')

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


def _sale_channel(order_type):
    """Admin panel / external sales are tracked separately — selling price often differs."""
    if order_type == 'external':
        return 'admin'
    return 'storefront'


def _grouped(queryset, *, by_channel=False):
    buckets = {}
    items = queryset.values(
        'product_id', 'quantity', 'total_price', 'cost_total', 'unit_cost', 'order__order_type',
    )
    for item in items:
        product_id = item['product_id']
        if not product_id:
            continue
        if by_channel:
            key = (product_id, _sale_channel(item.get('order__order_type')))
        else:
            key = product_id
        bucket = buckets.setdefault(key, {'quantity': 0, 'revenue': ZERO, 'cost': ZERO})
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

    purchase_vouchers = _sum(
        Expense.objects.filter(category__in=PURCHASE_CATEGORIES), 'amount',
    )
    opening = _sum(Product.objects.all(), 'opening_cost_value')
    additional = _sum(
        Expense.objects.exclude(category__in=PURCHASE_CATEGORIES), 'amount',
    )
    losses = _sum(Product.objects.all(), 'shrinkage_cost')
    manual_income = _sum(ManualIncome.objects.all(), 'amount')

    selling_value = ZERO
    remaining_cost = ZERO
    for product in Product.objects.prefetch_related('variants'):
        _remaining, estimated, _varies = _remaining_value(product)
        selling_value += estimated
        remaining_cost += money(product.inventory_cost_value)
    selling_value = money(selling_value)
    remaining_cost = money(remaining_cost)
    remaining_profit = selling_value - remaining_cost
    estimated_total = realized + remaining_profit - additional - losses + manual_income

    awaiting_orders = Order.objects.filter(stock_reduced=True).exclude(payment_status='paid')
    awaiting_items = _awaiting_items()
    return {
        'actual': {
            'current_revenue': text(revenue),
            'manual_income_total': text(manual_income),
            'total_income': text(revenue + manual_income),
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
    """Per-product profit from purchase vouchers and completed sales.

    Each product has a primary Storefront row (purchases, remaining stock, online
    sales). Admin-panel / external sales get a second row so custom prices are not
    blended with catalog storefront prices.
    """
    products = Product.objects.prefetch_related('variants').order_by('name')
    purchased = {
        row['product_id']: int(row['qty'] or 0)
        for row in StockMovement.objects.filter(reason='purchase', quantity__gt=0)
        .values('product_id')
        .annotate(qty=Sum('quantity'))
    }
    purchase_cost = {
        row['product_id']: money(row['total'])
        for row in Expense.objects.filter(category__in=PURCHASE_CATEGORIES)
        .exclude(product_id__isnull=True)
        .values('product_id')
        .annotate(total=Sum('amount'))
    }
    allocated = {
        row['product_id']: money(row['total'])
        for row in Expense.objects.exclude(category__in=PURCHASE_CATEGORIES)
        .exclude(product_id__isnull=True)
        .values('product_id')
        .annotate(total=Sum('amount'))
    }
    sold_by_channel = _grouped(_completed_items(), by_channel=True)
    sold_total = _grouped(_completed_items())
    awaiting = _grouped(_awaiting_items())

    rows = []
    for product in products:
        remaining, estimated_revenue, price_varies = _remaining_value(product)
        storefront = sold_by_channel.get((product.id, 'storefront'), {})
        admin_sale = sold_by_channel.get((product.id, 'admin'), {})
        all_sold = sold_total.get(product.id, {})
        waiting_row = awaiting.get(product.id, {})

        quantity_sold_all = int(all_sold.get('quantity') or 0)
        waiting_qty = int(waiting_row.get('quantity') or 0)
        quantity_purchased = int(product.opening_quantity or 0) + purchased.get(product.id, 0)
        product_purchase_cost = money(product.opening_cost_value) + purchase_cost.get(product.id, ZERO)
        remaining_cost = money(product.inventory_cost_value)
        allocated_cost = allocated.get(product.id, ZERO)
        gap = quantity_purchased - quantity_sold_all - remaining - waiting_qty
        suggested = money(product.cost_price) if product.cost_price and product.cost_price > 0 else None
        all_cogs = money(all_sold.get('cost') or 0)
        needs_cost = (
            gap < 0
            or (remaining > 0 and remaining_cost <= 0)
            or (quantity_sold_all > 0 and all_cogs <= 0)
        )

        channel_rows = [('storefront', storefront, True)]
        if int(admin_sale.get('quantity') or 0) > 0:
            channel_rows.append(('admin', admin_sale, False))

        for channel, sold_row, is_primary in channel_rows:
            quantity_sold = int(sold_row.get('quantity') or 0)
            revenue = money(sold_row.get('revenue') or 0)
            cogs = money(sold_row.get('cost') or 0)
            avg_sell = (
                money(revenue / Decimal(quantity_sold))
                if quantity_sold
                else money(product.price)
            )
            rows.append({
                'row_id': f'{product.id}:{channel}',
                'product_id': str(product.id),
                'product_name': product.name,
                'sale_channel': channel,
                'sale_channel_label': 'Admin panel' if channel == 'admin' else 'Storefront',
                'is_primary': is_primary,
                'quantity_purchased': quantity_purchased if is_primary else None,
                'quantity_sold': quantity_sold,
                'remaining_stock': remaining if is_primary else None,
                'total_purchase_cost': text(product_purchase_cost) if is_primary else None,
                'selling_price': text(avg_sell if channel == 'admin' else product.price),
                'selling_price_varies': bool(price_varies) if channel == 'storefront' else False,
                'avg_selling_price': text(avg_sell),
                'total_sales_revenue': text(revenue),
                'cost_of_goods_sold': text(cogs),
                'realized_profit': text(revenue - cogs),
                'estimated_remaining_revenue': text(estimated_revenue) if is_primary else None,
                'estimated_remaining_profit': text(estimated_revenue - remaining_cost) if is_primary else None,
                'allocated_additional_expenses': text(allocated_cost) if is_primary else text(ZERO),
                'awaiting_payment_quantity': waiting_qty if is_primary else 0,
                'needs_purchase_cost': bool(needs_cost and is_primary),
                'suggested_unit_cost': text(suggested) if suggested is not None and is_primary else None,
                'reconciliation_note': (
                    _note(gap, waiting_qty, price_varies, allocated_cost)
                    if is_primary
                    else (
                        'Admin panel sale — revenue uses the order’s selling price; '
                        'cost comes from product buying vouchers.'
                    )
                ),
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
