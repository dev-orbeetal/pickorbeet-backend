from django.db import migrations, models

import apps.accounts.models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_address_label'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='avatar',
            field=models.ImageField(blank=True, null=True, upload_to=apps.accounts.models.avatar_upload_path),
        ),
    ]
