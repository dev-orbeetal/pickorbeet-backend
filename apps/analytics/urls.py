from django.urls import path

from .views import (
    BreakdownView,
    CollectView,
    CustomerListView,
    CustomerTimelineView,
    FunnelView,
    LiveView,
    OverviewView,
)

urlpatterns = [
    path('collect/', CollectView.as_view(), name='analytics_collect'),
    path('overview/', OverviewView.as_view(), name='analytics_overview'),
    path('breakdown/', BreakdownView.as_view(), name='analytics_breakdown'),
    path('customers/', CustomerListView.as_view(), name='analytics_customers'),
    path('customers/<uuid:user_id>/', CustomerTimelineView.as_view(), name='analytics_customer_timeline'),
    path('live/', LiveView.as_view(), name='analytics_live'),
    path('funnel/', FunnelView.as_view(), name='analytics_funnel'),
]
