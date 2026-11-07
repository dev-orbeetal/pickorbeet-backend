from django.urls import path

from . import views

urlpatterns = [
    path('admin/templates/', views.TemplateListView.as_view(), name='campaign_templates'),
    path('admin/campaigns/', views.CampaignListCreateView.as_view(), name='campaign_list'),
    path('admin/campaigns/<uuid:pk>/', views.CampaignDetailView.as_view(), name='campaign_detail'),
    path('admin/campaigns/<uuid:pk>/send/', views.CampaignSendView.as_view(), name='campaign_send'),
    path('admin/campaigns/<uuid:pk>/schedule/', views.CampaignScheduleView.as_view(), name='campaign_schedule'),
    path('admin/campaigns/<uuid:pk>/cancel/', views.CampaignCancelView.as_view(), name='campaign_cancel'),
    path('admin/campaigns/<uuid:pk>/test/', views.CampaignTestView.as_view(), name='campaign_test'),
    path('admin/preview/', views.CampaignPreviewView.as_view(), name='campaign_preview'),
    path('admin/estimate/', views.CampaignEstimateView.as_view(), name='campaign_estimate'),
    path('admin/automations/', views.AutomationListView.as_view(), name='campaign_automations'),
    path('admin/automations/<str:trigger>/', views.AutomationDetailView.as_view(), name='campaign_automation'),
    path('admin/settings/', views.SettingsView.as_view(), name='campaign_settings'),
    path('admin/customers/', views.CampaignCustomerSearchView.as_view(), name='campaign_customers'),
]
