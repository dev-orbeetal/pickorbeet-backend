"""Who is in support chat right now.

Staff presence is any staff support socket. Customer presence is that
customer's support socket, or the HTTP pulse the shop app sends while the
chat screen is open. Gunicorn serves the API and Daphne serves the socket,
so both counts live in Redis. Tests keep them in memory.
"""
import logging
import time

from django.conf import settings

logger = logging.getLogger(__name__)

_KEY = 'support:staff'
_CUSTOMERS = 'support:customers'
_SEEN = 'support:customer-seen'
_TTL = 45
_SEEN_TTL = 70
_local = {}
_local_customers = {}
_local_seen = {}


def _client():
    if getattr(settings, 'RUNNING_TESTS', False):
        return None
    import redis

    return redis.Redis.from_url(
        settings.REDIS_URL,
        socket_connect_timeout=0.4,
        socket_timeout=0.4,
    )


def _local_online(now):
    stale = [name for name, expiry in _local.items() if expiry < now]
    for name in stale:
        _local.pop(name, None)
    return bool(_local)


def join(channel_name):
    now = int(time.time())
    try:
        client = _client()
        if client is None:
            _local[channel_name] = now + _TTL
            return True
        client.hset(_KEY, channel_name, now + _TTL)
    except Exception:
        logger.warning('Could not mark support staff online', exc_info=True)
        _local[channel_name] = now + _TTL
    return online()


def leave(channel_name):
    try:
        client = _client()
        if client is None:
            _local.pop(channel_name, None)
            return _local_online(int(time.time()))
        client.hdel(_KEY, channel_name)
    except Exception:
        logger.warning('Could not mark support staff offline', exc_info=True)
        _local.pop(channel_name, None)
    return online()


def online():
    now = int(time.time())
    try:
        client = _client()
        if client is None:
            return _local_online(now)
        members = client.hgetall(_KEY)
        stale = [name for name, expiry in members.items() if int(expiry) < now]
        if stale:
            client.hdel(_KEY, *stale)
        return len(members) > len(stale)
    except Exception:
        logger.warning('Could not read support presence', exc_info=True)
        return _local_online(now)


def _decode(value):
    return value.decode() if isinstance(value, bytes) else str(value)


def _customer_ids(now):
    stale = [name for name, (user_id, expiry) in _local_customers.items() if expiry < now]
    for name in stale:
        _local_customers.pop(name, None)
    return {user_id for user_id, expiry in _local_customers.values()}


def _matching_customer(client, user_id, now):
    """True when this customer still has an unexpired chat connection."""
    user_id = str(user_id)
    still = False
    stale = []
    for name, raw in client.hgetall(_CUSTOMERS).items():
        text = _decode(raw)
        uid, _, expiry = text.partition('|')
        channel = _decode(name)
        if not expiry or int(expiry) < now:
            stale.append(channel)
            continue
        if uid == user_id:
            still = True
    if stale:
        client.hdel(_CUSTOMERS, *stale)
    return still


def join_customer(channel_name, user_id):
    user_id = str(user_id)
    expiry = int(time.time()) + _TTL
    try:
        client = _client()
        if client is None:
            _local_customers[channel_name] = (user_id, expiry)
            return True
        client.hset(_CUSTOMERS, channel_name, f'{user_id}|{expiry}')
    except Exception:
        logger.warning('Could not mark support customer online', exc_info=True)
        _local_customers[channel_name] = (user_id, expiry)
    return True


def leave_customer(channel_name, user_id):
    try:
        client = _client()
        if client is None:
            _local_customers.pop(channel_name, None)
            return customer_online(user_id)
        client.hdel(_CUSTOMERS, channel_name)
    except Exception:
        logger.warning('Could not mark support customer offline', exc_info=True)
        _local_customers.pop(channel_name, None)
    return customer_online(user_id)


def _seen_online(user_id, now):
    """A recent chat open or message keeps the customer online.

    A paused phone can drop its socket for a moment. That must not flip the
    admin pill to offline while the person is still in the chat.
    """
    user_id = str(user_id)
    try:
        client = _client()
        if client is None:
            expiry = _local_seen.get(user_id, 0)
            if expiry < now:
                _local_seen.pop(user_id, None)
                return False
            return True
        raw = client.get(f'{_SEEN}:{user_id}')
        if raw is None:
            return False
        return int(raw) >= now
    except Exception:
        logger.warning('Could not read support customer activity', exc_info=True)
        return _local_seen.get(user_id, 0) >= now


def touch_customer(user_id):
    """Remember that this customer is in the chat, apart from any one socket."""
    user_id = str(user_id)
    expiry = int(time.time()) + _SEEN_TTL
    join_customer(f'http:{user_id}', user_id)
    try:
        client = _client()
        if client is None:
            _local_seen[user_id] = expiry
            return
        client.set(f'{_SEEN}:{user_id}', expiry, ex=_SEEN_TTL)
    except Exception:
        logger.warning('Could not record support customer activity', exc_info=True)
        _local_seen[user_id] = expiry


def clear_customer_seen(user_id):
    """The chat screen closed, so recent activity no longer counts."""
    user_id = str(user_id)
    _local_seen.pop(user_id, None)
    try:
        client = _client()
        if client is not None:
            client.delete(f'{_SEEN}:{user_id}')
    except Exception:
        logger.warning('Could not clear support customer activity', exc_info=True)


def customer_online(user_id):
    now = int(time.time())
    if _seen_online(user_id, now):
        return True
    try:
        client = _client()
        if client is None:
            return str(user_id) in _customer_ids(now)
        return _matching_customer(client, user_id, now)
    except Exception:
        logger.warning('Could not read support customer presence', exc_info=True)
        return str(user_id) in _customer_ids(now)
