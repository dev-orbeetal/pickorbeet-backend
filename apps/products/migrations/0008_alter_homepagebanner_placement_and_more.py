from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0007_storesettings_logo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='homepagebanner',
            name='placement',
            field=models.CharField(choices=[('hero', 'Hero slider (left)'), ('promo', 'Side card (right)')], default='hero', help_text='Hero images rotate in the left slider. The first two active side cards appear on the right, in display order.', max_length=10),
        ),
        migrations.AlterField(
            model_name='subcategory',
            name='image',
            field=models.ImageField(blank=True, help_text='Shown on the homepage category card. A square image works best.', null=True, upload_to='subcategories/', verbose_name='Cover image'),
        ),
    ]
