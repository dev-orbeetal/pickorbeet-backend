from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_account_security'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('customer', 'Customer'),
                    ('seller', 'Seller'),
                    ('accountant', 'Accountant'),
                    ('finance_manager', 'Finance Manager'),
                    ('super_admin', 'Super Admin'),
                ],
                default='customer',
                max_length=20,
            ),
        ),
    ]
