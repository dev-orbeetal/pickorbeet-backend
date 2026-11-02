from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('products', '0013_store_official_badge'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='supply_type',
            field=models.CharField(
                choices=[
                    ('available_stock', 'Available Stock'),
                    ('seller_provided', 'Seller-Provided'),
                ],
                default='available_stock',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='supplied_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name='supplied_products',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
