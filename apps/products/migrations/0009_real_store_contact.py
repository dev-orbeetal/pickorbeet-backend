from django.db import migrations, models

REAL_PHONE = '+8801819217424'
REAL_EMAIL = 'support@pickorbeet.com'
DUMMY_PHONES = {'+880 1234-567890', '+880 1234-567891'}
DUMMY_EMAILS = {'contact@pickorbeet.com'}


def replace_dummy_contact(apps, schema_editor):
    StoreSettings = apps.get_model('products', 'StoreSettings')
    for settings in StoreSettings.objects.all():
        phone_1 = (settings.contact_phone_1 or '').strip()
        phone_2 = (settings.contact_phone_2 or '').strip()
        email_1 = (settings.contact_email_1 or '').strip()
        email_2 = (settings.contact_email_2 or '').strip()

        if not phone_1 or phone_1 in DUMMY_PHONES:
            settings.contact_phone_1 = REAL_PHONE
        if phone_2 in DUMMY_PHONES:
            settings.contact_phone_2 = ''

        if not email_1 or email_1.lower() in DUMMY_EMAILS:
            settings.contact_email_1 = REAL_EMAIL
        if email_2.lower() in DUMMY_EMAILS or (
            email_2.lower() == REAL_EMAIL and settings.contact_email_1.lower() == REAL_EMAIL
        ):
            settings.contact_email_2 = ''

        settings.save(update_fields=[
            'contact_phone_1',
            'contact_phone_2',
            'contact_email_1',
            'contact_email_2',
        ])


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0008_alter_homepagebanner_placement_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='storesettings',
            name='contact_phone_1',
            field=models.CharField(blank=True, default='+8801819217424', max_length=20),
        ),
        migrations.AlterField(
            model_name='storesettings',
            name='contact_phone_2',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AlterField(
            model_name='storesettings',
            name='contact_email_1',
            field=models.EmailField(blank=True, default='support@pickorbeet.com', max_length=254),
        ),
        migrations.AlterField(
            model_name='storesettings',
            name='contact_email_2',
            field=models.EmailField(blank=True, default='', max_length=254),
        ),
        migrations.RunPython(replace_dummy_contact, migrations.RunPython.noop),
    ]
