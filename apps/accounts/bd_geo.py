"""
Bangladesh location catalog helpers: Dhaka detection and cascade validation.
"""
from django.utils.text import slugify
from rest_framework import serializers

from apps.accounts.models import BdDistrict, BdDivision, BdPostOffice

DHAKA_AREAS = {'dhaka', 'mirpur', 'uttara', 'gulshan', 'banani', 'dhanmondi', 'mohammadpur'}


def is_inside_dhaka(*, city='', district='', division=''):
    """Only Dhaka district ships at the inside rate; Gazipur or Narayanganj in Dhaka division do not.

    The city list is used only for old addresses that have no district.
    """
    district = (district or '').strip().lower()
    if district:
        return district == 'dhaka'
    return (city or '').strip().lower() in DHAKA_AREAS


def _norm(value):
    return (value or '').strip()


def _match_division(name):
    raw = _norm(name)
    if not raw:
        return None
    slug = slugify(raw)
    return (
        BdDivision.objects.filter(slug=slug).first()
        or BdDivision.objects.filter(name__iexact=raw).first()
    )


def _match_district(division, name):
    raw = _norm(name)
    if not raw or not division:
        return None
    slug = slugify(raw)
    qs = BdDistrict.objects.filter(division=division)
    return qs.filter(slug=slug).first() or qs.filter(name__iexact=raw).first()


def _match_post_office(district, *, post_office='', postal_code=''):
    if not district:
        return None
    qs = BdPostOffice.objects.filter(district=district)
    office = _norm(post_office)
    code = _norm(postal_code)
    if office and code:
        hit = qs.filter(name__iexact=office, postal_code=code).first()
        if hit:
            return hit
    if office:
        hit = qs.filter(name__iexact=office).first()
        if hit:
            return hit
    if code:
        matches = list(qs.filter(postal_code=code)[:2])
        if len(matches) == 1:
            return matches[0]
        if office:
            for item in matches:
                if item.name.lower() == office.lower():
                    return item
    return None


def validate_bd_location(attrs, *, require_cascade=True, prefix=''):
    """
    Validate division → district → post office against the catalog.

    ``prefix`` is '' for Address fields, or 'shipping_' / 'billing_' for orders.
    Mutates attrs with canonical catalog names when matched.
    """
    def key(name):
        return f'{prefix}{name}' if prefix else name

    division_name = _norm(attrs.get(key('division'), ''))
    district_name = _norm(attrs.get(key('district'), ''))
    post_office = _norm(attrs.get(key('post_office'), ''))
    postal_code = _norm(attrs.get(key('postal_code'), ''))

    if not require_cascade and not division_name and not district_name:
        return attrs

    if require_cascade and not division_name:
        raise serializers.ValidationError({key('division'): 'Select a division.'})
    if require_cascade and not district_name:
        raise serializers.ValidationError({key('district'): 'Select a district.'})

    division = _match_division(division_name) if division_name else None
    if division_name and not division:
        raise serializers.ValidationError({key('division'): 'Unknown division.'})

    district = _match_district(division, district_name) if district_name else None
    if district_name and not district:
        raise serializers.ValidationError({key('district'): 'District is not in the selected division.'})

    if post_office or postal_code:
        office = _match_post_office(district, post_office=post_office, postal_code=postal_code)
        if not office:
            raise serializers.ValidationError({
                key('post_office') if post_office else key('postal_code'):
                    'Post office / postal code is not valid for this district.',
            })
        attrs[key('post_office')] = office.name
        attrs[key('postal_code')] = office.postal_code

    if division:
        attrs[key('division')] = division.name
    if district:
        attrs[key('district')] = district.name

    return attrs
