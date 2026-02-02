"""
Views for reports app.
"""
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Avg, F
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from .models import DailySalesReport, StockReport, StockMovement
from .serializers import (
    DailySalesReportSerializer, StockReportSerializer, StockMovementSerializer,
    DateRangeSerializer, SalesSummarySerializer, TopProductSerializer
)
from apps.orders.models import Order, OrderItem
from apps.products.models import Product, Category
from apps.accounts.permissions import IsStaffUser, IsAccountant


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
        
        # Low stock products
        low_stock_count = Product.objects.filter(
            stock_quantity__lte=F('low_stock_threshold'),
            is_active=True
        ).count()
        
        # Out of stock products
        out_of_stock = Product.objects.filter(stock_quantity=0, is_active=True).count()
        
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
    """Generate current stock report."""
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
