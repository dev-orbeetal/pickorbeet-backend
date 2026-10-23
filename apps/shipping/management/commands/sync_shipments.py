"""
Poll Steadfast for shipments that have not reached a final status.

Webhooks are the primary channel; run this from cron as a fallback, e.g.

    */15 * * * * cd /srv/pickorbeet && venv/bin/python manage.py sync_shipments
"""
import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.shipping.models import Shipment
from apps.shipping.services import FINAL_STATUSES, ShipmentError, refresh_shipment
from apps.shipping.steadfast import SteadfastClient


class Command(BaseCommand):
    help = 'Refresh the courier status of shipments that are still on the way.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=200, help='Maximum shipments to check (default 200).')
        parser.add_argument('--min-age', type=int, default=300,
                            help='Skip shipments checked within this many seconds (default 300).')
        parser.add_argument('--pause', type=float, default=0.25,
                            help='Seconds to wait between requests (default 0.25).')
        parser.add_argument('--dry-run', action='store_true', help='List what would be checked.')

    def handle(self, *args, **options):
        client = SteadfastClient()
        if not client.is_configured and not options['dry_run']:
            self.stderr.write(self.style.ERROR('Steadfast API keys are not configured.'))
            return

        cutoff = timezone.now() - timedelta(seconds=options['min_age'])
        queryset = (
            Shipment.objects.exclude(status__in=FINAL_STATUSES)
            .exclude(consignment_id='', tracking_code='')
            .filter(Q(last_checked_at__isnull=True) | Q(last_checked_at__lt=cutoff))
            .select_related('order')
            .order_by('last_checked_at')[:options['limit']]
        )

        checked = changed = failed = 0
        for shipment in queryset:
            if options['dry_run']:
                self.stdout.write(f'{shipment.order.order_number}  {shipment.tracking_code}  {shipment.status}')
                continue
            try:
                _, did_change = refresh_shipment(shipment, force=True, client=client)
                checked += 1
                changed += int(did_change)
            except ShipmentError as exc:
                failed += 1
                self.stderr.write(f'{shipment.order.order_number}: {exc.message}')
                if exc.code in {'courier_not_configured', 'courier_auth_failed'}:
                    break
            time.sleep(options['pause'])

        if not options['dry_run']:
            self.stdout.write(self.style.SUCCESS(
                f'Checked {checked} shipment(s): {changed} changed, {failed} failed.'
            ))
