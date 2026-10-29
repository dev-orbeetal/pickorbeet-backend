"""
URL patterns for payments app.
"""
from django.urls import path
from .views import (
    InitiatePaymentView, PaymentIPNView, PaymentSuccessView,
    PaymentFailView, PaymentCancelView, PaymentListView,
    PaymentDetailView, RefundListCreateView, ProcessRefundView,
    ExpenseListCreateView, ExpenseDetailView, ExpenseByProductView, AdminIncomeView,
    FinanceSummaryView, ProductFinanceView,
)

urlpatterns = [
    # SSLCommerz endpoints
    path('initiate/', InitiatePaymentView.as_view(), name='initiate_payment'),
    path('ipn/', PaymentIPNView.as_view(), name='payment_ipn'),
    path('success/', PaymentSuccessView.as_view(), name='payment_success'),
    path('fail/', PaymentFailView.as_view(), name='payment_fail'),
    path('cancel/', PaymentCancelView.as_view(), name='payment_cancel'),
    
    # Admin endpoints. Specific paths stay ahead of the payment detail uuid.
    path('admin/finance/summary/', FinanceSummaryView.as_view(), name='finance_summary'),
    path('admin/finance/products/', ProductFinanceView.as_view(), name='product_finance'),
    path('admin/expenses/', ExpenseListCreateView.as_view(), name='expense_list'),
    path('admin/expenses/by-product/', ExpenseByProductView.as_view(), name='expense_by_product'),
    path('admin/expenses/<uuid:pk>/', ExpenseDetailView.as_view(), name='expense_detail'),
    path('admin/income/', AdminIncomeView.as_view(), name='admin_income'),
    path('admin/', PaymentListView.as_view(), name='payment_list'),
    path('admin/<uuid:pk>/', PaymentDetailView.as_view(), name='payment_detail'),
    path('admin/refunds/', RefundListCreateView.as_view(), name='refund_list'),
    path('admin/refunds/<uuid:pk>/process/', ProcessRefundView.as_view(), name='process_refund'),
]
