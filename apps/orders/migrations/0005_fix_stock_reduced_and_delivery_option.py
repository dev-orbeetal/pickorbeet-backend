# Fix migration: actually create stock_reduced column and DeliveryOption table
# that were faked during previous deployment due to coupon_code conflict.

import uuid
from django.db import migrations, models


def forwards(apps, schema_editor):
    """Add stock_reduced column and DeliveryOption table if they don't exist."""
    connection = schema_editor.connection
    
    # Check if stock_reduced column exists
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'orders_order' AND column_name = 'stock_reduced'
        """)
        if not cursor.fetchone():
            cursor.execute("""
                ALTER TABLE orders_order
                ADD COLUMN stock_reduced BOOLEAN NOT NULL DEFAULT FALSE
            """)
    
    # Check if DeliveryOption table exists
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'orders_deliveryoption'
            )
        """)
        exists = cursor.fetchone()[0]
        if not exists:
            cursor.execute("""
                CREATE TABLE orders_deliveryoption (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(100) NOT NULL UNIQUE,
                    charge NUMERIC(10, 2) NOT NULL DEFAULT 0,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    display_order INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_add_delivery_option'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
