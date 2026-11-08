from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shipping', '0005_shipment_sync_runs'),
    ]

    operations = [
        migrations.AddField(
            model_name='shipment',
            name='deliveryman_id',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
        migrations.AddField(
            model_name='shipment',
            name='rider_name',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='shipment',
            name='rider_phone',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
    ]
