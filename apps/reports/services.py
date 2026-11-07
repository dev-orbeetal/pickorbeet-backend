from django.db.models import Sum

from apps.orders.models import Order

from .models import DailySalesReport


def generate_daily_sales_report(report_date, user=None):
    """Build (or rebuild) the stored sales report for one day from paid orders."""
    orders = Order.objects.filter(
        created_at__date=report_date,
        payment_status='paid'
    )

    online_orders = orders.filter(order_type='online')
    # Field name is historical; counts external admin sales (and any legacy in-shop).
    offline_orders = orders.filter(order_type__in=['external', 'in_shop'])

    totals = orders.aggregate(
        gross_revenue=Sum('total'),
        delivery_charges=Sum('delivery_charge'),
        discounts=Sum('discount'),
        total_items=Sum('items__quantity'),
    )

    # Payment breakdown
    cash = offline_orders.filter(payment_method='cash').aggregate(
        total=Sum('total')
    )['total'] or 0
    card = offline_orders.filter(payment_method='card').aggregate(
        total=Sum('total')
    )['total'] or 0
    online = online_orders.aggregate(total=Sum('total'))['total'] or 0

    report, _ = DailySalesReport.objects.update_or_create(
        date=report_date,
        defaults={
            'total_orders': orders.count(),
            'online_orders': online_orders.count(),
            'in_shop_orders': offline_orders.count(),
            'gross_revenue': totals['gross_revenue'] or 0,
            'delivery_charges': totals['delivery_charges'] or 0,
            'discounts': totals['discounts'] or 0,
            'net_revenue': (totals['gross_revenue'] or 0) - (totals['delivery_charges'] or 0),
            'total_items_sold': totals['total_items'] or 0,
            'cash_payments': cash,
            'card_payments': card,
            'online_payments': online,
            'generated_by': user,
        }
    )
    return report
