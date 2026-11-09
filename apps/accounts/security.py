"""Sign-in sessions, emailed security codes, and device context."""
import hashlib
import ipaddress
import logging
import secrets
import uuid
from datetime import timedelta

from django.contrib.auth import authenticate
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from .emails import send_security_code_email
from .models import AuthSession, LoginEvent, SecurityCode, User

logger = logging.getLogger(__name__)

CODE_TTL = timedelta(minutes=10)
RESEND_WAIT = timedelta(seconds=60)
MAX_ATTEMPTS = 5
INVALID_LOGIN = 'No active account found with the given credentials'


class SecurityCooldown(Exception):
    def __init__(self, retry_after):
        self.retry_after = max(1, int(retry_after))
        super().__init__(f'Please wait {self.retry_after} seconds before requesting another code.')


def generate_code():
    return f'{secrets.randbelow(1_000_000):06d}'


def _hash(value):
    return hashlib.sha256(str(value).strip().encode()).hexdigest()


def mask_email(email):
    local, sep, domain = str(email or '').partition('@')
    if not sep:
        return ''
    if len(local) <= 1:
        hidden = '*'
    elif len(local) == 2:
        hidden = local[0] + '*'
    else:
        hidden = local[:2] + '***'
    return f'{hidden}@{domain}'


def normalize_email(value):
    return User.objects.normalize_email(str(value or '').strip()).lower()


def _clip(value, limit):
    return str(value or '').replace('\x00', '').strip()[:limit]


def client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    candidate = forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR', '')
    if not candidate:
        return None
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return None
    return candidate


def _device_name(user_agent, platform):
    agent = user_agent.lower()
    if 'iphone' in agent:
        return 'iPhone'
    if 'ipad' in agent:
        return 'iPad'
    if 'android' in agent:
        return 'Android'
    if 'mac os' in agent or 'macintosh' in agent:
        return 'Mac'
    if 'windows' in agent:
        return 'Windows'
    if 'linux' in agent:
        return 'Linux'
    if platform == 'web':
        return 'Web browser'
    if platform == 'app':
        return 'PickOrbeet app'
    return 'Unknown device'


def client_context(request):
    platform = _clip(request.headers.get('X-Client-Platform'), 20).lower() or 'unknown'
    user_agent = _clip(request.META.get('HTTP_USER_AGENT'), 500)
    device_name = _clip(request.headers.get('X-Device-Name'), 120) or _device_name(user_agent, platform)
    return {
        'device_id': _clip(request.headers.get('X-Device-Id'), 128),
        'device_name': device_name,
        'platform': platform,
        'ip_address': client_ip(request),
        'user_agent': user_agent,
    }


def current_sid(request):
    token = getattr(request, 'auth', None)
    getter = getattr(token, 'get', None)
    if not callable(getter):
        return None
    sid = getter('sid')
    return str(sid) if sid else None


def session_for_sid(sid, user_id=None):
    if not sid:
        return None
    try:
        uuid.UUID(str(sid))
    except (ValueError, TypeError, AttributeError):
        return None
    query = AuthSession.objects.filter(pk=sid)
    if user_id is not None:
        query = query.filter(user_id=user_id)
    return query.first()


def login_user_payload(user):
    return {
        'id': str(user.id),
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'role': user.role,
        'full_name': user.full_name,
    }


def record_login(request, *, success, method, user=None, email=''):
    address = _clip(email or (user.email if user else ''), 254)
    LoginEvent.objects.create(
        user=user,
        email=address,
        success=success,
        method=method,
        **client_context(request),
    )


def blacklist_refresh_jti(jti):
    if not jti:
        return
    outstanding = OutstandingToken.objects.filter(jti=jti).first()
    if outstanding is None:
        return
    BlacklistedToken.objects.get_or_create(token=outstanding)


def revoke_session(session):
    if session.revoked_at is not None:
        return
    session.revoked_at = timezone.now()
    session.save(update_fields=['revoked_at'])
    blacklist_refresh_jti(session.refresh_jti)


def revoke_other_sessions(user, keep_sid=None):
    sessions = AuthSession.objects.filter(user=user, revoked_at__isnull=True)
    if keep_sid:
        sessions = sessions.exclude(pk=keep_sid)
    for session in sessions:
        revoke_session(session)


def issue_login(user, request, method):
    """Open a session and return the token payload clients already expect."""
    context = client_context(request)
    refresh = RefreshToken.for_user(user)
    session = AuthSession.objects.create(
        user=user,
        refresh_jti=str(refresh['jti']),
        last_seen=timezone.now(),
        **context,
    )
    refresh['sid'] = str(session.id)
    refresh['email'] = user.email
    refresh['role'] = user.role
    refresh['full_name'] = user.full_name or ''
    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])
    LoginEvent.objects.create(
        user=user,
        email=user.email,
        success=True,
        method=method,
        **context,
    )
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': login_user_payload(user),
    }


def authenticate_password(request):
    email = _clip(request.data.get('email') or request.data.get('username'), 254)
    password = request.data.get('password') or ''
    user = authenticate(request, username=email, password=password) if email and password else None
    if user is None or not user.is_active:
        known = User.objects.filter(email__iexact=email).first() if email else None
        record_login(request, success=False, method=LoginEvent.PASSWORD, user=known, email=email)
        return None, email
    return user, email


@transaction.atomic
def issue_code(user, purpose, target_email=''):
    now = timezone.now()
    latest = (
        SecurityCode.objects.select_for_update()
        .filter(user=user, purpose=purpose, used_at__isnull=True, expires_at__gt=now)
        .order_by('-created_at')
        .first()
    )
    if latest is not None:
        elapsed = now - latest.last_sent_at
        if elapsed < RESEND_WAIT:
            raise SecurityCooldown((RESEND_WAIT - elapsed).total_seconds())
    SecurityCode.objects.filter(user=user, purpose=purpose, used_at__isnull=True).update(used_at=now)
    code = generate_code()
    challenge = secrets.token_urlsafe(32)
    SecurityCode.objects.create(
        user=user,
        purpose=purpose,
        code_hash=_hash(code),
        challenge_hash=_hash(challenge),
        target_email=normalize_email(target_email) if target_email else '',
        expires_at=now + CODE_TTL,
        last_sent_at=now,
    )
    return code, challenge


def send_code(user, purpose, code, to=None):
    try:
        send_security_code_email(user, code, purpose=purpose, to=to or user.email)
        return True
    except Exception:
        logger.exception('Security code email failed for %s (%s)', user.pk, purpose)
        return False


def void_latest_code(user, purpose):
    SecurityCode.objects.filter(user=user, purpose=purpose, used_at__isnull=True).update(used_at=timezone.now())


@transaction.atomic
def consume_code(challenge, code, purpose, user=None):
    """Return (row, error). error is invalid, expired, or locked. row is set when the challenge exists."""
    now = timezone.now()
    row = (
        SecurityCode.objects.select_for_update()
        .filter(challenge_hash=_hash(challenge), purpose=purpose)
        .first()
    )
    if row is None:
        return None, 'invalid'
    if user is not None and row.user_id != user.id:
        return None, 'invalid'
    if row.used_at is not None or row.expires_at <= now:
        return row, 'expired'
    if row.attempts >= MAX_ATTEMPTS:
        return row, 'locked'
    if row.code_hash != _hash(code):
        row.attempts += 1
        row.save(update_fields=['attempts'])
        return row, 'locked' if row.attempts >= MAX_ATTEMPTS else 'invalid'
    row.used_at = now
    row.save(update_fields=['used_at'])
    return row, None


@transaction.atomic
def resend_code(challenge):
    now = timezone.now()
    row = (
        SecurityCode.objects.select_for_update()
        .filter(challenge_hash=_hash(challenge), used_at__isnull=True)
        .first()
    )
    if row is None or row.expires_at <= now or row.attempts >= MAX_ATTEMPTS:
        return None, None
    elapsed = now - row.last_sent_at
    if elapsed < RESEND_WAIT:
        raise SecurityCooldown((RESEND_WAIT - elapsed).total_seconds())
    code = generate_code()
    row.code_hash = _hash(code)
    row.last_sent_at = now
    row.expires_at = now + CODE_TTL
    row.save(update_fields=['code_hash', 'last_sent_at', 'expires_at'])
    return row, code


def code_error_message(error):
    if error == 'expired':
        return 'That code has expired. Request a new one.'
    if error == 'locked':
        return 'Too many attempts. Request a new code.'
    return 'That code is incorrect.'


def touch_rotated_session(sid, refresh_jti):
    if not sid or not refresh_jti:
        return
    AuthSession.objects.filter(pk=sid, revoked_at__isnull=True).update(
        refresh_jti=refresh_jti,
        last_seen=timezone.now(),
    )


def recovery_email_error(user, email):
    try:
        validate_email(email)
    except ValidationError:
        return 'Enter a valid email address.'
    if email == user.email.lower():
        return 'Use an email that is different from your sign-in email.'
    if User.objects.filter(email__iexact=email).exists():
        return 'That email is already used by an account.'
    if User.objects.filter(recovery_email__iexact=email).exclude(pk=user.pk).exists():
        return 'That email is already used for account recovery.'
    return None
