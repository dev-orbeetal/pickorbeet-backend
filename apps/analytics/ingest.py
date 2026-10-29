"""Turn a collect payload into a visitor and a page view.

Geo fields are applied only when the caller has already checked the ingest
secret. The raw IP address is never written.
"""
import re
from urllib.parse import parse_qs, unquote, urlsplit

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from user_agents import parse as parse_user_agent

from .models import PageView, Visitor

STAFF_ROLES = {'seller', 'accountant', 'super_admin'}
MAX_DURATION_MS = 30 * 60 * 1000
CHANNELS = {'web', 'app'}
UTM_FIELDS = ('utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term')
SKIP_PREFIXES = ('/admin', '/api', '/django-admin', '/_next', '/static', '/media')
OWN_HOSTS = {
    'pickorbeet.com',
    'www.pickorbeet.com',
    'admin.pickorbeet.com',
    'server.pickorbeet.com',
    'localhost',
    '127.0.0.1',
}
BOT_MARKERS = (
    'googlebot', 'bingbot', 'yandexbot', 'baiduspider', 'duckduckbot',
    'facebookexternalhit', 'facebot', 'twitterbot', 'linkedinbot',
    'slackbot', 'telegrambot', 'bytespider', 'petalbot', 'ahrefsbot',
    'semrushbot', 'dotbot', 'headlesschrome', 'python-requests',
    'curl/', 'wget/', 'go-http-client', 'crawler', 'spider', 'slurp',
    'whatsapp/',
)
BOT_TOKEN = re.compile(r'(?:^|[^a-z0-9])bot(?:[^a-z0-9]|$)', re.I)
SEARCH_HOSTS = (
    'google.', 'bing.com', 'yahoo.', 'duckduckgo.', 'baidu.com', 'yandex.',
)
NON_SEARCH_HOSTS = ('play.google.', 'mail.google.', 'accounts.google.', 'drive.google.')


def is_prefetch(request):
    purpose = ' '.join(
        request.headers.get(name, '')
        for name in ('Purpose', 'Sec-Purpose', 'X-Purpose', 'X-Moz')
    ).lower()
    return 'prefetch' in purpose or 'preview' in purpose


def is_bot_user_agent(user_agent):
    lowered = (user_agent or '').lower()
    if not lowered:
        return False
    if BOT_TOKEN.search(lowered) or any(marker in lowered for marker in BOT_MARKERS):
        return True
    return parse_user_agent(lowered).is_bot


def parse_device(user_agent):
    """Return device fields, or None when the client is a bot."""
    if is_bot_user_agent(user_agent):
        return None
    if not user_agent:
        return {'device_type': 'desktop', 'browser': 'Unknown', 'os': 'Unknown'}
    parsed = parse_user_agent(user_agent[:1000])
    if parsed.is_bot:
        return None
    if parsed.is_tablet:
        device_type = 'tablet'
    elif parsed.is_mobile:
        device_type = 'mobile'
    else:
        device_type = 'desktop'
    return {
        'device_type': device_type,
        'browser': (parsed.browser.family or 'Unknown')[:64],
        'os': (parsed.os.family or 'Unknown')[:64],
    }


def normalize_path(raw):
    """Strip the query string and collapse high-cardinality order URLs."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    value = raw.strip()
    if '://' in value:
        path = urlsplit(value).path or '/'
    else:
        path = value.split('?', 1)[0].split('#', 1)[0]
    path = unquote(path)
    if not path.startswith('/'):
        path = '/' + path
    while '//' in path:
        path = path.replace('//', '/')
    if len(path) > 1 and path.endswith('/'):
        path = path.rstrip('/')
    lowered = path.lower()
    for prefix in SKIP_PREFIXES:
        if lowered == prefix or lowered.startswith(prefix + '/'):
            return None
    segments = path.split('/')
    if len(segments) >= 3 and segments[1] == 'order-success' and segments[2]:
        path = '/order-success/:order'
    return path[:500]


def referrer_host(raw):
    if not isinstance(raw, str) or not raw.strip():
        return ''
    value = raw.strip()
    try:
        host = urlsplit(value if '://' in value else f'//{value}').hostname or ''
    except ValueError:
        return ''
    host = host.lower()[:255]
    if host in OWN_HOSTS:
        return ''
    return host


def classify_source(host):
    if not host:
        return 'direct'
    if 'whatsapp' in host or host == 'wa.me' or host.endswith('.wa.me'):
        return 'whatsapp'
    if 'instagram.' in host or host.endswith('instagram.com'):
        return 'instagram'
    if (
        'facebook.' in host or host.endswith('fb.com') or host.endswith('fb.me')
        or host == 'fb.com' or host == 'fb.me'
    ):
        return 'facebook'
    if any(marker in host for marker in NON_SEARCH_HOSTS):
        return 'other'
    if any(marker in host for marker in SEARCH_HOSTS):
        return 'search'
    return 'other'


def _clean_label(value, limit):
    if not isinstance(value, str):
        return ''
    value = ' '.join(value.replace('\x00', ' ').split())
    return value[:limit]


def _query_values(path):
    if not isinstance(path, str) or '?' not in path:
        return {}
    query = path.split('?', 1)[1].split('#', 1)[0]
    parsed = parse_qs(query, keep_blank_values=False)
    return {key: values[0] for key, values in parsed.items() if values}


def utm_values(data, raw_path):
    query = _query_values(raw_path if isinstance(raw_path, str) else '')
    return {
        field: _clean_label(data.get(field) or query.get(field, ''), 120)
        for field in UTM_FIELDS
    }


def _clean_country(value):
    if not isinstance(value, str):
        return ''
    value = value.strip().upper()
    if len(value) == 2 and value.isalpha():
        return value
    return ''


def _clean_place(value):
    if not isinstance(value, str):
        return ''
    return _clean_label(unquote(value), 120)


def browser_user_agent(request):
    """Prefer the shopper's UA forwarded by the Vercel collector."""
    original = request.headers.get('X-Original-User-Agent') or ''
    if original:
        return original[:1000]
    return (request.headers.get('User-Agent') or '')[:1000]


def record_collect(data, *, user, user_agent, trust_geo):
    """Store a page view or update its duration.

    Returns ``stored``, ``ignored``, or ``duplicate``. Staff, bots, and
    non-page paths are ignored. A repeated event id is a duplicate.
    """
    if user is not None and getattr(user, 'role', '') in STAFF_ROLES:
        return 'ignored'

    kind = data.get('type')
    if kind == 'engagement':
        return _record_engagement(data)

    device = parse_device(user_agent)
    if device is None:
        return 'ignored'

    raw_path = data.get('path') or ''
    path = normalize_path(raw_path)
    if path is None:
        return 'ignored'

    customer = user if user is not None and getattr(user, 'role', '') == 'customer' else None
    now = timezone.now()
    channel = data.get('channel') or 'web'
    if channel not in CHANNELS:
        channel = 'web'
    host = referrer_host(data.get('referrer') or '')
    geo = {
        'country_code': _clean_country(data.get('country')) if trust_geo else '',
        'region': _clean_place(data.get('region')) if trust_geo else '',
        'city': _clean_place(data.get('city')) if trust_geo else '',
    }

    try:
        with transaction.atomic():
            visitor, _created = Visitor.objects.get_or_create(
                visitor_key=data['visitor_id'],
                defaults={
                    'first_seen': now,
                    'last_seen': now,
                    'channel': channel,
                    'pageview_count': 0,
                    'user': customer,
                },
            )
            pageview = PageView.objects.create(
                event_id=data['event_id'],
                occurred_at=now,
                visitor=visitor,
                session_key=data['session_id'],
                user=customer,
                path=path,
                title=_clean_label(data.get('title') or '', 300),
                referrer_host=host,
                source=classify_source(host),
                channel=channel,
                duration_ms=None,
                **utm_values(data, raw_path),
                **geo,
                **device,
            )
            _fill_previous_duration(pageview)
            _touch_visitor(visitor, now, customer)
            if customer is not None:
                PageView.objects.filter(visitor=visitor, user__isnull=True).update(user=customer)
    except IntegrityError:
        return 'duplicate'
    return 'stored'


def _record_engagement(data):
    duration = data.get('duration_ms')
    if duration is None:
        return 'ignored'
    duration = max(0, min(int(duration), MAX_DURATION_MS))
    if duration <= 0:
        return 'ignored'
    updated = PageView.objects.filter(
        event_id=data['event_id'],
        visitor__visitor_key=data['visitor_id'],
    ).update(duration_ms=duration)
    return 'stored' if updated else 'ignored'


def _fill_previous_duration(pageview):
    previous = (
        PageView.objects.filter(visitor=pageview.visitor, session_key=pageview.session_key)
        .exclude(pk=pageview.pk)
        .order_by('-occurred_at', '-pk')
        .first()
    )
    if previous is None or previous.duration_ms is not None:
        return
    delta = int((pageview.occurred_at - previous.occurred_at).total_seconds() * 1000)
    if 0 < delta <= MAX_DURATION_MS:
        previous.duration_ms = delta
        previous.save(update_fields=['duration_ms'])


def _touch_visitor(visitor, now, customer):
    visitor.last_seen = now
    visitor.pageview_count = F('pageview_count') + 1
    update_fields = ['last_seen', 'pageview_count']
    if customer is not None and visitor.user_id is None:
        visitor.user = customer
        update_fields.append('user')
    visitor.save(update_fields=update_fields)
