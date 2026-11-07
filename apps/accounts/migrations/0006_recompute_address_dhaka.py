"""Saved addresses follow the district-only Dhaka rule. Orders keep the charge they were placed with."""
from django.db import migrations

DHAKA_AREAS = {'dhaka', 'mirpur', 'uttara', 'gulshan', 'banani', 'dhanmondi', 'mohammadpur'}


def inside_dhaka(city, district):
    district = (district or '').strip().lower()
    if district:
        return district == 'dhaka'
    return (city or '').strip().lower() in DHAKA_AREAS


def recompute(apps, schema_editor):
    Address = apps.get_model('accounts', 'Address')
    rows = Address.objects.only('id', 'city', 'district', 'is_inside_dhaka').iterator()
    for address in rows:
        inside = inside_dhaka(address.city, address.district)
        if inside != address.is_inside_dhaka:
            Address.objects.filter(pk=address.pk).update(is_inside_dhaka=inside)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_bd_location_cascade'),
    ]

    operations = [
        migrations.RunPython(recompute, migrations.RunPython.noop),
    ]
