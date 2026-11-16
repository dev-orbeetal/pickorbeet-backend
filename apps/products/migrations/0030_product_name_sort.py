from django.db import migrations, models


def fill_name_sort(apps, schema_editor):
    from apps.products.name_sort import similar_name_key

    Product = apps.get_model('products', 'Product')
    batch = []
    for product in Product.objects.all().only('id', 'name').iterator():
        product.name_sort = similar_name_key(product.name)
        batch.append(product)
        if len(batch) >= 200:
            Product.objects.bulk_update(batch, ['name_sort'])
            batch = []
    if batch:
        Product.objects.bulk_update(batch, ['name_sort'])


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0029_deximpo_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='name_sort',
            field=models.CharField(blank=True, db_index=True, default='', editable=False, max_length=600),
        ),
        migrations.RunPython(fill_name_sort, migrations.RunPython.noop),
    ]
