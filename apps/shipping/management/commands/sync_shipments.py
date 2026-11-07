"""
Check Steadfast for shipments that have not reached a final status.

Celery beat runs the same check every two minutes (``steadfast-sync``). Use this
command to run it by hand, or from cron where beat is not running.
"""
from django.core.management.base import BaseCommand

from apps.shipping.sync import shipments_due, sync_active_shipments


class Command(BaseCommand):
    help = 'Refresh the courier status of shipments that are still on the way.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=200, help='Maximum shipments to check (default 200).')
        parser.add_argument('--min-age', type=int, default=None,
                            help='Skip shipments checked within this many seconds '
                                 '(default STEADFAST_SYNC_MIN_AGE_SECONDS).')
        parser.add_argument('--pause', type=float, default=0.25,
                            help='Seconds to wait between requests (default 0.25).')
        parser.add_argument('--force', action='store_true',
                            help='Run even while checks are paused after an API key error.')
        parser.add_argument('--dry-run', action='store_true', help='List what would be checked.')

    def handle(self, *args, **options):
        if options['dry_run']:
            for shipment in shipments_due(min_age=options['min_age'], limit=options['limit']):
                self.stdout.write(f'{shipment.order.order_number}  {shipment.tracking_code}  {shipment.status}')
            return

        result = sync_active_shipments(
            limit=options['limit'],
            min_age=options['min_age'],
            pause=options['pause'],
            trigger='command',
            force=options['force'],
        )
        skipped = result.get('skipped')
        if skipped == 'not_configured':
            self.stderr.write(self.style.ERROR('Steadfast API keys are not configured.'))
        elif skipped == 'paused':
            self.stderr.write(self.style.WARNING(
                f'Checks are paused until {result["until"]} after an API key error. Use --force to run now.'))
        elif skipped == 'locked':
            self.stderr.write(self.style.WARNING('Another check is already running.'))
        else:
            message = f'Checked {result["checked"]} shipment(s): {result["changed"]} changed, {result["failed"]} failed.'
            style = self.style.ERROR if result['error_code'] == 'courier_auth_failed' else self.style.SUCCESS
            self.stdout.write(style(message))
