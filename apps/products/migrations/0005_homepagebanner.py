from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0004_productvariant_low_stock_threshold'),
    ]

    operations = [
        migrations.CreateModel(
            name='HomepageBanner',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('image', models.ImageField(upload_to='banners/')),
                ('link', models.CharField(blank=True, default='', help_text='Optional URL opened when the banner is clicked', max_length=500)),
                ('placement', models.CharField(choices=[('hero', 'Hero slider'), ('promo', 'Promo banner')], default='hero', max_length=10)),
                ('display_order', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Homepage Banner',
                'verbose_name_plural': 'Homepage Banners',
                'ordering': ['placement', 'display_order', 'created_at'],
            },
        ),
    ]
