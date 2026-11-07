"""``{{placeholder}}`` wording, filled from a product at the moment a campaign goes out."""
import re
from decimal import Decimal

from core.mailer import format_taka

PLACEHOLDERS = {
    'product_name': 'Product name',
    'price': 'Price now',
    'old_price': 'Price before: the compare price, or the price before a drop',
    'discount': 'Percent off',
    'stock': 'Units left',
    'category': 'Category name',
    'count': 'How many products went live together',
    'others': 'How many besides the first',
}

_TOKEN = re.compile(r'{{\s*(\w+)\s*}}')


def unknown_placeholders(text):
    return sorted({name for name in _TOKEN.findall(text or '') if name not in PLACEHOLDERS})


def render(text, context):
    filled = _TOKEN.sub(lambda match: str(context.get(match.group(1), '') or ''), text or '')
    return ' '.join(filled.split())


def stock_state(product):
    """Sellable units and whether a customer can buy now, counting active variants when there are any."""
    variants = [variant for variant in product.variants.all() if variant.is_active]
    if variants:
        units = sum(int(variant.stock_quantity or 0) for variant in variants)
        return units, any(variant.is_available for variant in variants)
    units = int(product.stock_quantity or 0)
    return units, units > 0 or bool(product.dealer_available)


def percent_off(old_price, price):
    if not old_price or not price or Decimal(old_price) <= Decimal(price):
        return 0
    return int((Decimal(old_price) - Decimal(price)) * 100 / Decimal(old_price))


def product_context(product, *, extra=None):
    """Placeholder values for ``product``. ``extra`` wins, such as the price before a drop."""
    extra = dict(extra or {})
    if product is None:
        return {key: value for key, value in extra.items() if key in PLACEHOLDERS}
    units, _available = stock_state(product)
    old_price = extra.pop('old_price', None) or product.compare_price
    discount = percent_off(old_price, product.price)
    context = {
        'product_name': product.name,
        'price': format_taka(product.price),
        'old_price': format_taka(old_price) if discount else '',
        'discount': str(discount) if discount else '',
        'stock': str(units),
        'category': product.category.name if product.category_id else '',
    }
    context.update({key: value for key, value in extra.items() if key in PLACEHOLDERS})
    return context
