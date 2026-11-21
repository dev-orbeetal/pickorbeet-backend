import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0012_order_deletion_log'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('payments', '0010_finance_drafts'),
    ]

    operations = [
        migrations.CreateModel(
            name='FinanceReview',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('reviewed_at', models.DateTimeField(auto_now_add=True)),
                (
                    'expense',
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='finance_review',
                        to='payments.expense',
                    ),
                ),
                (
                    'manual_income',
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='finance_review',
                        to='payments.manualincome',
                    ),
                ),
                (
                    'order',
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='finance_review',
                        to='orders.order',
                    ),
                ),
                (
                    'reviewed_by',
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='finance_reviews',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Finance Review',
                'verbose_name_plural': 'Finance Reviews',
            },
        ),
        migrations.AddConstraint(
            model_name='financereview',
            constraint=models.CheckConstraint(
                check=(
                    models.Q(expense__isnull=False, manual_income__isnull=True, order__isnull=True)
                    | models.Q(expense__isnull=True, manual_income__isnull=False, order__isnull=True)
                    | models.Q(expense__isnull=True, manual_income__isnull=True, order__isnull=False)
                ),
                name='finance_review_one_target',
            ),
        ),
    ]
