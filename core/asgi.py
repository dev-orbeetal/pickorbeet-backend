"""
ASGI config for Pickorbeet.

HTTP stays on this application for Daphne. Gunicorn keeps serving the REST API
through WSGI. Nginx sends only /ws/ to the Daphne process.
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django_asgi = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from apps.notifications.middleware import JwtAuthMiddleware  # noqa: E402
from apps.notifications.routing import websocket_urlpatterns as notification_ws  # noqa: E402
from apps.support.routing import websocket_urlpatterns as support_ws  # noqa: E402

application = ProtocolTypeRouter({
    'http': django_asgi,
    'websocket': JwtAuthMiddleware(URLRouter(notification_ws + support_ws)),
})
