"""Sellable SKUs built from the variant: color, then size, then a number.

``white-lg-998`` is a white, large item whose own number is 998.
A product with only a color is ``white-998``. Supplier prefixes such as
``DX-10055`` are not part of the sellable code.
"""
import re

_COLOR_WORDS = {
    'beige', 'black', 'blue', 'bronze', 'brown', 'burgundy', 'champagne',
    'charcoal', 'clear', 'copper', 'cream', 'cyan', 'gold',
    'graphite', 'gray', 'green', 'grey', 'ivory', 'khaki', 'magenta',
    'maroon', 'midnight', 'mint', 'navy', 'olive', 'orange', 'pink',
    'purple', 'red', 'rose', 'silver', 'starlight', 'teal', 'transparent',
    'violet', 'white', 'yellow',
}
_COLOR_MODIFIERS = {
    'aurora', 'dark', 'deep', 'hot', 'ice', 'jet', 'light', 'matte',
    'metallic', 'pastel', 'platinum', 'sapphire', 'sky', 'space',
}
# Single letters are sizes only when the value is explicitly a size.
_LETTER_SIZES = {
    's': 'sm',
    'm': 'md',
    'l': 'lg',
}
_WORD_SIZES = {
    'xs': 'xs',
    'extra small': 'xs',
    'extrasmall': 'xs',
    'sm': 'sm',
    'small': 'sm',
    'md': 'md',
    'medium': 'md',
    'lg': 'lg',
    'large': 'lg',
    'xl': 'xl',
    'extra large': 'xl',
    'extralarge': 'xl',
    'xxl': 'xxl',
    '2xl': 'xxl',
    'double xl': 'xxl',
    'xxxl': 'xxxl',
    '3xl': 'xxxl',
    'free': 'free',
    'free size': 'free',
    'freesize': 'free',
}
_ALL_SIZES = {**_WORD_SIZES, **_LETTER_SIZES}
_SKU_LIMIT = 50
_NUMBER_LIMIT = 100_000_000


def _words(text):
    cleaned = re.sub(r'[^A-Za-z0-9]+', ' ', str(text or '').lower()).strip()
    return [word for word in cleaned.split() if word]


def color_token(text):
    """Lowercase color slug, or '' when the text is not a color."""
    words = [word for word in _words(text) if not word.isdigit()]
    if not words or len(words) > 4:
        return ''
    if any(word not in _COLOR_WORDS and word not in _COLOR_MODIFIERS for word in words):
        return ''
    if not any(word in _COLOR_WORDS for word in words):
        return ''
    return '-'.join(words)


def size_token(text, allow_letters=False):
    """Size slug such as ``lg``. Single letters count only when allow_letters is set."""
    words = _words(text)
    if not words or any(word.isdigit() for word in words):
        return ''
    key = ' '.join(words)
    table = _ALL_SIZES if allow_letters else _WORD_SIZES
    return table.get(key) or table.get(key.replace(' ', '')) or ''


def slug_token(text):
    token = re.sub(r'[^A-Za-z0-9]+', '-', str(text or '').lower()).strip('-')
    return token[:24]


def number_from_sku(sku):
    """Last number in a code. ``DX-10055`` is 10055. ``HM-SKU-0001975`` is 1975."""
    groups = re.findall(r'\d+', str(sku or ''))
    if not groups:
        return None
    number = int(groups[-1])
    if number <= 0 or number >= _NUMBER_LIMIT:
        return None
    return number


def variant_parts(labels):
    """Color, then size, then any other option, from the variant's own values."""
    color = ''
    size = ''
    others = []
    for label in labels or []:
        as_size = size_token(label, allow_letters=True)
        as_color = color_token(label)
        if as_size and not as_color and not size:
            size = as_size
        elif as_color and not color:
            color = as_color
        else:
            token = slug_token(label)
            if token and token not in others:
                others.append(token)
    return [part for part in (color, size, *others) if part]


def product_parts(name, color, size):
    """Color and size written in the product title.

    The stored color is not used. Scraped color fields often say Black for a
    product whose name never mentions a color, and those stay on their current
    code. An explicit size value still counts, because that field is a real size.
    """
    words = _words(name)
    colors = []
    sizes = []
    index = 0
    while index < len(words):
        word = words[index]
        if word in _COLOR_MODIFIERS and index + 1 < len(words) and words[index + 1] in _COLOR_WORDS:
            colors.append(f'{word}-{words[index + 1]}')
            index += 2
            continue
        # "black head" is a blackhead tool, not the color black.
        if word == 'black' and index + 1 < len(words) and words[index + 1] == 'head':
            index += 2
            continue
        if word in _COLOR_WORDS:
            colors.append(word)
            index += 1
            continue
        index += 1
    if not sizes:
        field_size = size_token(size, allow_letters=True)
        if field_size:
            sizes.append(field_size)
    deduped = []
    for item in colors:
        if item not in deduped:
            deduped.append(item)
    if len(deduped) > 3:
        deduped = deduped[:3]
    chosen_size = sizes[-1] if sizes else ''
    return [part for part in ('-'.join(deduped), chosen_size) if part]


def join_sku(parts, number):
    number_text = str(int(number))
    suffix = f'-{number_text}'
    body = '-'.join(parts)
    if len(body) + len(suffix) <= _SKU_LIMIT:
        return f'{body}{suffix}'
    room = _SKU_LIMIT - len(suffix)
    body = body[:room].rstrip('-')
    return f'{body}{suffix}'


def matches_structure(sku, parts):
    if not sku or not parts:
        return False
    prefix = '-'.join(parts) + '-'
    if not str(sku).startswith(prefix):
        return False
    return str(sku)[len(prefix):].isdigit()


def starting_number(skus):
    best = 999
    for sku in skus:
        number = number_from_sku(sku)
        if number is not None:
            best = max(best, number)
    return best + 1


class SkuAllocator:
    """Hands out unique lowercase codes. Numbers already in use move up by one."""

    def __init__(self, taken):
        self.taken = {str(sku).casefold() for sku in taken if sku}
        self.next_number = starting_number(self.taken)
        self.bumped = 0

    def claim(self, parts, preferred):
        if not parts:
            raise ValueError('A variant SKU needs a color, a size, or another option.')
        number = preferred if preferred is not None else self.next_number
        first_choice = number
        while True:
            sku = join_sku(parts, number)
            if sku.casefold() not in self.taken:
                break
            number += 1
        if number != first_choice:
            self.bumped += 1
        self.taken.add(sku.casefold())
        if number >= self.next_number:
            self.next_number = number + 1
        return sku


def plan_changes(product_rows, variant_rows):
    """Decide which stored codes should become color-size-number codes.

    Each row is a dict. Products need id, sku, name, color, size, variant_count.
    Variants need id, sku, product_sku, and labels. Parents that have variants
    keep their own code; each variant gets one. Returns product changes,
    variant changes, how many single products had nothing to name, and how many
    numbers had to move to stay unique. A change is (id, old, new).
    """
    product_plans = []
    variant_plans = []
    skipped = 0
    stable = []

    for row in product_rows:
        sku = row.get('sku') or ''
        if row.get('variant_count'):
            if sku:
                stable.append(sku)
            continue
        parts = product_parts(row.get('name'), row.get('color'), row.get('size'))
        if not parts:
            skipped += 1
            if sku:
                stable.append(sku)
            continue
        if matches_structure(sku, parts):
            stable.append(sku)
            continue
        product_plans.append((row, parts))

    for row in variant_rows:
        sku = row.get('sku') or ''
        parts = variant_parts(row.get('labels'))
        if not parts:
            if sku:
                stable.append(sku)
            continue
        if matches_structure(sku, parts):
            stable.append(sku)
            continue
        variant_plans.append((row, parts))

    allocator = SkuAllocator(stable)
    product_changes = []
    for row, parts in sorted(product_plans, key=lambda item: (item[0].get('sku') or '', str(item[0].get('id')))):
        new = allocator.claim(parts, number_from_sku(row.get('sku')))
        product_changes.append((row.get('id'), row.get('sku') or '', new))
    variant_changes = []
    for row, parts in sorted(variant_plans, key=lambda item: (item[0].get('product_sku') or '', item[0].get('sku') or '', str(item[0].get('id')))):
        new = allocator.claim(parts, number_from_sku(row.get('product_sku')))
        variant_changes.append((row.get('id'), row.get('sku') or '', new))
    return product_changes, variant_changes, skipped, allocator.bumped


def claim_variant_sku(product_sku, labels, taken):
    """Unique variant code, recorded in ``taken`` so the next one cannot reuse it."""
    parts = variant_parts(labels)
    if not parts:
        parts = ['item']
    allocator = SkuAllocator(taken)
    # Keep the caller's set in sync, including codes this claim just consumed.
    sku = allocator.claim(parts, number_from_sku(product_sku))
    taken.add(sku)
    return sku
