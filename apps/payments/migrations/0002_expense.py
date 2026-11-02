import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0014_product_supply_type'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('payments', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Expense',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('voucher_number', models.CharField(max_length=24, unique=True)),
                ('expense_date', models.DateField()),
                ('category', models.CharField(choices=[
                    ('inventory_purchase', 'Inventory Purchase'),
                    ('shipping', 'Shipping & Delivery'),
                    ('marketing', 'Marketing & Ads'),
                    ('utilities', 'Utilities'),
                    ('rent', 'Rent'),
                    ('salaries', 'Salaries'),
                    ('packaging', 'Packaging'),
                    ('software', 'Software & Tools'),
                    ('miscellaneous', 'Miscellaneous'),
                ], max_length=32)),
                ('description', models.TextField()),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('payment_method', models.CharField(blank=True, choices=[
                    ('cash', 'Cash'),
                    ('card', 'Card'),
                    ('mobile_banking', 'Mobile Banking'),
                ], default='', max_length=20)),
                ('payee', models.CharField(blank=True, default='', max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='expenses_recorded',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('product', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='expenses',
                    to='products.product',
                )),
            ],
            options={
                'verbose_name': 'Expense',
                'verbose_name_plural': 'Expenses',
                'ordering': ['-expense_date', '-created_at'],
            },
        ),
    ]
