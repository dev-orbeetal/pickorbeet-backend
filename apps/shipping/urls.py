"""
URL patterns for the shipping app.
"""
from django.urls import path

from .views import (
    AdminShipmentBulkRefreshView,
    AdminShipmentDetailView,
    AdminShipmentImportPreviewView,
    AdminShipmentImportView,
    AdminShipmentListView,
    AdminShipmentRefreshView,
    AdminShipmentSummaryView,
    AdminSteadfastBalanceView,
    SteadfastWebhookView,
)

urlpatterns = [
    path('steadfast/webhook/', SteadfastWebhookView.as_view(), name='steadfast_webhook'),
    path('admin/shipments/', AdminShipmentListView.as_view(), name='admin_shipment_list'),
    path('admin/shipments/summary/', AdminShipmentSummaryView.as_view(), name='admin_shipment_summary'),
    path('admin/shipments/bulk-refresh/', AdminShipmentBulkRefreshView.as_view(), name='admin_shipment_bulk_refresh'),
    path('admin/shipments/import/preview/', AdminShipmentImportPreviewView.as_view(), name='admin_shipment_import_preview'),
    path('admin/shipments/import/', AdminShipmentImportView.as_view(), name='admin_shipment_import'),
    path('admin/shipments/<uuid:pk>/', AdminShipmentDetailView.as_view(), name='admin_shipment_detail'),
    path('admin/shipments/<uuid:pk>/refresh/', AdminShipmentRefreshView.as_view(), name='admin_shipment_refresh'),
    path('admin/steadfast/balance/', AdminSteadfastBalanceView.as_view(), name='admin_steadfast_balance'),
]
