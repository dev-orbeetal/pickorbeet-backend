from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0006_homepage_sections'),
    ]

    operations = [
        migrations.AddField(
            model_name='storesettings',
            name='logo',
            field=models.ImageField(blank=True, help_text='Store logo shown in the shop header and footer.', null=True, upload_to='store/'),
        ),
    ]
