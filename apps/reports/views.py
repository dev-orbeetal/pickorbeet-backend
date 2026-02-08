"""
Views for reports app.
"""
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Avg, F, Q, Case, When, IntegerField
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from datetime import timedelta
from .models import DailySalesReport, StockReport, StockMovement
from .serializers import (
    DailySalesReportSerializer, StockReportSerializer, StockMovementSerializer,
    DateRangeSerializer, SalesSummarySerializer, TopProductSerializer
)
from apps.orders.models import Order, OrderItem
from apps.products.models import Product, ProductVariant, Category
from apps.accounts.permissions import IsStaffUser, IsAccountant


class InventoryAnalyticsView(APIView):
    """Comprehensive inventory analytics for the Inventory Management page."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get(self, request):
        today = timezone.now().date()
        last_30_days = today - timedelta(days=30)
        last_7_days = today - timedelta(days=7)
        last_90_days = today - timedelta(days=90)
        
        products = Product.objects.filter(is_active=True)
        
        # Stock Summary (variant-aware)
        total_products = products.count()
        all_products = list(products.select_related('category').prefetch_related('variants'))
        in_stock = 0
        low_stock = 0
        out_of_stock = 0
        stock_value = 0
        total_units = 0
        
        for p in all_products:
            active_variants = [v for v in p.variants.all() if v.is_active]
            if active_variants:
                is_out = all(v.stock_quantity == 0 for v in active_variants)
                is_low = any(v.stock_quantity <= v.low_stock_threshold for v in active_variants)
                variant_stock = sum(v.stock_quantity for v in active_variants)
                total_units += variant_stock
                stock_value += variant_stock * float(p.price)
                if is_out:
                    out_of_stock += 1
                elif is_low:
                    low_stock += 1
                else:
                    in_stock += 1
            else:
                total_units += p.stock_quantity
                stock_value += p.stock_quantity * float(p.price)
                if p.stock_quantity == 0:
                    out_of_stock += 1
                elif p.stock_quantity <= p.low_stock_threshold:
                    low_stock += 1
                else:
                    in_stock += 1
        
        # Sales Statistics (Last 30 days)
        orders_30_days = Order.objects.filter(
            created_at__date__gte=last_30_days,
            payment_status='paid'
        )
        
        total_sold_30_days = OrderItem.objects.filter(
            order__in=orders_30_days
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        revenue_30_days = orders_30_days.aggregate(total=Sum('total'))['total'] or 0
        
        # Sales Statistics (Last 7 days)
        orders_7_days = Order.objects.filter(
            created_at__date__gte=last_7_days,
            payment_status='paid'
        )
        
        total_sold_7_days = OrderItem.objects.filter(
            order__in=orders_7_days
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        revenue_7_days = orders_7_days.aggregate(total=Sum('total'))['total'] or 0
        
        # Daily Sales Trend (Last 30 days)
        daily_sales = Order.objects.filter(
            created_at__date__gte=last_30_days,
            payment_status='paid'
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            orders=Count('id'),
            revenue=Sum('total'),
            items=Sum('items__quantity')
        ).order_by('date')
        
        # Weekly Sales Trend (Last 90 days)
        weekly_sales = Order.objects.filter(
            created_at__date__gte=last_90_days,
            payment_status='paid'
        ).annotate(
            week=TruncWeek('created_at')
        ).values('week').annotate(
            orders=Count('id'),
            revenue=Sum('total'),
            items=Sum('items__quantity')
        ).order_by('week')
        
        # Category Stock Distribution (variant-aware)
        from collections import defaultdict
        cat_data = defaultdict(lambda: {'product_count': 0, 'total_stock': 0, 'stock_value': 0, 'out_of_stock_count': 0, 'low_stock_count': 0})
        for p in all_products:
            cat_id = str(p.category_id)
            cat_name = p.category.name if p.category else 'Uncategorized'
            cat_data[(cat_id, cat_name)]['product_count'] += 1
            active_variants = [v for v in p.variants.all() if v.is_active]
            if active_variants:
                p_stock = sum(v.stock_quantity for v in active_variants)
                p_out = all(v.stock_quantity == 0 for v in active_variants)
                p_low = any(v.stock_quantity <= v.low_stock_threshold for v in active_variants) and not p_out
            else:
                p_stock = p.stock_quantity
                p_out = p.stock_quantity == 0
                p_low = p.stock_quantity > 0 and p.stock_quantity <= p.low_stock_threshold
            cat_data[(cat_id, cat_name)]['total_stock'] += p_stock
            cat_data[(cat_id, cat_name)]['stock_value'] += p_stock * float(p.price)
            if p_out:
                cat_data[(cat_id, cat_name)]['out_of_stock_count'] += 1
            elif p_low:
                cat_data[(cat_id, cat_name)]['low_stock_count'] += 1
        category_stock = [
            {'category__id': k[0], 'category__name': k[1], **v}
            for k, v in sorted(cat_data.items(), key=lambda x: -x[1]['total_stock'])
        ]
        
        # Top Selling Products (Last 30 days)
        top_selling = OrderItem.objects.filter(
            order__in=orders_30_days
        ).values(
            'product__id', 'product__name', 'product__sku', 'product__stock_quantity'
        ).annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum('total_price')
        ).order_by('-total_sold')[:10]
        
        # Slow Moving Products (Products with low sales in last 30 days)
        products_with_sales = OrderItem.objects.filter(
            order__in=orders_30_days
        ).values_list('product_id', flat=True).distinct()
        
        slow_moving = products.exclude(
            id__in=products_with_sales
        ).filter(
            stock_quantity__gt=0
        ).values(
            'id', 'name', 'sku', 'stock_quantity', 'price'
        ).order_by('-stock_quantity')[:10]
        
        # Low Stock Products (variant-aware)
        low_stock_products_list = []
        for p in all_products:
            active_variants = [v for v in p.variants.all() if v.is_active]
            if active_variants:
                is_low = any(v.stock_quantity <= v.low_stock_threshold for v in active_variants)
                p_stock = sum(v.stock_quantity for v in active_variants)
            else:
                is_low = p.stock_quantity <= p.low_stock_threshold
                p_stock = p.stock_quantity
            if is_low:
                low_stock_products_list.append({
                    'id': str(p.id), 'name': p.name, 'sku': p.sku,
                    'stock_quantity': p_stock, 'threshold': p.low_stock_threshold,
                    'category': p.category.name if p.category else '',
                    'value': float(p_stock * p.price),
                })
        low_stock_products_list.sort(key=lambda x: x['stock_quantity'])
        low_stock_products = low_stock_products_list[:20]
        
        # Stock Status Distribution for Chart
        stock_status_distribution = {
            'in_stock': in_stock,
            'low_stock': low_stock,
            'out_of_stock': out_of_stock
        }
        
        # Recent Stock Movements
        recent_movements = StockMovement.objects.select_related(
            'product', 'variant', 'created_by'
        ).order_by('-created_at')[:30]
        
        movements_data = [
            {
                'id': str(m.id),
                'product_id': str(m.product.id),
                'product_name': m.product.name,
                'product_sku': m.product.sku,
                'variant_id': str(m.variant.id) if m.variant else None,
                'variant_label': (
                    f"{m.variant.size or ''} {m.variant.color or ''}".strip()
                    if m.variant else None
                ),
                'variant_sku': m.variant.sku if m.variant else None,
                'movement_type': m.movement_type,
                'quantity': m.quantity,
                'previous_stock': m.previous_stock,
                'new_stock': m.new_stock,
                'reason': m.reason,
                'note': m.note or '',
                'created_at': m.created_at.isoformat(),
                'created_by': m.created_by.email if m.created_by else None
            }
            for m in recent_movements
        ]
        
        # Inventory Turnover Rate (Simplified)
        avg_inventory = total_units / 2 if total_units > 0 else 1
        turnover_rate = (total_sold_30_days / avg_inventory) * 12 if avg_inventory > 0 else 0
        
        # Stock Age Distribution
        stock_age = products.filter(stock_quantity__gt=0).aggregate(
            fresh=Count('id', filter=Q(updated_at__gte=last_7_days)),
            recent=Count('id', filter=Q(updated_at__gte=last_30_days, updated_at__lt=last_7_days)),
            aging=Count('id', filter=Q(updated_at__gte=last_90_days, updated_at__lt=last_30_days)),
            old=Count('id', filter=Q(updated_at__lt=last_90_days))
        )
        
        return Response({
            'summary': {
                'total_products': total_products,
                'in_stock': in_stock,
                'low_stock': low_stock,
                'out_of_stock': out_of_stock,
                'total_units': total_units,
                'stock_value': float(stock_value),
                'turnover_rate': round(turnover_rate, 2),
            },
            'sales_stats': {
                'last_7_days': {
                    'units_sold': total_sold_7_days,
                    'revenue': float(revenue_7_days),
                    'orders': orders_7_days.count(),
                },
                'last_30_days': {
                    'units_sold': total_sold_30_days,
                    'revenue': float(revenue_30_days),
                    'orders': orders_30_days.count(),
                },
            },
            'stock_status_distribution': stock_status_distribution,
            'stock_age_distribution': stock_age,
            'daily_sales_trend': [
                {
                    'date': d['date'].isoformat() if d['date'] else None,
                    'orders': d['orders'],
                    'revenue': float(d['revenue'] or 0),
                    'items': d['items'] or 0,
                }
                for d in daily_sales
            ],
            'weekly_sales_trend': [
                {
                    'week': w['week'].isoformat() if w['week'] else None,
                    'orders': w['orders'],
                    'revenue': float(w['revenue'] or 0),
                    'items': w['items'] or 0,
                }
                for w in weekly_sales
            ],
            'category_stock': [
                {
                    'category_id': c['category__id'],
                    'category_name': c['category__name'] or 'Uncategorized',
                    'product_count': c['product_count'],
                    'total_stock': c['total_stock'] or 0,
                    'stock_value': float(c['stock_value'] or 0),
                    'out_of_stock_count': c['out_of_stock_count'],
                    'low_stock_count': c['low_stock_count'],
                }
                for c in category_stock
            ],
            'top_selling_products': [
                {
                    'product_id': str(p['product__id']),
                    'product_name': p['product__name'],
                    'product_sku': p['product__sku'],
                    'current_stock': p['product__stock_quantity'],
                    'total_sold': p['total_sold'],
                    'total_revenue': float(p['total_revenue']),
                }
                for p in top_selling
            ],
            'slow_moving_products': [
                {
                    'id': str(p['id']),
                    'name': p['name'],
                    'sku': p['sku'],
                    'stock_quantity': p['stock_quantity'],
                    'value': float(p['stock_quantity'] * p['price']),
                }
                for p in slow_moving
            ],
            'low_stock_products': low_stock_products,
            'recent_stock_movements': movements_data,
        })


class DashboardStatsView(APIView):
    """Get dashboard statistics."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get(self, request):
        today = timezone.now().date()
        
        # Today's stats
        today_orders = Order.objects.filter(created_at__date=today)
        today_revenue = today_orders.aggregate(total=Sum('total'))['total'] or 0
        
        # This month stats
        month_start = today.replace(day=1)
        month_orders = Order.objects.filter(created_at__date__gte=month_start)
        month_revenue = month_orders.aggregate(total=Sum('total'))['total'] or 0
        
        # Pending orders
        pending_orders = Order.objects.filter(order_status='pending').count()
        
        # Low stock products (variant-aware)
        from apps.products.models import ProductVariant
        # Products without variants that are low stock
        no_variant_low = Q(
            variants__isnull=True,
            stock_quantity__lte=F('low_stock_threshold'),
        )
        # Products with at least one variant that is low stock
        variant_low = Q(
            variants__is_active=True,
            variants__stock_quantity__lte=F('variants__low_stock_threshold'),
        )
        low_stock_count = Product.objects.filter(
            is_active=True
        ).filter(no_variant_low | variant_low).distinct().count()
        
        # Out of stock products (variant-aware)
        no_variant_oos = Q(variants__isnull=True, stock_quantity=0)
        all_active = Product.objects.filter(is_active=True)
        # For variant products: all variants have 0 stock
        variant_products_with_stock = Product.objects.filter(
            is_active=True, variants__is_active=True, variants__stock_quantity__gt=0
        ).distinct()
        out_of_stock = all_active.filter(no_variant_oos).distinct().count() + \
            all_active.filter(variants__isnull=False).distinct().exclude(
                id__in=variant_products_with_stock
            ).count()
        
        return Response({
            'today': {
                'orders': today_orders.count(),
                'revenue': float(today_revenue),
            },
            'this_month': {
                'orders': month_orders.count(),
                'revenue': float(month_revenue),
            },
            'pending_orders': pending_orders,
            'low_stock_products': low_stock_count,
            'out_of_stock_products': out_of_stock,
            'total_products': Product.objects.filter(is_active=True).count(),
            'total_categories': Category.objects.filter(is_active=True).count(),
        })


class SalesReportView(APIView):
    """Generate sales report for date range."""
    permission_classes = [IsAuthenticated, IsAccountant]

    def post(self, request):
        serializer = DateRangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        start_date = serializer.validated_data['start_date']
        end_date = serializer.validated_data['end_date']
        
        orders = Order.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            payment_status='paid'
        )
        
        # Overall summary
        summary = orders.aggregate(
            total_orders=Count('id'),
            total_revenue=Sum('total'),
            total_items=Sum('items__quantity'),
        )
        
        online_orders = orders.filter(order_type='online').count()
        in_shop_orders = orders.filter(order_type='in_shop').count()
        
        avg_order_value = orders.aggregate(avg=Avg('total'))['avg'] or 0
        
        # Daily breakdown
        daily_sales = orders.annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            orders=Count('id'),
            revenue=Sum('total'),
            items=Sum('items__quantity')
        ).order_by('date')
        
        # Top selling products
        top_products = OrderItem.objects.filter(
            order__in=orders
        ).values(
            'product__id', 'product__name'
        ).annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum('total_price')
        ).order_by('-total_sold')[:10]
        
        # Category breakdown
        category_sales = OrderItem.objects.filter(
            order__in=orders
        ).values(
            'product__category__id', 'product__category__name'
        ).annotate(
            total_orders=Count('order', distinct=True),
            total_revenue=Sum('total_price')
        ).order_by('-total_revenue')
        
        return Response({
            'period': {
                'start_date': start_date,
                'end_date': end_date,
            },
            'summary': {
                'total_orders': summary['total_orders'] or 0,
                'total_revenue': float(summary['total_revenue'] or 0),
                'total_items_sold': summary['total_items'] or 0,
                'average_order_value': float(avg_order_value),
                'online_orders': online_orders,
                'in_shop_orders': in_shop_orders,
            },
            'daily_sales': list(daily_sales),
            'top_products': [
                {
                    'product_id': str(p['product__id']),
                    'product_name': p['product__name'],
                    'total_sold': p['total_sold'],
                    'total_revenue': float(p['total_revenue']),
                }
                for p in top_products
            ],
            'category_sales': [
                {
                    'category_id': str(c['product__category__id']),
                    'category_name': c['product__category__name'],
                    'total_orders': c['total_orders'],
                    'total_revenue': float(c['total_revenue']),
                }
                for c in category_sales
            ],
        })


class StockReportView(APIView):
    """Generate current stock report with variant details."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get(self, request):
        products = Product.objects.filter(is_active=True)
        
        total_products = products.count()
        in_stock = products.filter(stock_quantity__gt=F('low_stock_threshold')).count()
        low_stock = products.filter(
            stock_quantity__gt=0,
            stock_quantity__lte=F('low_stock_threshold')
        ).count()
        out_of_stock = products.filter(stock_quantity=0).count()
        
        # Calculate stock value
        stock_value = products.aggregate(
            total=Sum(F('stock_quantity') * F('price'))
        )['total'] or 0
        
        total_units = products.aggregate(total=Sum('stock_quantity'))['total'] or 0
        
        # Variant stats
        total_variants = ProductVariant.objects.filter(product__is_active=True).count()
        variant_units = ProductVariant.objects.filter(
            product__is_active=True
        ).aggregate(total=Sum('stock_quantity'))['total'] or 0
        
        # Low stock products details
        low_stock_products = products.filter(
            stock_quantity__lte=F('low_stock_threshold')
        ).values(
            'id', 'name', 'sku', 'stock_quantity', 'low_stock_threshold'
        ).order_by('stock_quantity')[:20]
        
        # Category-wise stock
        category_stock = products.values(
            'category__id', 'category__name'
        ).annotate(
            product_count=Count('id'),
            total_stock=Sum('stock_quantity'),
            stock_value=Sum(F('stock_quantity') * F('price'))
        ).order_by('-total_stock')
        
        # Full product list with variants for detailed stock report
        all_products_qs = products.select_related(
            'category'
        ).prefetch_related(
            'variants'
        ).order_by('category__name', 'name')
        
        all_products = []
        for p in all_products_qs:
            variants_data = []
            for v in p.variants.all():
                variants_data.append({
                    'id': str(v.id),
                    'sku': v.sku,
                    'barcode': v.barcode,
                    'size': v.size,
                    'color': v.color,
                    'stock_quantity': v.stock_quantity,
                    'price': float(v.price) if v.price else float(p.price),
                    'stock_value': float((v.price or p.price) * v.stock_quantity),
                })
            
            all_products.append({
                'id': str(p.id),
                'name': p.name,
                'sku': p.sku,
                'barcode': p.barcode,
                'category': p.category.name if p.category else 'Uncategorized',
                'price': float(p.price),
                'stock_quantity': p.stock_quantity,
                'low_stock_threshold': p.low_stock_threshold,
                'stock_value': float(p.price * p.stock_quantity),
                'has_variants': len(variants_data) > 0,
                'variants': variants_data,
                'total_variant_stock': sum(v['stock_quantity'] for v in variants_data),
            })
        
        # Save stock report
        report, _ = StockReport.objects.update_or_create(
            date=timezone.now().date(),
            defaults={
                'total_products': total_products,
                'in_stock_products': in_stock,
                'low_stock_products': low_stock,
                'out_of_stock_products': out_of_stock,
                'total_stock_value': stock_value,
                'total_units': total_units,
                'generated_by': request.user,
            }
        )
        
        return Response({
            'generated_at': timezone.now(),
            'summary': {
                'total_products': total_products,
                'in_stock': in_stock,
                'low_stock': low_stock,
                'out_of_stock': out_of_stock,
                'total_units': total_units,
                'total_stock_value': float(stock_value),
                'total_variants': total_variants,
                'total_variant_units': variant_units,
            },
            'low_stock_products': list(low_stock_products),
            'category_stock': [
                {
                    'category_id': str(c['category__id']),
                    'category_name': c['category__name'],
                    'product_count': c['product_count'],
                    'total_stock': c['total_stock'],
                    'stock_value': float(c['stock_value'] or 0),
                }
                for c in category_stock
            ],
            'all_products': all_products,
        })


class StockMovementListView(generics.ListAPIView):
    """List stock movements."""
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get_queryset(self):
        queryset = StockMovement.objects.all().select_related('product', 'created_by')
        
        # Filter by product
        product_id = self.request.query_params.get('product_id')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        return queryset


class DailySalesReportListView(generics.ListAPIView):
    """List historical daily sales reports."""
    serializer_class = DailySalesReportSerializer
    permission_classes = [IsAuthenticated, IsAccountant]

    def get_queryset(self):
        return DailySalesReport.objects.all()


class StockReportListView(generics.ListAPIView):
    """List historical stock reports."""
    serializer_class = StockReportSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get_queryset(self):
        return StockReport.objects.all()


class GenerateDailySalesReportView(APIView):
    """Generate daily sales report for a specific date."""
    permission_classes = [IsAuthenticated, IsAccountant]

    def post(self, request):
        date_str = request.data.get('date')
        if date_str:
            from datetime import datetime
            report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            report_date = timezone.now().date()
        
        orders = Order.objects.filter(
            created_at__date=report_date,
            payment_status='paid'
        )
        
        online_orders = orders.filter(order_type='online')
        in_shop_orders = orders.filter(order_type='in_shop')
        
        totals = orders.aggregate(
            gross_revenue=Sum('total'),
            delivery_charges=Sum('delivery_charge'),
            discounts=Sum('discount'),
            total_items=Sum('items__quantity'),
        )
        
        # Payment breakdown
        cash = in_shop_orders.filter(payment_method='cash').aggregate(
            total=Sum('total')
        )['total'] or 0
        card = in_shop_orders.filter(payment_method='card').aggregate(
            total=Sum('total')
        )['total'] or 0
        online = online_orders.aggregate(total=Sum('total'))['total'] or 0
        
        report, created = DailySalesReport.objects.update_or_create(
            date=report_date,
            defaults={
                'total_orders': orders.count(),
                'online_orders': online_orders.count(),
                'in_shop_orders': in_shop_orders.count(),
                'gross_revenue': totals['gross_revenue'] or 0,
                'delivery_charges': totals['delivery_charges'] or 0,
                'discounts': totals['discounts'] or 0,
                'net_revenue': (totals['gross_revenue'] or 0) - (totals['delivery_charges'] or 0),
                'total_items_sold': totals['total_items'] or 0,
                'cash_payments': cash,
                'card_payments': card,
                'online_payments': online,
                'generated_by': request.user,
            }
        )
        
        return Response(DailySalesReportSerializer(report).data)
