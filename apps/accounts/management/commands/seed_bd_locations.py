"""
Idempotent upsert of Bangladesh divisions, districts, and post offices.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.accounts.models import BdDistrict, BdDivision, BdPostOffice

DATA_PATH = Path(__file__).resolve().parents[2] / 'data' / 'bd_locations.json'


class Command(BaseCommand):
    help = 'Seed Bangladesh division → district → post office catalog'

    def add_arguments(self, parser):
        parser.add_argument(
            '--path',
            type=str,
            default=str(DATA_PATH),
            help='Path to bd_locations.json',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        path = Path(options['path'])
        if not path.exists():
            raise SystemExit(f'Fixture not found: {path}')

        payload = json.loads(path.read_text(encoding='utf-8'))
        divisions = payload.get('divisions') or []
        div_count = dist_count = office_count = 0

        for index, div_data in enumerate(divisions):
            name = (div_data.get('name') or '').strip()
            if not name:
                continue
            slug = (div_data.get('slug') or slugify(name)).strip()
            division, _ = BdDivision.objects.update_or_create(
                slug=slug,
                defaults={
                    'name': name,
                    'display_order': div_data.get('display_order') or index + 1,
                },
            )
            div_count += 1
            seen_district_slugs = set()
            for dist_data in div_data.get('districts') or []:
                dist_name = (dist_data.get('name') or '').strip()
                if not dist_name:
                    continue
                dist_slug = (dist_data.get('slug') or slugify(dist_name)).strip()
                seen_district_slugs.add(dist_slug)
                district, _ = BdDistrict.objects.update_or_create(
                    division=division,
                    slug=dist_slug,
                    defaults={'name': dist_name},
                )
                dist_count += 1
                for office_data in dist_data.get('post_offices') or []:
                    office_name = (office_data.get('name') or '').strip()
                    postal_code = str(office_data.get('postal_code') or '').strip()
                    if not office_name or not postal_code:
                        continue
                    BdPostOffice.objects.update_or_create(
                        district=district,
                        name=office_name,
                        postal_code=postal_code,
                        defaults={},
                    )
                    office_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {div_count} divisions, {dist_count} districts, {office_count} post offices.'
        ))
