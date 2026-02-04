"""
URL patterns for reports app.
"""
from django.urls import path
from .views import (
    DashboardStatsView, SalesReportView, StockReportView,
    StockMovementListView, DailySalesReportListView, StockReportListView,
    GenerateDailySalesReportView, InventoryAnalyticsView
)

urlpatterns = [
    # Dashboard
    path('dashboard/', DashboardStatsView.as_view(), name='dashboard_stats'),
    
    # Inventory Analytics
    path('inventory/analytics/', InventoryAnalyticsView.as_view(), name='inventory_analytics'),
    
    # Sales reports
    path('sales/', SalesReportView.as_view(), name='sales_report'),
    path('sales/daily/', DailySalesReportListView.as_view(), name='daily_sales_list'),
    path('sales/generate/', GenerateDailySalesReportView.as_view(), name='generate_daily_sales'),
    
    # Stock reports
    path('stock/', StockReportView.as_view(), name='stock_report'),
    path('stock/history/', StockReportListView.as_view(), name='stock_report_list'),
    path('stock/movements/', StockMovementListView.as_view(), name='stock_movements'),
]
