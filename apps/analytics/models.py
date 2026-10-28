import uuid

from django.conf import settings
from django.db import models


class Visitor(models.Model):
    """One browser. Clearing site data starts a new visitor."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visitor_key = models.UUIDField(unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='analytics_visitors',
    )
    first_seen = models.DateTimeField(db_index=True)
    last_seen = models.DateTimeField(db_index=True)
    channel = models.CharField(max_length=16, default='web')
    pageview_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-last_seen']

    def __str__(self):
        return str(self.visitor_key)


class PageView(models.Model):
    """One route change on the shop website."""

    event_id = models.UUIDField(unique=True)
    occurred_at = models.DateTimeField(db_index=True)
    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE, related_name='pageviews')
    session_key = models.UUIDField(db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='analytics_pageviews',
    )
    path = models.CharField(max_length=500, db_index=True)
    title = models.CharField(max_length=300, blank=True)
    referrer_host = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=32, default='direct', db_index=True)
    utm_source = models.CharField(max_length=120, blank=True, db_index=True)
    utm_medium = models.CharField(max_length=120, blank=True)
    utm_campaign = models.CharField(max_length=120, blank=True, db_index=True)
    utm_content = models.CharField(max_length=120, blank=True)
    utm_term = models.CharField(max_length=120, blank=True)
    country_code = models.CharField(max_length=2, blank=True, db_index=True)
    region = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120, blank=True)
    device_type = models.CharField(max_length=16, db_index=True)
    browser = models.CharField(max_length=64, blank=True)
    os = models.CharField(max_length=64, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    channel = models.CharField(max_length=16, default='web')

    class Meta:
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['occurred_at', 'path']),
            models.Index(fields=['visitor', 'occurred_at']),
            models.Index(fields=['user', 'occurred_at']),
            models.Index(fields=['session_key', 'occurred_at']),
            models.Index(fields=['country_code', 'occurred_at']),
            models.Index(fields=['device_type', 'occurred_at']),
        ]

    def __str__(self):
        return f'{self.path} @ {self.occurred_at:%Y-%m-%d %H:%M}'
