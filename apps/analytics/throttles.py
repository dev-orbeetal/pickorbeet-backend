import hashlib
import secrets

from django.conf import settings
from rest_framework.throttling import ScopedRateThrottle


class AnalyticsCollectThrottle(ScopedRateThrottle):
    """Limit collect calls per shopper, without keeping the raw IP address."""

    scope = 'analytics_collect'

    def get_cache_key(self, request, view):
        ident = self._ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}

    def _ident(self, request):
        secret = getattr(settings, 'ANALYTICS_INGEST_SECRET', '') or ''
        provided = request.headers.get('X-Analytics-Secret') or ''
        forwarded = (request.headers.get('X-Visitor-Ip') or '').strip()[:64]
        if secret and forwarded and secrets.compare_digest(provided, secret):
            raw = forwarded
        else:
            raw = super().get_ident(request)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()
