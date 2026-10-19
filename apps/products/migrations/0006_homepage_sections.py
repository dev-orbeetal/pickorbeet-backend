import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0005_homepagebanner'),
    ]

    operations = [
        migrations.AddField(
            model_name='homepagebanner',
            name='button_label',
            field=models.CharField(blank=True, default='', max_length=80),
        ),
        migrations.AddField(
            model_name='homepagebanner',
            name='subtitle',
            field=models.CharField(blank=True, default='', max_length=240),
        ),
        migrations.AddField(
            model_name='homepagebanner',
            name='title',
            field=models.CharField(blank=True, default='', max_length=160),
        ),
        migrations.CreateModel(
            name='HomepageSection',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('key', models.SlugField(max_length=60, unique=True)),
                ('section_type', models.CharField(choices=[('hero', 'Hero slider'), ('categories', 'Categories'), ('benefits', 'Service benefits'), ('products', 'Product row'), ('promos', 'Promotional banners')], max_length=20)),
                ('title', models.CharField(blank=True, default='', max_length=120)),
                ('subtitle', models.CharField(blank=True, default='', max_length=240)),
                ('is_enabled', models.BooleanField(default=True)),
                ('display_order', models.PositiveIntegerField(default=0)),
                ('item_limit', models.PositiveIntegerField(default=8)),
                ('view_all_label', models.CharField(blank=True, default='', max_length=80)),
                ('view_all_url', models.CharField(blank=True, default='', max_length=300)),
                ('product_source', models.CharField(choices=[('manual', 'Selected products'), ('latest', 'Latest products'), ('on_sale', 'Products on sale'), ('featured', 'Featured products')], default='manual', max_length=20)),
            ],
            options={
                'verbose_name': 'Homepage Section',
                'verbose_name_plural': 'Homepage Sections',
                'ordering': ['display_order', 'title'],
            },
        ),
        migrations.CreateModel(
            name='HomepageBenefit',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=120)),
                ('description', models.CharField(blank=True, default='', max_length=200)),
                ('icon', models.CharField(default='shield', help_text='shield, truck, card, or returns', max_length=40)),
                ('display_order', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Homepage Benefit',
                'verbose_name_plural': 'Homepage Benefits',
                'ordering': ['display_order', 'title'],
            },
        ),
        migrations.CreateModel(
            name='HomepageSectionProduct',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('display_order', models.PositiveIntegerField(default=0)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='homepage_placements', to='products.product')),
                ('section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='section_products', to='products.homepagesection')),
            ],
            options={
                'verbose_name': 'Section Product',
                'verbose_name_plural': 'Section Products',
                'ordering': ['display_order', 'id'],
                'unique_together': {('section', 'product')},
            },
        ),
    ]
