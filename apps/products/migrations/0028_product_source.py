from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0027_merge_20261111_1912'),
    ]

    operations = [
        migrations.AlterField(
            model_name='catalogimport',
            name='provider',
            field=models.CharField(
                choices=[
                    ('itech', 'i-Tech'),
                    ('marvellous', 'Marvellous'),
                    ('hemalmart', 'Hemal Mart'),
                ],
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='ProductSource',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('provider', models.CharField(
                    choices=[
                        ('itech', 'i-Tech'),
                        ('marvellous', 'Marvellous'),
                        ('hemalmart', 'Hemal Mart'),
                        ('store', 'Store'),
                    ],
                    max_length=20,
                )),
                ('sku', models.CharField(blank=True, default='', max_length=50)),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('compare_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('source_url', models.URLField(blank=True, default='', max_length=800)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('catalog_import', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='sources',
                    to='products.catalogimport',
                )),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sources',
                    to='products.product',
                )),
            ],
            options={
                'verbose_name': 'Product source',
                'verbose_name_plural': 'Product sources',
                'ordering': ['price', 'created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='productsource',
            constraint=models.UniqueConstraint(
                fields=('product', 'provider'),
                name='unique_product_source_provider',
            ),
        ),
    ]
