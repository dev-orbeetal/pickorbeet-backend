"""Reload Steadfast's thana list. Celery beat also does this weekly."""
from django.core.management.base import BaseCommand, CommandError

from apps.shipping.services import ShipmentError, refresh_police_stations
from apps.shipping.steadfast import SteadfastClient


class Command(BaseCommand):
    help = "Download Steadfast's police stations (thanas) for matching delivery addresses."

    def handle(self, *args, **options):
        client = SteadfastClient()
        if not client.is_configured:
            raise CommandError('Steadfast API keys are not configured.')
        try:
            result = refresh_police_stations(client=client)
        except ShipmentError as exc:
            raise CommandError(exc.message) from exc
        self.stdout.write(self.style.SUCCESS(
            f"Saved {result['stations']} police stations in {result['districts']} districts."
        ))
