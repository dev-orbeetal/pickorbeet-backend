"""Order catalog titles so the same model sits together.

Plain A–Z splits a model when a color, wattage, or word order changes.
This builds one sort key in three steps:

1. Normalize punctuation, case, and connector spellings (USB-C, Type-C).
2. Keep the brand and model tokens as the family, and move colors, sizes,
   and generic words (cable, charger) behind them.
3. Encode numbers so 2, 10, and 100 sort in numeric order.

The key is a total order, so it stays correct across admin pages.
"""
import re
import unicodedata

_KEY_LIMIT = 600
_UNIT = re.compile(
    r'^\d+(?:\.\d+)?(?:w|watts?|mah|gb|tb|mb|ft|cm|mm|inch(?:es)?|pk|pcs|pack|v)$'
)
_DIGITS = re.compile(r'\d+')
_USB_C = re.compile(r'(?:usb|type)\s*-?\s*c\b')
_USB_A = re.compile(r'(?:usb|type)\s*-?\s*a\b')

# Words that describe a variant or a product type. They stay in the key,
# after the model, so they cannot push two versions of one model apart.
_TRAILING = {
    'adapter', 'adapters', 'adaptor', 'bluetooth', 'braided', 'cable', 'cables',
    'certified', 'charger', 'chargers', 'combo', 'compact', 'earbud', 'earbuds',
    'earphone', 'earphones', 'fast', 'headphone', 'headphones', 'magnetic',
    'neckband', 'original', 'portable', 'professional', 'series', 'slim',
    'smartwatch', 'speaker', 'speakers', 'stereo', 'super', 'ultra', 'wall',
    'watch', 'watches', 'wireless',
}
_COLORS = {
    'beige', 'black', 'blue', 'brown', 'clear', 'gold', 'gray', 'green', 'grey',
    'navy', 'orange', 'pink', 'purple', 'red', 'rose', 'silver', 'starlight',
    'transparent', 'violet', 'white', 'yellow',
}
_DROPPED = {
    'a', 'an', 'and', 'by', 'for', 'from', 'in', 'new', 'of', 'on', 'or', 'the',
    'to', 'with',
}
# Hoist a known brand so "Cable Anker Nano" sorts with "Anker Nano Cable".
_BRANDS = {
    'acefast', 'adata', 'anker', 'apple', 'asus', 'awei', 'baseus', 'bestway',
    'boya', 'canon', 'cmf', 'curren', 'dell', 'dexgen', 'dlink', 'dsp', 'enchen',
    'epson', 'esonic', 'eufy', 'geemy', 'gigabyte', 'hoco', 'hp', 'huawei',
    'huntkey', 'intel', 'jisulife', 'kemei', 'kumi', 'ldnio', 'lenovo',
    'logitech', 'midea', 'mikrotik', 'mophie', 'msi', 'naviforce', 'netgear',
    'nokia', 'nothing', 'ofkoz', 'oneplus', 'oppo', 'oraimo', 'panasonic',
    'qcy', 'realme', 'samsung', 'soundcore', 'toshiba', 'tplink', 'txrui',
    'ugreen', 'vivo', 'xiaomi', 'zeblaze',
}


def _natural(token):
    return _DIGITS.sub(lambda match: f'{int(match.group()):08d}', token)


def _tokens(name):
    text = unicodedata.normalize('NFKC', str(name or '')).casefold()
    text = text.replace('power bank', 'powerbank').replace('power-bank', 'powerbank')
    text = _USB_C.sub('usbc', text)
    text = _USB_A.sub('usba', text)
    return [token for token in re.split(r'[^\w]+', text, flags=re.UNICODE) if token]


def similar_name_key(name):
    """Sort key that keeps one product family in a single block."""
    identity = []
    trailing = []
    for token in _tokens(name):
        if token in _DROPPED:
            continue
        if token in _COLORS or token in _TRAILING or _UNIT.match(token) or (token.isdigit() and len(token) >= 4):
            trailing.append(token)
        else:
            identity.append(token)

    brand = next((token for token in identity if token in _BRANDS), None)
    if brand:
        rest = [token for token in identity if token != brand]
        ordered = [brand, *sorted(rest, key=_natural)]
    elif identity:
        ordered = [identity[0], *sorted(identity[1:], key=_natural)]
    else:
        ordered = sorted(trailing, key=_natural)
        trailing = []

    key = ' '.join(_natural(token) for token in ordered)
    if trailing:
        key = f"{key}\t{' '.join(sorted(_natural(token) for token in trailing))}"
    return key[:_KEY_LIMIT]
