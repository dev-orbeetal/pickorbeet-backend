from django.db import migrations
from django.utils import timezone

TEMPLATES = [
    ('new_arrival', 'New Arrival', 'Something New Just Arrived! ✨',
     "Meet your next favorite — {{product_name}} is now available. Don't miss out!", 'Tap to explore', True),
    ('new_arrival', 'Fresh drop', 'Fresh drop in {{category}} 🔥',
     '{{product_name}} just landed at {{price}}. Be the first to grab it.', 'Tap to explore', False),
    ('low_stock', 'Almost gone', 'Hurry, almost gone! ⏳',
     'Only {{stock}} left of {{product_name}}. Grab yours before it sells out.', 'Shop now', True),
    ('back_in_stock', 'Back in stock', 'Back in stock 🎉',
     '{{product_name}} is available again. Get it before it sells out again.', 'Shop now', True),
    ('price_drop', 'Price drop', 'Price drop on {{product_name}} 💸',
     'Now {{price}}, was {{old_price}}. Save {{discount}}% while it lasts.', 'See the deal', True),
    ('flash_sale', 'Flash sale', 'Flash sale ⚡ {{discount}}% off',
     '{{product_name}} is {{price}} for a limited time. Tap before it ends.', 'Shop the sale', True),
    ('custom', 'Announcement', 'A little something for you 🎁',
     'Fresh picks are waiting in the PickOrbeet app. Come take a look.', 'Open PickOrbeet', False),
]

RULES = [
    {
        'trigger': 'new_arrival',
        'title': 'Something New Just Arrived! ✨',
        'body': "Meet your next favorite — {{product_name}} is now available. Don't miss out!",
        'digest_title': '{{count}} new arrivals just landed ✨',
        'digest_body': '{{product_name}} and {{others}} more are now available. Take a look before they go.',
        'cta_label': 'Tap to explore',
        'audience': 'all',
        'threshold': 0,
    },
    {
        'trigger': 'low_stock',
        'title': 'Hurry, almost gone! ⏳',
        'body': 'Only {{stock}} left of {{product_name}}. Grab yours before it sells out.',
        'cta_label': 'Shop now',
        'audience': 'interested',
        'threshold': 5,
    },
    {
        'trigger': 'back_in_stock',
        'title': 'Back in stock 🎉',
        'body': '{{product_name}} is available again. Get it before it sells out again.',
        'cta_label': 'Shop now',
        'audience': 'interested',
        'threshold': 0,
    },
    {
        'trigger': 'price_drop',
        'title': 'Price drop on {{product_name}} 💸',
        'body': 'Now {{price}}, was {{old_price}}. Save {{discount}}% while it lasts.',
        'cta_label': 'See the deal',
        'audience': 'interested',
        'threshold': 10,
    },
]


def seed(apps, schema_editor):
    CampaignTemplate = apps.get_model('campaigns', 'CampaignTemplate')
    AutomationRule = apps.get_model('campaigns', 'AutomationRule')
    CampaignSettings = apps.get_model('campaigns', 'CampaignSettings')
    for order, (kind, name, title, body, cta, recommended) in enumerate(TEMPLATES, start=1):
        CampaignTemplate.objects.get_or_create(
            kind=kind, name=name, is_system=True,
            defaults={
                'title': title, 'body': body, 'cta_label': cta,
                'is_recommended': recommended, 'display_order': order * 10,
            },
        )
    for rule in RULES:
        AutomationRule.objects.get_or_create(trigger=rule['trigger'], defaults=rule)
    CampaignSettings.objects.get_or_create(pk=1)


def backfill(apps, schema_editor):
    """Products that exist today were never new to customers here: mark them announced."""
    Product = apps.get_model('products', 'Product')
    ProductWatch = apps.get_model('campaigns', 'ProductWatch')
    now = timezone.now()
    known = set(ProductWatch.objects.values_list('product_id', flat=True))
    ProductWatch.objects.bulk_create(
        [
            ProductWatch(product_id=pk, announced_at=now, primed=False, price=price or 0)
            for pk, price in Product.objects.values_list('pk', 'price')
            if pk not in known
        ],
        batch_size=500,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('campaigns', '0001_initial'),
        ('products', '0025_wishlist_item'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
