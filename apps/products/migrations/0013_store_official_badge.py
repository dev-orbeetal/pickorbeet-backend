from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0012_product_option_values'),
    ]

    operations = [
        migrations.AddField(
            model_name='storesettings',
            name='official_badge_size',
            field=models.CharField(
                choices=[('small', 'Small'), ('medium', 'Medium'), ('large', 'Large')],
                default='medium',
                help_text='Size of the Official badge on product photos.',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='storesettings',
            name='official_badge_color',
            field=models.CharField(
                default='#2864E8',
                help_text='Accent color of the Official badge, as #RRGGBB.',
                max_length=7,
            ),
        ),
        migrations.AddField(
            model_name='storesettings',
            name='official_badge_position',
            field=models.CharField(
                choices=[
                    ('top-left', 'Top left'),
                    ('top-right', 'Top right'),
                    ('bottom-left', 'Bottom left'),
                    ('bottom-right', 'Bottom right'),
                ],
                default='top-left',
                help_text='Corner of the product photo where the Official badge sits.',
                max_length=12,
            ),
        ),
    ]
