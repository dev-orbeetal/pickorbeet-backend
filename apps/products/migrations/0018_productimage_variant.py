from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0017_product_dealer_available'),
    ]

    operations = [
        migrations.AddField(
            model_name='productimage',
            name='variant',
            field=models.ForeignKey(
                blank=True,
                help_text='When set, the store shows this image for that variant. Empty means shared across variants.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='images',
                to='products.productvariant',
            ),
        ),
    ]
