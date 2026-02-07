"""
Management command to fix missing database columns/tables.
Run: python manage.py fix_db
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Fix missing stock_reduced column and DeliveryOption table in the database'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # 1. Add stock_reduced column if missing
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'orders_order' AND column_name = 'stock_reduced'
            """)
            if not cursor.fetchone():
                cursor.execute("""
                    ALTER TABLE orders_order
                    ADD COLUMN stock_reduced BOOLEAN NOT NULL DEFAULT FALSE
                """)
                self.stdout.write(self.style.SUCCESS('✅ Added stock_reduced column to orders_order'))
            else:
                self.stdout.write(self.style.WARNING('⏭  stock_reduced column already exists'))

            # 2. Create DeliveryOption table if missing
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
                self.stdout.write(self.style.SUCCESS('✅ Created orders_deliveryoption table'))
            else:
                self.stdout.write(self.style.WARNING('⏭  orders_deliveryoption table already exists'))

            # 3. Add low_stock_threshold column to products_productvariant if missing
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'products_productvariant' AND column_name = 'low_stock_threshold'
            """)
            if not cursor.fetchone():
                cursor.execute("""
                    ALTER TABLE products_productvariant
                    ADD COLUMN low_stock_threshold INTEGER NOT NULL DEFAULT 10
                """)
                self.stdout.write(self.style.SUCCESS('✅ Added low_stock_threshold column to products_productvariant'))
            else:
                self.stdout.write(self.style.WARNING('⏭  low_stock_threshold column already exists on products_productvariant'))

        self.stdout.write(self.style.SUCCESS('\n✅ Database fix complete! Restart gunicorn now.'))
