"""
Delivery charges. Dhaka district pays the inside rate and every other district the
outside rate. Staff set both amounts in Store settings.
"""
from decimal import Decimal

from django.conf import settings

from apps.accounts.bd_geo import is_inside_dhaka


def delivery_charges():
    """(inside Dhaka, outside Dhaka). The settings.py amounts apply only before the store row exists."""
    from apps.products.models import StoreSettings

    store = StoreSettings.objects.only(
        'delivery_charge_inside_dhaka', 'delivery_charge_outside_dhaka',
    ).first()
    if store is None:
        return (
            Decimal(settings.DELIVERY_CHARGE_INSIDE_DHAKA),
            Decimal(settings.DELIVERY_CHARGE_OUTSIDE_DHAKA),
        )
    return store.delivery_charge_inside_dhaka, store.delivery_charge_outside_dhaka


def delivery_charge_for(inside_dhaka):
    inside, outside = delivery_charges()
    return inside if inside_dhaka else outside


def delivery_charge_for_address(*, city='', district='', division=''):
    return delivery_charge_for(is_inside_dhaka(city=city, district=district, division=division))
