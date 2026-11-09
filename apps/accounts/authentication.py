"""JWT auth that rejects a token whose sign-in session was revoked.

Tokens issued before sessions existed have no `sid` and keep working until they refresh.
"""
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from .security import session_for_sid


class SessionJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        sid = validated_token.get('sid')
        if not sid:
            return user
        session = session_for_sid(sid, user.id)
        if session is None or session.revoked_at is not None:
            raise AuthenticationFailed('This session has ended. Sign in again.', code='session_ended')
        return user
