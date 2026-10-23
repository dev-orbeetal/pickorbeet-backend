from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_add_user_address_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='address',
            name='label',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
    ]
