"""
Steadfast has no district or thana field on ``create_order``; it reads both from the
address text. These helpers pick the thana from Steadfast's own list so the address
names one it recognises.
"""
import re

from .models import SteadfastPoliceStation

# Old and new romanisations of the same word.
WORD_SPELLINGS = {
    'chittagong': 'chattogram',
    'comilla': 'cumilla',
    'barisal': 'barishal',
    'jessore': 'jashore',
    'bogra': 'bogura',
    'kotowali': 'kotwali',
    'kotoali': 'kotwali',
    'kotwaly': 'kotwali',
    'sador': 'sadar',
    'shadar': 'sadar',
    'netrakona': 'netrokona',
    'jhalakathi': 'jhalokati',
    'jhalokathi': 'jhalokati',
    'jhalakati': 'jhalokati',
    'brahamanbaria': 'brahmanbaria',
    'khagrachhari': 'khagrachari',
    'moulvibazar': 'maulvibazar',
    'laxmipur': 'lakshmipur',
    'narshingdi': 'narsingdi',
    'hobiganj': 'habiganj',
}

# Whole district names that differ by more than one word.
DISTRICT_ALIASES = {
    'chapainawabganj': 'nawabganj',
    'chapainababganj': 'nawabganj',
    'coxbazar': 'coxsbazar',
    'moulvibazar': 'maulvibazar',
    'moulvibazaar': 'maulvibazar',
    'kishorganj': 'kishoreganj',
}

MATCHED = 'matched'
SADAR = 'sadar'


def _spell(word):
    word = re.sub(r'gonj$', 'ganj', word)
    return WORD_SPELLINGS.get(word, word)


def text_key(text):
    """Lowercase words with spelling variants folded: "Kotowali, Comilla" -> "kotwali cumilla"."""
    cleaned = re.sub(r"[’'`]", '', str(text or '').lower())
    return ' '.join(_spell(word) for word in re.findall(r'[a-z0-9]+', cleaned))


def district_key(name):
    compact = text_key(name).replace(' ', '')
    return DISTRICT_ALIASES.get(compact, compact)


def stations_for_district(district):
    key = district_key(district)
    if not key:
        return []
    return list(SteadfastPoliceStation.objects.filter(is_active=True, district_key=key).order_by('name'))


def _sadar(stations, key):
    """The district headquarters thana: "Noakhali Sadar", else the closest "... Sadar ..." name."""
    by_key = {station.name_key.replace(' ', ''): station for station in stations}
    for candidate in (f'{key}sadar', key):
        if candidate in by_key:
            return by_key[candidate]
    sadars = [station for station in stations if 'sadar' in station.name_key.split()]
    return min(
        sadars,
        key=lambda station: (not station.name_key.replace(' ', '').startswith(key), len(station.name_key)),
        default=None,
    )


def match_police_station(order):
    """``(station, how)`` for the order's district. ``how`` is MATCHED, SADAR or ''.

    The post office is the strongest hint, then the area, then the street lines.
    """
    stations = stations_for_district(order.shipping_district)
    if not stations:
        return None, ''
    hints = (
        order.shipping_post_office,
        order.shipping_city,
        order.shipping_address_line2,
        order.shipping_address_line1,
    )
    for hint in hints:
        haystack = f' {text_key(hint)} '
        if not haystack.strip():
            continue
        hits = [station for station in stations if station.name_key and f' {station.name_key} ' in haystack]
        if hits:
            return max(hits, key=lambda station: len(station.name_key)), MATCHED
    sadar = _sadar(stations, district_key(order.shipping_district))
    return (sadar, SADAR) if sadar else (None, '')
