from django.urls import path

from .views import (
    ConversationView,
    CustomerReadView,
    MessageCreateView,
    StaffInboxView,
    StaffReadView,
    StaffReplyView,
    StaffThreadView,
)

urlpatterns = [
    path('conversation/', ConversationView.as_view(), name='support-conversation'),
    path('messages/', MessageCreateView.as_view(), name='support-messages'),
    path('read/', CustomerReadView.as_view(), name='support-read'),
    path('inbox/', StaffInboxView.as_view(), name='support-inbox'),
    path('inbox/<uuid:pk>/', StaffThreadView.as_view(), name='support-thread'),
    path('inbox/<uuid:pk>/read/', StaffReadView.as_view(), name='support-thread-read'),
    path('inbox/<uuid:pk>/reply/', StaffReplyView.as_view(), name='support-reply'),
]
