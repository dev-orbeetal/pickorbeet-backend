"""
URL patterns for the shipping app.
"""
from django.urls import path

from .views import SteadfastWebhookView

urlpatterns = [
    path('steadfast/webhook/', SteadfastWebhookView.as_view(), name='steadfast_webhook'),
]
