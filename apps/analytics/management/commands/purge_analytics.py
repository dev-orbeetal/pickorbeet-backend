"""Drop raw page views older than the retention window. Visitor rows stay."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.analytics.models import PageView


class Command(BaseCommand):
    help = 'Delete page views older than N days (default 180). Visitor first and last seen are kept.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=180, help='Keep page views newer than this many days.')

    def handle(self, *args, **options):
        days = options['days']
        if days < 1:
            self.stderr.write(self.style.ERROR('--days must be at least 1.'))
            return
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _detail = PageView.objects.filter(occurred_at__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f'Deleted {deleted} page views older than {days} days.'))
