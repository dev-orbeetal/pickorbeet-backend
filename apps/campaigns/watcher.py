"""Watch the catalog and start automated campaigns for arrivals, stock and price."""
import logging
from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Prefetch
from django.utils import timezone

from apps.products.models import Product, ProductImage, ProductVariant

from .models import (
    KIND_BACK_IN_STOCK,
    KIND_LOW_STOCK,
    KIND_NEW_ARRIVAL,
    KIND_PRICE_DROP,
    AutomationRule,
    Campaign,
    CampaignSettings,
    ProductWatch,
)
from .rendering import percent_off, stock_state
from .services import next_open_at, save_campaign, schedule, send_now

logger = logging.getLogger(__name__)

LOCK_NAME = 'pickorbeet:campaigns-watch'
LOCK_TIMEOUT = 4 * 60


def _redis():
    import redis

    return redis.Redis.from_url(settings.REDIS_URL, socket_timeout=5, socket_connect_timeout=5)


@contextmanager
def watch_lock():
    from redis.exceptions import LockError, RedisError

    lock = None
    try:
        lock = _redis().lock(LOCK_NAME, timeout=LOCK_TIMEOUT, blocking=False)
        acquired = lock.acquire()
    except RedisError:
        logger.warning('Catalog watch lock unavailable; running without it', exc_info=True)
        lock, acquired = None, True
    if not acquired:
        yield False
        return
    try:
        yield True
    finally:
        if lock is not None:
            try:
                lock.release()
            except (LockError, RedisError):
                logger.info('Catalog watch lock had already expired')


def _settled(product, minutes, now):
    return product.updated_at <= now - timedelta(minutes=minutes)


def _rules():
    return {rule.trigger: rule for rule in AutomationRule.objects.all()}


def _queue(rule, *, product, extra=None, product_ids=None, title=None, body=None, now=None):
    """Save an automated campaign and send it, or hold it until quiet hours end."""
    extra = extra or {}
    ids = [str(value) for value in (product_ids or ([product.pk] if product is not None else []))]
    digest = len(ids) > 1
    campaign = save_campaign(
        {
            'kind': rule.trigger,
            'trigger': rule.trigger,
            'title': title or (rule.digest_title if digest and rule.digest_title else rule.title),
            'body': body or (rule.digest_body if digest and rule.digest_body else rule.body),
            'cta_label': rule.cta_label,
            'audience': rule.audience,
            'product_id': product.pk if product is not None else None,
            'product_ids': ids,
            'context': extra,
            'name': '',
        },
    )
    Campaign.objects.filter(pk=campaign.pk).update(source=Campaign.SOURCE_AUTOMATION)
    campaign.source = Campaign.SOURCE_AUTOMATION
    open_at = next_open_at(now)
    settings = CampaignSettings.load()
    cap = settings.daily_cap if campaign.source == Campaign.SOURCE_AUTOMATION else None
    if open_at is not None:
        schedule(campaign, open_at)
        return campaign
    return send_now(campaign, daily_cap=cap)


def _snapshot(watch, *, units, available, price, low_alerted, announced_at=None, primed=True):
    watch.units = units
    watch.available = available
    watch.price = price
    watch.low_alerted = low_alerted
    watch.primed = primed
    fields = ['units', 'available', 'price', 'low_alerted', 'primed', 'checked_at']
    if announced_at is not None:
        watch.announced_at = announced_at
        fields.append('announced_at')
    watch.save(update_fields=fields)


def watch_catalog(now=None):
    """Compare live products to the last snapshot and queue customer notifications.

    Returns a dict of how many campaigns each trigger started. A run that could
    not take the lock is ``{'skipped': True}``.
    """
    with watch_lock() as acquired:
        if not acquired:
            return {'skipped': True}
        return _watch(now or timezone.now())


def _watch(now):
    settings = CampaignSettings.load()
    rules = _rules()
    started = {KIND_NEW_ARRIVAL: 0, KIND_LOW_STOCK: 0, KIND_BACK_IN_STOCK: 0, KIND_PRICE_DROP: 0}

    products = list(
        Product.objects.filter(is_active=True)
        .select_related('category')
        .prefetch_related(
            Prefetch('images', queryset=ProductImage.objects.order_by('-is_primary', 'display_order')),
            Prefetch('variants', queryset=ProductVariant.objects.filter(is_active=True)),
        )
    )
    watches = ProductWatch.objects.in_bulk([product.pk for product in products])
    arrivals = []
    stock_events = []

    for product in products:
        units, available = stock_state(product)
        price = Decimal(product.price or 0)
        watch = watches.get(product.pk)

        if watch is None:
            if _settled(product, settings.arrival_settle_minutes, now):
                arrivals.append(product)
            continue

        if not watch.primed:
            _snapshot(
                watch, units=units, available=available, price=price,
                low_alerted=units > 0 and units <= (rules.get(KIND_LOW_STOCK).threshold if KIND_LOW_STOCK in rules else 0),
            )
            continue

        if watch.announced_at is None:
            if _settled(product, settings.arrival_settle_minutes, now):
                arrivals.append(product)
            continue

        low_rule = rules.get(KIND_LOW_STOCK)
        back_rule = rules.get(KIND_BACK_IN_STOCK)
        drop_rule = rules.get(KIND_PRICE_DROP)

        if back_rule and back_rule.enabled and (not watch.available) and available:
            stock_events.append((KIND_BACK_IN_STOCK, product, {'old_price': str(watch.price)}, units, available, price))
        elif (
            low_rule and low_rule.enabled and not watch.low_alerted
            and units > 0 and units <= low_rule.threshold
        ):
            stock_events.append((KIND_LOW_STOCK, product, {'stock': str(units)}, units, available, price))

        if drop_rule and drop_rule.enabled and watch.price and price < watch.price:
            drop = percent_off(watch.price, price)
            if drop >= drop_rule.threshold:
                stock_events.append(
                    (KIND_PRICE_DROP, product, {'old_price': str(watch.price), 'discount': str(drop)}, units, available, price)
                )

        low_alerted = watch.low_alerted
        if units > (low_rule.threshold if low_rule else 0):
            low_alerted = False
        _snapshot(watch, units=units, available=available, price=price, low_alerted=low_alerted)

    arrival_rule = rules.get(KIND_NEW_ARRIVAL)
    if arrival_rule and arrival_rule.enabled and arrivals:
        if len(arrivals) == 1:
            product = arrivals[0]
            _queue(arrival_rule, product=product, extra={'count': '1', 'others': '0'}, now=now)
        else:
            first = arrivals[0]
            others = len(arrivals) - 1
            _queue(
                arrival_rule, product=first,
                extra={'count': str(len(arrivals)), 'others': str(others)},
                product_ids=[item.pk for item in arrivals],
                now=now,
            )
        started[KIND_NEW_ARRIVAL] = 1
        for product in arrivals:
            units, available = stock_state(product)
            watch, _ = ProductWatch.objects.get_or_create(
                product=product,
                defaults={'units': units, 'available': available, 'price': product.price or 0, 'primed': True},
            )
            _snapshot(
                watch, units=units, available=available, price=product.price or 0,
                low_alerted=False, announced_at=now, primed=True,
            )

    for trigger, product, extra, units, available, price in stock_events:
        rule = rules.get(trigger)
        if rule is None or not rule.enabled:
            continue
        try:
            _queue(rule, product=product, extra=extra, now=now)
            started[trigger] += 1
        except Exception:
            logger.warning('Automated %s for %s failed', trigger, product.pk, exc_info=True)
        watch = watches.get(product.pk)
        low_alerted = watch.low_alerted if watch else False
        if trigger == KIND_LOW_STOCK:
            low_alerted = True
        if watch:
            _snapshot(watch, units=units, available=available, price=price, low_alerted=low_alerted)

    return started
