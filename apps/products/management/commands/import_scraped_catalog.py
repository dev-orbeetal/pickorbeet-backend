"""
Import one scraped shop folder as a tracked catalog batch.

The other shop's quantity is not Pickorbeet stock. Products are created with
stock at zero and dealer availability off, so they list as out of stock until
you add stock or turn that batch on. Selling prices are raised by the catalog
taka bands before they are saved. Running the command again skips SKUs that
already exist, including any price changed since the import.
"""
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils.text import slugify

from apps.products.catalog_pricing import raised_catalog_prices
from apps.products.models import (
    CatalogImport, Category, Product, ProductImage, ProductSource, ProductSpecification, SubCategory,
)

PROVIDER_LABELS = dict(CatalogImport.PROVIDER_CHOICES)
CENT = Decimal('0.01')


def clip(value, limit):
    text = '' if value is None else str(value).strip()
    return text[:limit]


def as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def as_money(value):
    if value is None or value == '':
        return None
    amount = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    return amount


def safe_sku(sku):
    cleaned = re.sub(r'[^A-Za-z0-9._-]+', '-', sku).strip('.-')
    return cleaned or 'product'


def load_json(path):
    try:
        with path.open(encoding='utf-8') as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise CommandError(f'Missing {path}') from exc
    except json.JSONDecodeError as exc:
        raise CommandError(f'{path} is not valid JSON: {exc}') from exc


def inside(root, relative):
    """Resolve a catalog-relative file and refuse paths that leave the folder."""
    if not relative or not isinstance(relative, str):
        return None
    root = root.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path if path.is_file() else None


def match_key(name):
    """Fold a product title so the same item from two shops can be recognized.

    Letters from every language stay in the key. Dropping them would treat
    different Bengali titles as the same product when the English words match.
    """
    text = unicodedata.normalize('NFKC', str(name or '')).casefold()
    text = re.sub(r'[^\w]+', ' ', text, flags=re.UNICODE)
    return re.sub(r'\s+', ' ', text).strip()


def collapse_repeated_catalog_products():
    """Keep one active listing when a catalog already has the same title twice."""
    grouped = {}
    products = (
        Product.objects.filter(is_active=True, catalog_import__isnull=False)
        .select_related('catalog_import')
        .order_by('price', 'created_at')
    )
    for product in products:
        key = match_key(product.name)
        if len(key) < 10:
            continue
        grouped.setdefault(key, []).append(product)
    collapsed = 0
    for group in grouped.values():
        if len(group) < 2:
            continue
        keeper = group[0]
        record_catalog_offer(keeper, keeper)
        for other in group[1:]:
            record_catalog_offer(keeper, other)
            other.is_active = False
            other.save(update_fields=['is_active', 'updated_at'])
            collapsed += 1
        keeper.sync_lowest_source_price()
    return collapsed


def record_catalog_offer(target, source_product):
    sku = source_product.sku or ''
    if sku and ProductSource.objects.filter(sku=sku).exists():
        return
    batch = source_product.catalog_import
    if batch is None:
        return
    ProductSource.objects.create(
        product=target,
        provider=batch.provider,
        catalog_import=batch,
        sku=sku,
        price=source_product.price,
        compare_price=source_product.compare_price,
        source_url=source_product.source_url or '',
    )


def free_slug(preferred, name, sku):
    base = slugify(preferred) or slugify(name) or slugify(sku) or 'product'
    base = base[:270]
    slug = base
    number = 2
    while Product.objects.filter(slug=slug).exists():
        suffix = f'-{number}'
        slug = f'{base[:280 - len(suffix)]}{suffix}'
        number += 1
    return slug


class Command(BaseCommand):
    help = 'Import a scraped shop catalog as one tracked provider batch. Stock stays at zero.'

    def add_arguments(self, parser):
        parser.add_argument('catalog', help='Shop folder with categories.json, products.json, and images/')
        parser.add_argument(
            '--provider', required=True,
            choices=[choice for choice, _label in CatalogImport.PROVIDER_CHOICES],
        )
        parser.add_argument('--label', default='', help='Batch name. Defaults to the provider name.')

    def handle(self, *args, **options):
        root = Path(options['catalog']).expanduser().resolve()
        if not root.is_dir():
            raise CommandError(f'{root} is not a folder')
        provider = options['provider']
        categories = load_json(root / 'categories.json')
        products = load_json(root / 'products.json')
        if not isinstance(categories, list) or not isinstance(products, list):
            raise CommandError('categories.json and products.json must be lists')

        departments, subcategories = self._import_categories(root, provider, categories)
        collapsed = collapse_repeated_catalog_products()
        if collapsed:
            self.stdout.write(f'Combined {collapsed} repeated catalog listings into the cheaper one.')
        pending, skipped, errors = self._pending_products(products)
        if not pending:
            self.stdout.write(self.style.WARNING(
                f'Nothing new for {PROVIDER_LABELS[provider]}. Skipped {skipped} existing SKUs.'
            ))
            return

        label = (options['label'] or '').strip()[:120]
        if not label:
            label = self._next_label(provider)
        batch = CatalogImport.objects.create(provider=provider, label=label)
        self._index_existing_products()
        created = 0
        linked = 0
        missing_images = 0
        for index, row in enumerate(pending, start=1):
            try:
                with transaction.atomic():
                    outcome, missing = self._create_product(
                        root, provider, batch, row, departments, subcategories,
                    )
                missing_images += missing
                if outcome == 'linked':
                    linked += 1
                else:
                    created += 1
            except Exception as exc:
                errors += 1
                self.stderr.write(f'{row.get("sku")}: {exc}')
            if index % 100 == 0:
                self.stdout.write(f'  {index} of {len(pending)}')

        if created == 0 and linked == 0:
            batch.delete()
            raise CommandError(f'No products imported. {errors} failed.')

        self.stdout.write(self.style.SUCCESS(
            f'Imported {created} {label} products, linked {linked} that other providers already sell '
            f'({skipped} already in the store, {errors} failed, {missing_images} images missing).'
        ))

    def _next_label(self, provider):
        base = PROVIDER_LABELS[provider]
        existing = CatalogImport.objects.filter(provider=provider).count()
        if existing == 0:
            return base
        return f'{base} {existing + 1}'

    def _import_categories(self, root, provider, rows):
        parents = [row for row in rows if not row.get('parent_slug')]
        children = [row for row in rows if row.get('parent_slug')]
        category_floor = Category.objects.aggregate(highest=Max('display_order'))['highest'] or 0
        departments = {}
        for row in parents:
            category = self._category(root, provider, row, category_floor)
            slug = clip(row.get('slug'), 120)
            if category is not None and slug:
                departments[slug] = category

        subcategories = {}
        floors = {}
        for row in children:
            parent_slug = clip(row.get('parent_slug'), 120)
            parent = departments.get(parent_slug) or Category.objects.filter(slug=parent_slug).first()
            if parent is None:
                self.stderr.write(f'Skipping subcategory {row.get("slug")}: unknown department {parent_slug}')
                continue
            if parent.pk not in floors:
                floors[parent.pk] = parent.subcategories.aggregate(highest=Max('display_order'))['highest'] or 0
            sub = self._subcategory(root, provider, parent, row, floors[parent.pk])
            slug = clip(row.get('slug'), 120)
            if sub is not None and slug:
                subcategories[(parent_slug, slug)] = sub
        return departments, subcategories

    def _category(self, root, provider, row, floor):
        name = clip(row.get('name'), 100)
        slug = clip(row.get('slug'), 120)
        if not name:
            return None
        category = None
        if slug:
            category = Category.objects.filter(slug=slug).first()
        if category is None:
            category = Category.objects.filter(name__iexact=name).first()
        if category is None:
            try:
                with transaction.atomic():
                    category = Category.objects.create(
                        name=name,
                        slug=slug,
                        description=(row.get('description') or '') or None,
                        is_active=True,
                        is_featured=False,
                        display_order=floor + 1 + as_int(row.get('display_order')),
                    )
            except IntegrityError:
                category = Category.objects.filter(slug=slug).first() or Category.objects.filter(name__iexact=name).first()
        if category is not None:
            self._copy_image(category, 'image', root, provider, row.get('image'))
        return category

    def _subcategory(self, root, provider, parent, row, floor):
        name = clip(row.get('name'), 100)
        slug = clip(row.get('slug'), 120)
        if not name:
            return None
        sub = None
        if slug:
            sub = parent.subcategories.filter(slug=slug).first()
        if sub is None:
            sub = parent.subcategories.filter(name__iexact=name).first()
        if sub is None:
            try:
                with transaction.atomic():
                    sub = SubCategory.objects.create(
                        category=parent,
                        name=name,
                        slug=slug,
                        description=(row.get('description') or '') or None,
                        is_active=True,
                        display_order=floor + 1 + as_int(row.get('display_order')),
                    )
            except IntegrityError:
                sub = parent.subcategories.filter(slug=slug).first() or parent.subcategories.filter(name__iexact=name).first()
        if sub is not None:
            self._copy_image(sub, 'image', root, provider, row.get('image'))
        return sub

    def _copy_image(self, instance, field_name, root, provider, relative):
        if getattr(instance, field_name):
            return
        source = inside(root, relative)
        if source is None:
            return
        filename = source.name
        with source.open('rb') as handle:
            getattr(instance, field_name).save(f'imports/{provider}/{filename}', File(handle), save=True)

    def _pending_products(self, products):
        pending = []
        skipped = 0
        errors = 0
        seen = set()
        for row in products:
            if not isinstance(row, dict):
                errors += 1
                continue
            sku = clip(row.get('sku'), 50)
            if not sku or sku in seen:
                errors += 1
                self.stderr.write(f'Skipping a product with a missing or repeated SKU: {row.get("name")}')
                continue
            seen.add(sku)
            if Product.objects.filter(sku=sku).exists() or ProductSource.objects.filter(sku=sku).exists():
                skipped += 1
                continue
            pending.append(row)
        return pending, skipped, errors

    def _create_product(self, root, provider, batch, row, departments, subcategories):
        sku = clip(row.get('sku'), 50)
        name = clip(row.get('name'), 255)
        if not name:
            raise CommandError(f'{sku} has no name')
        try:
            price = as_money(row.get('price'))
        except InvalidOperation as exc:
            raise CommandError(f'{sku} has a price that is not a number') from exc
        if price is None:
            raise CommandError(f'{sku} has no price')
        try:
            compare = as_money(row.get('compare_price'))
        except InvalidOperation:
            compare = None

        category_slug = clip(row.get('category_slug'), 120)
        category = departments.get(category_slug) or Category.objects.filter(slug=category_slug).first()
        if category is None:
            raise CommandError(f'{sku} is in unknown category {category_slug or "(blank)"}')
        sub_slug = clip(row.get('subcategory_slug'), 120)
        subcategory = subcategories.get((category_slug, sub_slug)) if sub_slug else None
        if sub_slug and subcategory is None:
            subcategory = SubCategory.objects.filter(category=category, slug=sub_slug).first()

        source = row.get('source') if isinstance(row.get('source'), dict) else {}
        source_url = clip(source.get('url'), 800)
        if not source_url.startswith(('http://', 'https://')):
            source_url = ''
        price, compare = raised_catalog_prices(price, compare)

        match = self._match_product(name, provider)
        if match is not None:
            self._attach_source(match, provider, batch, row, price, compare, source_url, sku)
            self.stdout.write(f'Linked {sku} onto {match.sku or match.name}')
            return 'linked', 0

        product = Product.objects.create(
            name=name,
            slug=free_slug(row.get('slug'), name, sku),
            sku=sku,
            category=category,
            subcategory=subcategory,
            description=row.get('description') or '',
            short_description=clip(row.get('short_description'), 500),
            price=price,
            compare_price=compare,
            color=clip(row.get('color'), 50),
            warranty_period=clip(row.get('warranty_period'), 80),
            stock_quantity=0,
            warehouse_stock=0,
            dealer_stock=0,
            dealer_available=False,
            is_active=bool(row.get('is_active', True)),
            is_featured=False,
            catalog_import=batch,
            source_url=source_url,
        )
        self._specifications(product, row.get('specifications') or [])
        self._remember_product(product, provider)
        self._attach_source(
            product, provider, batch, row, price, compare, source_url, sku, primary=True,
        )
        missing = self._images(root, provider, product, sku, row.get('images') or [])
        return 'created', missing

    def _index_existing_products(self):
        self._by_name = {}
        products = Product.objects.select_related('catalog_import').prefetch_related('sources')
        for product in products:
            self._remember_product(product)

    def _remember_product(self, product, provider=None):
        key = match_key(product.name)
        if len(key) < 10:
            return
        self._by_name.setdefault(key, product)
        known = getattr(product, '_provider_ids', None)
        if known is None:
            known = {source.provider for source in product.sources.all()}
            if product.catalog_import_id and product.catalog_import.provider:
                known.add(product.catalog_import.provider)
            product._provider_ids = known
        if provider:
            known.add(provider)

    def _match_product(self, name, provider):
        key = match_key(name)
        if len(key) < 10:
            return None
        product = self._by_name.get(key)
        if product is None:
            return None
        return product

    def _attach_source(self, product, provider, batch, row, price, compare, source_url, sku, primary=False):
        if not primary:
            self._ensure_original_source(product)
        if sku and ProductSource.objects.filter(sku=sku).exists():
            return
        ProductSource.objects.create(
            product=product,
            provider=provider,
            catalog_import=batch,
            sku=sku,
            price=price,
            compare_price=compare,
            source_url=source_url,
        )
        providers = getattr(product, '_provider_ids', None)
        if providers is not None:
            providers.add(provider)
        self._apply_lowest_price(product)

    def _ensure_original_source(self, product):
        if product.sources.exists():
            return
        if product.catalog_import_id and product.catalog_import.provider:
            origin = product.catalog_import.provider
            origin_batch = product.catalog_import
        else:
            origin = ProductSource.STORE
            origin_batch = None
        ProductSource.objects.create(
            product=product,
            provider=origin,
            catalog_import=origin_batch,
            sku=product.sku or '',
            price=product.price,
            compare_price=product.compare_price,
            source_url=product.source_url or '',
        )
        providers = getattr(product, '_provider_ids', None)
        if providers is not None:
            providers.add(origin)

    def _apply_lowest_price(self, product):
        product.sync_lowest_source_price()

    def _specifications(self, product, rows):
        specs = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            name = clip(row.get('name'), 80)
            value = clip(row.get('value'), 255)
            if not name or not value:
                continue
            specs.append(ProductSpecification(
                product=product,
                name=name,
                value=value,
                sort_order=as_int(row.get('sort_order', index)),
            ))
        if specs:
            ProductSpecification.objects.bulk_create(specs)

    def _images(self, root, provider, product, sku, rows):
        images = [row for row in rows if isinstance(row, dict)]
        images.sort(key=lambda row: as_int(row.get('display_order')))
        any_primary = any(row.get('is_primary') for row in images)
        primary_used = False
        missing = 0
        folder = safe_sku(sku)
        for index, row in enumerate(images):
            source = inside(root, row.get('image'))
            if source is None:
                missing += 1
                self.stderr.write(f'{sku}: missing image {row.get("image")}')
                continue
            want_primary = bool(row.get('is_primary')) if any_primary else index == 0
            is_primary = want_primary and not primary_used
            image = ProductImage(
                product=product,
                alt_text=clip(row.get('alt_text') or product.name, 255),
                is_primary=is_primary,
                display_order=as_int(row.get('display_order', index)),
            )
            try:
                with transaction.atomic():
                    with source.open('rb') as handle:
                        image.image.save(
                            f'imports/{provider}/{folder}/{source.name}', File(handle), save=True,
                        )
            except Exception as exc:
                missing += 1
                self.stderr.write(f'{sku}: could not save {row.get("image")}: {exc}')
                continue
            if is_primary:
                primary_used = True
        if images and not primary_used and product.images.exists():
            first = product.images.order_by('display_order', 'id').first()
            if first is not None:
                first.is_primary = True
                first.save(update_fields=['is_primary'])
        return missing
