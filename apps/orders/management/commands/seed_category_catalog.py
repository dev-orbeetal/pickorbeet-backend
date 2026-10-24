"""Add catalog products until every department has at least ten.

Reads apps/orders/catalog_assets/manifest.json and the JPEGs beside it.
Existing SKUs are left alone, including price and stock. Safe to re-run,
and it does not require DEBUG.
"""
import json
import shutil
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.products.models import Category, Product, ProductImage

ASSETS = Path(__file__).resolve().parents[2] / 'catalog_assets'
MINIMUM = 10


class Command(BaseCommand):
    help = 'Add missing products so each category has at least ten, with photos and descriptions.'

    def handle(self, *args, **options):
        manifest_path = ASSETS / 'manifest.json'
        if not manifest_path.exists():
            raise CommandError(f'Missing {manifest_path}. Run apps/orders/catalog_assets/fetch.py first.')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        grouped = {}
        for item in manifest:
            grouped.setdefault(item['category'], []).append(item)

        created = 0
        with transaction.atomic():
            for name, items in grouped.items():
                category = Category.objects.filter(name=name).first()
                if category is None:
                    self.stdout.write(self.style.WARNING(f'Skipped unknown category {name}'))
                    continue
                have = category.products.filter(is_active=True).count()
                added_here = 0
                for item in items:
                    if have >= MINIMUM:
                        break
                    if Product.objects.filter(sku=item['sku']).exists():
                        continue
                    if self._create(category, item):
                        have += 1
                        added_here += 1
                        created += 1
                self.stdout.write(f'{name}: {have} products ({added_here} added)')
                if have < MINIMUM:
                    self.stdout.write(self.style.WARNING(f'  {name} is still under {MINIMUM}'))
        self.stdout.write(self.style.SUCCESS(f'Catalog seed added {created} products.'))

    def _create(self, category, item):
        filename = item['image']
        source = ASSETS / 'images' / filename
        if not source.exists():
            self.stdout.write(self.style.WARNING(f'  Missing image for {item["sku"]}'))
            return False
        target = Path(settings.MEDIA_ROOT) / 'catalog' / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.stat().st_size != source.stat().st_size:
            shutil.copyfile(source, target)
        compare = item.get('compare') or None
        product = Product(
            sku=item['sku'],
            barcode=item['sku'],
            name=item['name'],
            category=category,
            price=Decimal(item['price']),
            compare_price=Decimal(compare) if compare else None,
            short_description=item['short'][:500],
            description=item['description'],
            stock_quantity=int(item['stock']),
            is_active=True,
            is_featured=False,
        )
        product.save()
        ProductImage.objects.create(
            product=product,
            image=f'catalog/{filename}',
            alt_text=item['name'][:255],
            is_primary=True,
            display_order=0,
        )
        return True
