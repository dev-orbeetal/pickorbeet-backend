from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0009_purchase_receipt_idempotency'),
    ]

    operations = [
        migrations.AddField(
            model_name='expense',
            name='status',
            field=models.CharField(
                choices=[('posted', 'Posted'), ('draft', 'Draft')],
                default='posted',
                help_text='Drafts stay out of finance totals and do not change stock.',
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='expense',
            name='draft_payload',
            field=models.JSONField(
                blank=True,
                help_text='Unfinished purchase lines kept until a Product Buying draft is posted.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='manualincome',
            name='status',
            field=models.CharField(
                choices=[('posted', 'Posted'), ('draft', 'Draft')],
                default='posted',
                help_text='Drafts stay out of finance totals until they are posted.',
                max_length=16,
            ),
        ),
    ]
