"""Rewrite sellable SKUs into color-size-number form, such as white-lg-998.

Supplier codes on the provider record stay as they are, so a later import
still recognizes the shop's own SKU. Products with no color and no size are
left unchanged. Run again safely: a code that already matches is kept.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from apps.products.models import Product, ProductVariant
from apps.products.sku_code import plan_changes


class Command(BaseCommand):
    help = 'Set product and variant SKUs from their color and size, like white-lg-998.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print the changes without saving them.',
        )

    def handle(self, *args, **options):
        products = [
            {
                'id': product.id,
                'sku': product.sku or '',
                'name': product.name,
                'color': product.color or '',
                'size': product.size or '',
                'variant_count': product.variant_count,
            }
            for product in Product.objects.annotate(variant_count=Count('variants'))
        ]
        variants = []
        for variant in ProductVariant.objects.select_related('product').prefetch_related('values'):
            labels = [value.label for value in variant.values.all()]
            if not labels:
                labels = [label for label in (variant.color, variant.size) if label]
            variants.append({
                'id': variant.id,
                'sku': variant.sku or '',
                'product_sku': variant.product.sku or '',
                'labels': labels,
            })

        product_changes, variant_changes, skipped, bumped = plan_changes(products, variants)
        self.stdout.write(
            f'products {len(product_changes)}, variants {len(variant_changes)}, '
            f'unchanged {skipped}, numbers adjusted {bumped}'
        )
        for old, new, name in self._samples(product_changes, products):
            self.stdout.write(f'  {old or "(blank)"} -> {new}  {name}')
        for row_id, old, new in variant_changes:
            self.stdout.write(f'  variant {old or "(blank)"} -> {new}')

        if options['dry_run'] or not (product_changes or variant_changes):
            return

        with transaction.atomic():
            self._park(Product, product_changes)
            self._park(ProductVariant, variant_changes)
            self._write(Product, product_changes)
            self._write(ProductVariant, variant_changes)
        self.stdout.write(self.style.SUCCESS(
            f'Updated {len(product_changes)} products and {len(variant_changes)} variants.'
        ))

    def _samples(self, changes, products):
        names = {row['id']: row['name'] for row in products}
        shown = []
        for row_id, old, new in changes[:25]:
            shown.append((old, new, names.get(row_id, '')))
        return shown

    def _park(self, model, changes):
        for row_id, _old, _new in changes:
            model.objects.filter(pk=row_id).update(sku=f'tmp-{row_id.hex}')

    def _write(self, model, changes):
        for row_id, _old, new in changes:
            model.objects.filter(pk=row_id).update(sku=new)
