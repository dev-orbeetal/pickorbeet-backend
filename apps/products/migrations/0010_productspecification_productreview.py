from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('products', '0009_real_store_contact'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductSpecification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=80)),
                ('value', models.CharField(max_length=255)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='specifications', to='products.product')),
            ],
            options={
                'verbose_name': 'Product specification',
                'verbose_name_plural': 'Product specifications',
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='ProductReview',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('rating', models.PositiveSmallIntegerField()),
                ('comment', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='products.product')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='product_reviews', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Product review',
                'verbose_name_plural': 'Product reviews',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='productreview',
            constraint=models.UniqueConstraint(fields=('product', 'user'), name='unique_product_review'),
        ),
        migrations.AddConstraint(
            model_name='productreview',
            constraint=models.CheckConstraint(check=models.Q(('rating__gte', 1), ('rating__lte', 5)), name='product_review_rating_range'),
        ),
    ]
