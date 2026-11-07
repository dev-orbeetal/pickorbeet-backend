from django.db import migrations, models


def use_official_tracking_links(apps, schema_editor):
    """Links we built as ``/t/{tracking code}`` lead nowhere. Keep only Steadfast's own link."""
    Shipment = apps.get_model('shipping', 'Shipment')
    for shipment in Shipment.objects.exclude(tracking_url='', raw_response={}).iterator():
        raw = shipment.raw_response if isinstance(shipment.raw_response, dict) else {}
        link = str(raw.get('tracking_link') or '').strip()
        if link.startswith('https://') and len(link) <= 500:
            official = link
        elif shipment.tracking_code and shipment.tracking_url.rstrip('/').endswith(f'/t/{shipment.tracking_code}'):
            official = ''
        else:
            continue
        if official != shipment.tracking_url:
            Shipment.objects.filter(pk=shipment.pk).update(tracking_url=official)


class Migration(migrations.Migration):

    dependencies = [
        ('shipping', '0002_steadfast_police_stations'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='shipmentevent',
            options={'ordering': [models.OrderBy(models.F('occurred_at'), descending=True, nulls_last=True), '-created_at'], 'verbose_name': 'Shipment Event', 'verbose_name_plural': 'Shipment Events'},
        ),
        migrations.RunPython(use_official_tracking_links, migrations.RunPython.noop),
    ]
