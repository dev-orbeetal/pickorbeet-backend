"""Security endpoints: email 2FA, sessions, login activity, and recovery email."""
import logging

from django.db import IntegrityError
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import AuthSession, LoginEvent, SecurityCode
from .security import (
    INVALID_LOGIN,
    SecurityCooldown,
    authenticate_password,
    code_error_message,
    consume_code,
    current_sid,
    issue_code,
    issue_login,
    mask_email,
    normalize_email,
    recovery_email_error,
    record_login,
    resend_code,
    revoke_other_sessions,
    revoke_session,
    send_code,
    session_for_sid,
    touch_rotated_session,
    void_latest_code,
)

logger = logging.getLogger(__name__)


def _cooldown(exc):
    return Response(
        {
            'detail': str(exc),
            'code': 'resend_cooldown',
            'retry_after': exc.retry_after,
        },
        status=status.HTTP_429_TOO_MANY_REQUESTS,
    )


def _challenge_body(user, challenge, email):
    return {
        'requires_2fa': True,
        'challenge': challenge,
        'email_hint': mask_email(email or user.email),
    }


def begin_code(user, purpose, target_email=''):
    try:
        code, challenge = issue_code(user, purpose, target_email=target_email)
    except SecurityCooldown as exc:
        return _cooldown(exc)
    recipient = target_email or user.email
    if not send_code(user, purpose, code, to=recipient):
        void_latest_code(user, purpose)
        return Response(
            {'detail': 'We could not send the code. Try again in a moment.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    body = _challenge_body(user, challenge, recipient)
    if purpose != SecurityCode.LOGIN:
        body['requires_code'] = True
        body.pop('requires_2fa', None)
    return Response(body)


class LoginView(APIView):
    """Password sign-in. Two-factor accounts receive an email code instead of tokens."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        user, _email = authenticate_password(request)
        if user is None:
            return Response({'detail': INVALID_LOGIN}, status=status.HTTP_401_UNAUTHORIZED)
        if user.two_factor_enabled:
            if not user.is_verified:
                return Response(
                    {'detail': 'Verify your email before signing in with two-factor authentication.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return begin_code(user, SecurityCode.LOGIN)
        return Response(issue_login(user, request, LoginEvent.PASSWORD))


class TwoFactorVerifyView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        challenge = str(request.data.get('challenge') or '')
        code = str(request.data.get('otp_code') or request.data.get('code') or '').strip()
        if not challenge or not code:
            return Response({'detail': 'Enter the code from your email.'}, status=status.HTTP_400_BAD_REQUEST)
        row, error = consume_code(challenge, code, SecurityCode.LOGIN)
        if error:
            if row is not None:
                record_login(
                    request,
                    success=False,
                    method=LoginEvent.TWO_FACTOR,
                    user=row.user,
                    email=row.user.email,
                )
            return Response({'detail': code_error_message(error), 'code': error}, status=status.HTTP_400_BAD_REQUEST)
        user = row.user
        if not user.is_active or not user.two_factor_enabled:
            return Response(
                {'detail': 'Two-factor authentication is not available for this account.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(issue_login(user, request, LoginEvent.TWO_FACTOR))


class TwoFactorResendView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        challenge = str(request.data.get('challenge') or '')
        if not challenge:
            return Response({'detail': 'Request a new code from the sign-in screen.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            row, code = resend_code(challenge)
        except SecurityCooldown as exc:
            return _cooldown(exc)
        if row is None:
            return Response(
                {'detail': 'That code has expired. Request a new one.', 'code': 'expired'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        recipient = row.target_email or row.user.email
        if not send_code(row.user, row.purpose, code, to=recipient):
            return Response(
                {'detail': 'We could not send the code. Try again in a moment.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({'message': 'A new code is on its way.', 'email_hint': mask_email(recipient)})


class TwoFactorEnableView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.two_factor_enabled:
            return Response({'detail': 'Two-factor authentication is already on.'}, status=status.HTTP_400_BAD_REQUEST)
        if not user.is_verified:
            return Response(
                {'detail': 'Verify your email before turning on two-factor authentication.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return begin_code(user, SecurityCode.ENABLE)


class TwoFactorEnableConfirmView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        challenge = str(request.data.get('challenge') or '')
        code = str(request.data.get('otp_code') or request.data.get('code') or '').strip()
        row, error = consume_code(challenge, code, SecurityCode.ENABLE, user=request.user)
        if error:
            return Response({'detail': code_error_message(error), 'code': error}, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        user.two_factor_enabled = True
        user.save(update_fields=['two_factor_enabled'])
        return Response({'two_factor_enabled': True, 'message': 'Two-factor authentication is on.'})


class TwoFactorDisableView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user.two_factor_enabled:
            return Response({'detail': 'Two-factor authentication is already off.'}, status=status.HTTP_400_BAD_REQUEST)
        password = request.data.get('password') or ''
        challenge = str(request.data.get('challenge') or '')
        code = str(request.data.get('otp_code') or request.data.get('code') or '').strip()
        if user.has_usable_password():
            if not password or not user.check_password(password):
                return Response({'password': 'Wrong password.'}, status=status.HTTP_400_BAD_REQUEST)
        elif challenge and code:
            _row, error = consume_code(challenge, code, SecurityCode.DISABLE, user=user)
            if error:
                return Response({'detail': code_error_message(error), 'code': error}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return begin_code(user, SecurityCode.DISABLE)
        user.two_factor_enabled = False
        user.save(update_fields=['two_factor_enabled'])
        return Response({'two_factor_enabled': False, 'message': 'Two-factor authentication is off.'})


class SessionListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        sid = current_sid(request)
        sessions = AuthSession.objects.filter(user=request.user, revoked_at__isnull=True).order_by('-last_seen')
        return Response({
            'results': [
                {
                    'id': str(session.id),
                    'device_id': session.device_id,
                    'device_name': session.device_name,
                    'platform': session.platform,
                    'ip_address': session.ip_address,
                    'last_seen': session.last_seen,
                    'created_at': session.created_at,
                    'current': sid is not None and str(session.id) == sid,
                }
                for session in sessions
            ],
        })


class SessionRevokeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        session = AuthSession.objects.filter(pk=pk, user=request.user, revoked_at__isnull=True).first()
        if session is None:
            return Response({'detail': 'That device is already signed out.'}, status=status.HTTP_404_NOT_FOUND)
        if current_sid(request) and str(session.id) == current_sid(request):
            return Response(
                {'detail': "This is the device you're using. Sign out from settings to leave it."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        revoke_session(session)
        return Response({'message': 'Signed out of that device.'})


class SessionRevokeOthersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        revoke_other_sessions(request.user, keep_sid=current_sid(request))
        return Response({'message': 'Signed out of every other device.'})


class LoginActivityView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        events = LoginEvent.objects.filter(user=request.user).order_by('-created_at')[:50]
        return Response({
            'results': [
                {
                    'id': str(event.id),
                    'success': event.success,
                    'method': event.method,
                    'device_name': event.device_name,
                    'platform': event.platform,
                    'ip_address': event.ip_address,
                    'created_at': event.created_at,
                }
                for event in events
            ],
        })


class RecoveryEmailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        email = normalize_email(request.data.get('email'))
        error = recovery_email_error(request.user, email)
        if error:
            return Response({'email': error}, status=status.HTTP_400_BAD_REQUEST)
        return begin_code(request.user, SecurityCode.RECOVERY, target_email=email)

    def delete(self, request):
        user = request.user
        user.recovery_email = None
        user.recovery_email_verified = False
        user.save(update_fields=['recovery_email', 'recovery_email_verified'])
        return Response({'message': 'Recovery email removed.', 'recovery_email': None})


class RecoveryEmailConfirmView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        challenge = str(request.data.get('challenge') or '')
        code = str(request.data.get('otp_code') or request.data.get('code') or '').strip()
        row, error = consume_code(challenge, code, SecurityCode.RECOVERY, user=request.user)
        if error:
            return Response({'detail': code_error_message(error), 'code': error}, status=status.HTTP_400_BAD_REQUEST)
        email = row.target_email
        conflict = recovery_email_error(request.user, email)
        if conflict:
            return Response({'email': conflict}, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        user.recovery_email = email
        user.recovery_email_verified = True
        try:
            user.save(update_fields=['recovery_email', 'recovery_email_verified'])
        except IntegrityError:
            return Response(
                {'email': 'That email is already used for account recovery.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({
            'message': 'Recovery email saved.',
            'recovery_email': user.recovery_email,
            'recovery_email_verified': True,
        })


class SessionTokenRefreshView(TokenRefreshView):
    """Rotate the refresh token and keep it attached to the same device session."""

    authentication_classes = []

    def post(self, request, *args, **kwargs):
        raw = request.data.get('refresh')
        sid = None
        incoming = None
        if raw:
            try:
                incoming = RefreshToken(raw)
            except TokenError:
                return Response({'detail': 'Token is invalid or expired'}, status=status.HTTP_401_UNAUTHORIZED)
            sid = incoming.get('sid')
            if sid:
                session = session_for_sid(sid)
                if session is None or session.revoked_at is not None:
                    try:
                        incoming.blacklist()
                    except TokenError:
                        pass
                    return Response(
                        {'detail': 'This session has ended. Sign in again.', 'code': 'session_ended'},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200 and sid:
            rotated = response.data.get('refresh')
            if rotated:
                try:
                    touch_rotated_session(sid, str(RefreshToken(rotated)['jti']))
                except TokenError:
                    logger.exception('Could not record the rotated refresh token')
            else:
                touch_rotated_session(sid, str(incoming['jti']) if incoming is not None else '')
        return response
