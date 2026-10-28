from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0010_productspecification_productreview'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='is_official',
            field=models.BooleanField(
                default=False,
                help_text='Shows an Official badge on the product photo.',
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='warranty_period',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Example: 1 year. Leave empty when the product has no warranty.',
                max_length=80,
            ),
        ),
    ]
