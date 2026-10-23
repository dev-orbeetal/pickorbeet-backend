"""Inbox routes under /api/v1/notifications/."""
from django.urls import path

from .views import (
    DeviceRegisterView,
    DeviceUnregisterView,
    MarkAllReadView,
    MarkReadView,
    NotificationListView,
    UnreadCountView,
)

urlpatterns = [
    path('', NotificationListView.as_view(), name='notification_list'),
    path('unread-count/', UnreadCountView.as_view(), name='notification_unread_count'),
    path('read-all/', MarkAllReadView.as_view(), name='notification_read_all'),
    path('devices/', DeviceRegisterView.as_view(), name='notification_device_register'),
    path('devices/<str:device_id>/', DeviceUnregisterView.as_view(), name='notification_device_unregister'),
    path('<uuid:pk>/read/', MarkReadView.as_view(), name='notification_read'),
]
