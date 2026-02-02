"""
URL patterns for payments app.
"""
from django.urls import path
from .views import (
    InitiatePaymentView, PaymentIPNView, PaymentSuccessView,
    PaymentFailView, PaymentCancelView, PaymentListView,
    PaymentDetailView, RefundListCreateView, ProcessRefundView
)

urlpatterns = [
    # SSLCommerz endpoints
    path('initiate/', InitiatePaymentView.as_view(), name='initiate_payment'),
    path('ipn/', PaymentIPNView.as_view(), name='payment_ipn'),
    path('success/', PaymentSuccessView.as_view(), name='payment_success'),
    path('fail/', PaymentFailView.as_view(), name='payment_fail'),
    path('cancel/', PaymentCancelView.as_view(), name='payment_cancel'),
    
    # Admin endpoints
    path('admin/', PaymentListView.as_view(), name='payment_list'),
    path('admin/<uuid:pk>/', PaymentDetailView.as_view(), name='payment_detail'),
    path('admin/refunds/', RefundListCreateView.as_view(), name='refund_list'),
    path('admin/refunds/<uuid:pk>/process/', ProcessRefundView.as_view(), name='process_refund'),
]
