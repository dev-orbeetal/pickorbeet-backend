from django.urls import path

from .consumers import SupportConsumer

websocket_urlpatterns = [
    path('ws/support/', SupportConsumer.as_asgi()),
]
