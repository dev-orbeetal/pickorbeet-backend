"""Named product options and the sellable combinations they produce."""
import re
from decimal import Decimal, InvalidOperation

from django.db import transaction

from apps.products.models import ProductOption, ProductOptionValue, ProductVariant

HEX = re.compile(r'^#[0-9A-Fa-f]{6}$')


class SetupError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


def sku_token(label):
    cleaned = re.sub(r'[^A-Za-z0-9]', '', label or '').upper()
    return cleaned[:8] or 'X'


def build_variant_sku(product_sku, labels, taken):
    base = re.sub(r'[^A-Za-z0-9-]', '', (product_sku or 'ITEM')).upper()[:20] or 'ITEM'
    sku = '-'.join([base, *[sku_token(label) for label in labels]])[:50]
    if sku not in taken:
        taken.add(sku)
        return sku
    number = 2
    while number < 1000:
        suffix = f'-{number}'
        candidate = f'{sku[:50 - len(suffix)]}{suffix}'
        if candidate not in taken:
            taken.add(candidate)
            return candidate
        number += 1
    raise SetupError('Could not build a unique SKU.')


def variant_options(variant):
    if variant is None:
        return []
    values = sorted(
        variant.values.all(),
        key=lambda value: (value.option.sort_order, value.sort_order, value.label.lower()),
    )
    return [
        {
            'name': value.option.name,
            'kind': value.option.kind,
            'label': value.label,
            'color_hex': value.color_hex or '',
        }
        for value in values
    ]


def option_groups(product):
    return [
        {
            'name': option.name,
            'kind': option.kind,
            'values': [
                {'label': value.label, 'color_hex': value.color_hex or ''}
                for value in option.values.all()
            ],
        }
        for option in product.options.all()
    ]


def legacy_fields(groups, selections):
    size = None
    color = None
    for group in groups:
        chosen = next(
            (item['label'] for item in selections if item['name'].casefold() == group['name'].casefold()),
            '',
        )
        if group['name'].casefold() == 'size':
            size = chosen or None
        if group['name'].casefold() == 'color':
            color = chosen or None
    return size, color


def _clean_groups(groups):
    if not isinstance(groups, list):
        raise SetupError('Options must be a list.')
    cleaned = []
    seen_names = set()
    for group in groups:
        if not isinstance(group, dict):
            raise SetupError('Each option needs a name and a kind.')
        name = str(group.get('name') or '').strip()
        kind = str(group.get('kind') or ProductOption.TEXT).strip()
        if not name:
            raise SetupError('Name each option.')
        if len(name) > 40:
            raise SetupError(f'{name} is too long.')
        if kind not in (ProductOption.TEXT, ProductOption.SWATCH):
            raise SetupError(f'{name} must be text or a color swatch.')
        key = name.casefold()
        if key in seen_names:
            raise SetupError('Option names must be different.')
        seen_names.add(key)
        raw_values = group.get('values') or []
        if not isinstance(raw_values, list) or not raw_values:
            raise SetupError(f'Add a value for {name}.')
        values = []
        seen_labels = set()
        for raw in raw_values:
            if not isinstance(raw, dict):
                raise SetupError(f'Each {name} value needs a label.')
            label = str(raw.get('label') or '').strip()
            if not label:
                raise SetupError(f'Each {name} value needs a label.')
            if len(label) > 40:
                raise SetupError(f'{label} is too long.')
            label_key = label.casefold()
            if label_key in seen_labels:
                raise SetupError(f'{name} already has {label}.')
            seen_labels.add(label_key)
            color_hex = str(raw.get('color_hex') or '').strip()
            if kind == ProductOption.SWATCH:
                if not HEX.match(color_hex):
                    raise SetupError(f'Choose a color for {label}.')
                color_hex = color_hex.upper()
            else:
                color_hex = ''
            values.append({'label': label, 'color_hex': color_hex})
        cleaned.append({'name': name, 'kind': kind, 'values': values})
    return cleaned


def _clean_rows(groups, rows):
    if not isinstance(rows, list):
        raise SetupError('Variants must be a list.')
    if groups and not rows:
        raise SetupError('Add a value so the combinations can be created.')
    if rows and not groups:
        raise SetupError('Name an option before adding variants.')
    cleaned = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise SetupError('A variant is missing its values.')
        selections = []
        raw_selections = row.get('selections') or []
        if not isinstance(raw_selections, list):
            raise SetupError('A variant is missing its values.')
        by_name = {}
        for item in raw_selections:
            if not isinstance(item, dict):
                continue
            by_name[str(item.get('name') or '').strip().casefold()] = str(item.get('label') or '').strip()
        for group in groups:
            label = by_name.get(group['name'].casefold(), '')
            known = {value['label'].casefold(): value['label'] for value in group['values']}
            if label.casefold() not in known:
                raise SetupError(f'Each variant needs a {group["name"]}.')
            selections.append({'name': group['name'], 'label': known[label.casefold()]})
        key = tuple(item['label'].casefold() for item in selections)
        if key in seen:
            raise SetupError('Two variants use the same values.')
        seen.add(key)
        price = row.get('price')
        if price in (None, ''):
            price = None
        else:
            try:
                price = Decimal(str(price))
            except (InvalidOperation, ValueError):
                raise SetupError('Enter a valid variant price.')
            if price < 0:
                raise SetupError('Enter a valid variant price.')
        barcode = str(row.get('barcode') or '').strip() or None
        if barcode and len(barcode) > 50:
            raise SetupError('A variant barcode is too long.')
        variant_id = str(row.get('id') or '').strip() or None
        cleaned.append({
            'id': variant_id,
            'selections': selections,
            'price': price,
            'stock_quantity': _clean_count(row.get('stock_quantity'), 'stock'),
            'low_stock_threshold': _clean_count(row.get('low_stock_threshold', 10), 'low stock alert'),
            'is_active': bool(row.get('is_active', True)),
            'barcode': barcode,
        })
    return cleaned


def _clean_count(value, label):
    if value in (None, ''):
        return 0
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise SetupError(f'Enter a valid {label}.')
    if number < 0:
        raise SetupError(f'Enter a valid {label}.')
    return number


def _upsert_options(product, groups):
    existing = {option.name.casefold(): option for option in product.options.all()}
    for option in existing.values():
        option.name = f'__tmp__{option.pk.hex[:12]}'
        option.save(update_fields=['name'])
    lookup = {}
    kept_options = []
    for index, group in enumerate(groups):
        option = existing.get(group['name'].casefold())
        if option is None:
            option = ProductOption.objects.create(
                product=product,
                name=group['name'],
                kind=group['kind'],
                sort_order=index,
            )
        else:
            option.name = group['name']
            option.kind = group['kind']
            option.sort_order = index
            option.save()
        kept_options.append(option.pk)
        current_values = {value.label.casefold(): value for value in option.values.all()}
        for value in current_values.values():
            value.label = f'__tmp__{value.pk.hex[:12]}'
            value.save(update_fields=['label'])
        kept_values = []
        for value_index, value in enumerate(group['values']):
            stored = current_values.get(value['label'].casefold())
            if stored is None:
                stored = ProductOptionValue.objects.create(
                    option=option,
                    label=value['label'],
                    color_hex=value['color_hex'],
                    sort_order=value_index,
                )
            else:
                stored.label = value['label']
                stored.color_hex = value['color_hex']
                stored.sort_order = value_index
                stored.save()
            kept_values.append(stored.pk)
            lookup[(group['name'].casefold(), value['label'].casefold())] = stored
        option.values.exclude(pk__in=kept_values).delete()
    product.options.exclude(pk__in=kept_options).delete()
    return lookup


@transaction.atomic
def sync_variant_setup(product, groups, rows):
    cleaned_groups = _clean_groups(groups or [])
    cleaned_rows = _clean_rows(cleaned_groups, rows or [])
    lookup = _upsert_options(product, cleaned_groups)

    keep_ids = []
    owned = {str(variant_id): variant for variant_id, variant in (
        (str(variant.pk), variant) for variant in product.variants.all()
    )}
    for row in cleaned_rows:
        if not row['id']:
            continue
        if row['id'] not in owned:
            raise SetupError('A variant on this product could not be found.')
        keep_ids.append(owned[row['id']].pk)
    product.variants.exclude(pk__in=keep_ids).delete()

    taken = set(ProductVariant.objects.values_list('sku', flat=True))
    saved = []
    for row in cleaned_rows:
        values = [
            lookup[(item['name'].casefold(), item['label'].casefold())]
            for item in row['selections']
        ]
        size, color = legacy_fields(cleaned_groups, row['selections'])
        variant = owned.get(row['id']) if row['id'] else None
        if variant is None:
            sku = build_variant_sku(
                product.sku,
                [item['label'] for item in row['selections']],
                taken,
            )
            variant = ProductVariant(product=product, sku=sku)
        barcode = row['barcode']
        if barcode and ProductVariant.objects.filter(barcode=barcode).exclude(pk=variant.pk).exists():
            raise SetupError(f'The barcode {barcode} is already used.')
        variant.barcode = barcode
        variant.price = row['price']
        variant.stock_quantity = row['stock_quantity']
        variant.low_stock_threshold = row['low_stock_threshold']
        variant.is_active = row['is_active']
        variant.size = size
        variant.color = color
        if not variant.sku:
            variant.sku = build_variant_sku(
                product.sku,
                [item['label'] for item in row['selections']],
                taken,
            )
        variant.save()
        variant.values.set(values)
        saved.append(variant)
    return saved
