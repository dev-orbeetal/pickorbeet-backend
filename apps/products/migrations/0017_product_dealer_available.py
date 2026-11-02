from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0016_location_stock'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='dealer_available',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Manual flag: dealers can fulfill this product even when warehouse '
                    'stock is zero. Independent of calculated dealer_stock.'
                ),
            ),
        ),
    ]
