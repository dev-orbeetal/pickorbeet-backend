"""Authenticate the notification socket with the same access token as the API."""
from urllib.parse import parse_qs, urlparse

from channels.db import database_sync_to_async
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import User


def origin_allowed(scope):
    """Phones often omit Origin. Browsers must match the API host or CORS list."""
    origin = None
    for name, value in scope.get('headers', []):
        if name == b'origin':
            origin = value.decode('latin1')
            break
    if not origin:
        return True
    host = (urlparse(origin).hostname or '').lower()
    allowed_hosts = {item.lower() for item in settings.ALLOWED_HOSTS}
    if host in allowed_hosts or '*' in allowed_hosts:
        return True
    return origin in set(settings.CORS_ALLOWED_ORIGINS)


@database_sync_to_async
def user_from_token(token):
    if not token:
        return AnonymousUser()
    try:
        access = AccessToken(token)
        user_id = access.get('user_id')
        if not user_id:
            return AnonymousUser()
        return User.objects.get(pk=user_id, is_active=True)
    except (TokenError, User.DoesNotExist, KeyError, ValueError):
        return AnonymousUser()


class JwtAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if not origin_allowed(scope):
            await send({'type': 'websocket.close', 'code': 4403})
            return
        query = parse_qs(scope.get('query_string', b'').decode())
        token = (query.get('token') or [None])[0]
        scope['user'] = await user_from_token(token)
        return await self.app(scope, receive, send)
