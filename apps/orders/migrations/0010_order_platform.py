from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0009_bd_location_cascade'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='platform',
            field=models.CharField(
                choices=[
                    ('web', 'Web'),
                    ('app', 'App'),
                    ('admin', 'Admin'),
                    ('unknown', 'Unknown'),
                ],
                db_index=True,
                default='unknown',
                help_text='Client surface that placed the order: web, app, or admin.',
                max_length=20,
            ),
        ),
    ]
