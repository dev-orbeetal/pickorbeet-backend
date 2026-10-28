"""Staff aggregates. Day boundaries are Asia/Dhaka."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Count, Max, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.orders.models import Order

from .models import PageView, Visitor

DHAKA = ZoneInfo('Asia/Dhaka')
MAX_RANGE_DAYS = 366

DIMENSIONS = {
    'page': 'path',
    'country': 'country_code',
    'region': 'region',
    'city': 'city',
    'device': 'device_type',
    'browser': 'browser',
    'os': 'os',
    'source': 'source',
    'utm_source': 'utm_source',
    'utm_campaign': 'utm_campaign',
}

KPI_KEYS = (
    'visitors',
    'pageviews',
    'sessions',
    'bounce_rate',
    'avg_duration_ms',
    'pages_per_session',
    'new_visitors',
    'returning_visitors',
    'logged_in_visitors',
)


def parse_range(params):
    today = timezone.localdate()
    raw_from = (params.get('from') or '').strip()
    raw_to = (params.get('to') or '').strip()
    try:
        end = datetime.strptime(raw_to, '%Y-%m-%d').date() if raw_to else today
        start = datetime.strptime(raw_from, '%Y-%m-%d').date() if raw_from else end - timedelta(days=6)
    except ValueError as exc:
        raise ValidationError({'detail': 'Use dates as YYYY-MM-DD.'}) from exc
    if start > end:
        start, end = end, start
    if (end - start).days > MAX_RANGE_DAYS:
        start = end - timedelta(days=MAX_RANGE_DAYS)
    return start, end, *bounds(start, end)


def bounds(start, end):
    start_dt = datetime.combine(start, time.min, tzinfo=DHAKA)
    end_dt = datetime.combine(end + timedelta(days=1), time.min, tzinfo=DHAKA)
    return start_dt, end_dt


def previous_bounds(start, end):
    length = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=length - 1)
    return prev_start, prev_end, *bounds(prev_start, prev_end)


def overview(start, end):
    start_dt, end_dt = bounds(start, end)
    prev_start, prev_end, prev_start_dt, prev_end_dt = previous_bounds(start, end)
    current = window_metrics(start_dt, end_dt)
    previous = window_metrics(prev_start_dt, prev_end_dt)
    return {
        'from': start.isoformat(),
        'to': end.isoformat(),
        'timezone': 'Asia/Dhaka',
        'active_now': active_now(),
        'kpis': current,
        'previous': previous,
        'change': {key: percent_change(current[key], previous[key]) for key in KPI_KEYS},
        'series': daily_series(start, end, start_dt, end_dt),
    }


def window_metrics(start_dt, end_dt):
    qs = PageView.objects.filter(occurred_at__gte=start_dt, occurred_at__lt=end_dt)
    pageviews = qs.count()
    visitors = qs.values('visitor_id').distinct().count()
    sessions = qs.values('session_key').distinct().count()
    singles = qs.values('session_key').annotate(n=Count('id')).filter(n=1).count() if sessions else 0
    visitor_ids = qs.values('visitor_id')
    return {
        'visitors': visitors,
        'pageviews': pageviews,
        'sessions': sessions,
        'bounce_rate': round(singles / sessions * 100, 1) if sessions else 0,
        'avg_duration_ms': average_duration_ms(qs),
        'pages_per_session': round(pageviews / sessions, 2) if sessions else 0,
        'new_visitors': Visitor.objects.filter(
            id__in=visitor_ids, first_seen__gte=start_dt, first_seen__lt=end_dt,
        ).count(),
        'returning_visitors': Visitor.objects.filter(
            id__in=visitor_ids, first_seen__lt=start_dt,
        ).count(),
        'logged_in_visitors': qs.exclude(user_id__isnull=True).values('user_id').distinct().count(),
    }


def active_now():
    since = timezone.now() - timedelta(minutes=5)
    return PageView.objects.filter(occurred_at__gte=since).values('visitor_id').distinct().count()


def percent_change(current, previous):
    if not previous:
        return None
    return round((current - previous) / previous * 100, 1)


def average_duration_ms(qs):
    durations = []
    current_key = None
    first = last = None
    last_duration = None
    rows = qs.order_by('session_key', 'occurred_at', 'pk').values_list(
        'session_key', 'occurred_at', 'duration_ms',
    )
    for key, occurred, duration in rows.iterator():
        if current_key is None:
            current_key, first, last, last_duration = key, occurred, occurred, duration
            continue
        if key != current_key:
            durations.append(_session_duration(first, last, last_duration))
            current_key, first, last, last_duration = key, occurred, occurred, duration
        else:
            last = occurred
            last_duration = duration
    if current_key is not None:
        durations.append(_session_duration(first, last, last_duration))
    positive = [item for item in durations if item > 0]
    if not positive:
        return 0
    return int(round(sum(positive) / len(positive)))


def _session_duration(first, last, last_duration):
    span = int((last - first).total_seconds() * 1000)
    return span + (last_duration or 0)


def daily_series(start, end, start_dt, end_dt):
    from django.db.models.functions import TruncDay

    rows = (
        PageView.objects.filter(occurred_at__gte=start_dt, occurred_at__lt=end_dt)
        .annotate(day=TruncDay('occurred_at', tzinfo=DHAKA))
        .values('day')
        .annotate(
            pageviews=Count('id'),
            visitors=Count('visitor_id', distinct=True),
            sessions=Count('session_key', distinct=True),
        )
    )
    by_day = {_day_key(row['day']): row for row in rows}
    series = []
    cursor = start
    while cursor <= end:
        key = cursor.isoformat()
        row = by_day.get(key)
        series.append({
            'date': key,
            'visitors': row['visitors'] if row else 0,
            'pageviews': row['pageviews'] if row else 0,
            'sessions': row['sessions'] if row else 0,
        })
        cursor += timedelta(days=1)
    return series


def _day_key(value):
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = value.astimezone(DHAKA)
        return value.date().isoformat()
    return value.isoformat()


def breakdown(start, end, dimension):
    field = DIMENSIONS.get(dimension)
    if field is None:
        raise ValidationError({'dimension': 'Unknown dimension.'})
    start_dt, end_dt = bounds(start, end)
    qs = PageView.objects.filter(occurred_at__gte=start_dt, occurred_at__lt=end_dt)
    if dimension in ('utm_source', 'utm_campaign'):
        qs = qs.exclude(**{field: ''})
    rows = (
        qs.values(field)
        .annotate(pageviews=Count('id'), visitors=Count('visitor_id', distinct=True))
        .order_by('-pageviews', field)[:20]
    )
    return {
        'dimension': dimension,
        'results': [
            {
                'label': row[field] or 'Unknown',
                'pageviews': row['pageviews'],
                'visitors': row['visitors'],
            }
            for row in rows
        ],
    }


def customers(start, end, query):
    start_dt, end_dt = bounds(start, end)
    qs = PageView.objects.filter(
        occurred_at__gte=start_dt,
        occurred_at__lt=end_dt,
        user__isnull=False,
        user__role='customer',
    )
    if query:
        qs = qs.filter(
            Q(user__email__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
        )
    grouped = list(
        qs.values('user_id', 'user__email', 'user__first_name', 'user__last_name')
        .annotate(pageviews=Count('id'), last_seen=Max('occurred_at'))
        .order_by('-last_seen')[:50]
    )
    user_ids = [row['user_id'] for row in grouped]
    latest = {}
    if user_ids:
        hits = (
            PageView.objects.filter(
                user_id__in=user_ids,
                occurred_at__gte=start_dt,
                occurred_at__lt=end_dt,
            )
            .order_by('user_id', '-occurred_at')
            .distinct('user_id')
        )
        latest = {hit.user_id: hit for hit in hits}
    results = []
    for row in grouped:
        hit = latest.get(row['user_id'])
        results.append({
            'user_id': str(row['user_id']),
            'name': f"{row['user__first_name']} {row['user__last_name']}".strip(),
            'email': row['user__email'],
            'last_seen': row['last_seen'].isoformat(),
            'pageviews': row['pageviews'],
            'last_path': hit.path if hit else '',
            'country': hit.country_code if hit else '',
            'device': hit.device_type if hit else '',
        })
    return {'count': len(results), 'results': results}


def timeline(user):
    rows = PageView.objects.filter(user=user).order_by('-occurred_at')[:100]
    return {
        'user': {
            'id': str(user.id),
            'name': user.full_name,
            'email': user.email,
        },
        'results': [
            {
                'occurred_at': row.occurred_at.isoformat(),
                'path': row.path,
                'title': row.title,
                'country': row.country_code,
                'region': row.region,
                'city': row.city,
                'device': row.device_type,
                'browser': row.browser,
                'os': row.os,
                'source': row.source,
                'duration_ms': row.duration_ms,
            }
            for row in rows
        ],
    }


def live_feed():
    rows = PageView.objects.select_related('user').order_by('-occurred_at')[:50]
    results = []
    for row in rows:
        account = None
        if row.user_id and row.user.role == 'customer':
            account = {
                'id': str(row.user_id),
                'name': row.user.full_name,
                'email': row.user.email,
            }
        results.append({
            'occurred_at': row.occurred_at.isoformat(),
            'path': row.path,
            'title': row.title,
            'country': row.country_code,
            'region': row.region,
            'city': row.city,
            'device': row.device_type,
            'browser': row.browser,
            'source': row.source,
            'user': account,
        })
    return {'results': results}


def funnel(start, end):
    start_dt, end_dt = bounds(start, end)
    qs = PageView.objects.filter(occurred_at__gte=start_dt, occurred_at__lt=end_dt)
    steps = [
        ('product', 'Product views', qs.filter(path__startswith='/product/')),
        ('cart', 'Cart', qs.filter(Q(path='/cart') | Q(path__startswith='/cart/'))),
        ('checkout', 'Checkout', qs.filter(Q(path='/checkout') | Q(path__startswith='/checkout/'))),
    ]
    results = []
    for key, label, step_qs in steps:
        results.append({
            'key': key,
            'label': label,
            'pageviews': step_qs.count(),
            'visitors': step_qs.values('visitor_id').distinct().count(),
        })
    orders = Order.objects.filter(
        created_at__gte=start_dt,
        created_at__lt=end_dt,
        order_type='online',
    ).exclude(order_status='cancelled')
    order_count = orders.count()
    results.append({
        'key': 'orders',
        'label': 'Orders placed',
        'pageviews': order_count,
        'visitors': order_count,
    })
    return {'steps': results}
