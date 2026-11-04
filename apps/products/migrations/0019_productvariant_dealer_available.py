from django.db import migrations, models


def copy_product_dealer_flag(apps, schema_editor):
    ProductVariant = apps.get_model('products', 'ProductVariant')
    for variant in ProductVariant.objects.select_related('product').iterator():
        flag = bool(getattr(variant.product, 'dealer_available', False))
        if variant.dealer_available != flag:
            variant.dealer_available = flag
            variant.save(update_fields=['dealer_available'])


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0018_productimage_variant'),
    ]

    operations = [
        migrations.AddField(
            model_name='productvariant',
            name='dealer_available',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Manual flag: this variant is sellable on the public store and '
                    'dealers can fulfill it even when warehouse stock is zero. '
                    'Independent of calculated dealer_stock.'
                ),
            ),
        ),
        migrations.RunPython(copy_product_dealer_flag, migrations.RunPython.noop),
    ]
