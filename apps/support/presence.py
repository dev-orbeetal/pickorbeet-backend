"""Staff are online while a support socket is connected.

Gunicorn serves the API and Daphne serves the socket, so the count lives in
Redis. Tests keep it in memory.
"""
import logging
import time

from django.conf import settings

logger = logging.getLogger(__name__)

_KEY = 'support:staff'
_TTL = 45
_local = {}


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
