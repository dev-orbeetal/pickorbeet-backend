"""
Management command to create the WELCOME10 coupon.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.orders.models import Coupon


class Command(BaseCommand):
    help = 'Create the WELCOME10 coupon for new user signups'

    def handle(self, *args, **options):
        # Check if coupon already exists
        if Coupon.objects.filter(code='WELCOME10').exists():
            self.stdout.write(self.style.WARNING('WELCOME10 coupon already exists.'))
            return

        # Create the coupon
        coupon = Coupon.objects.create(
            code='WELCOME10',
            name='Welcome Discount - 10% Off First Order',
            description='Welcome discount for new users. Get 10% off your first purchase!',
            discount_type='percentage',
            discount_value=10,
            minimum_order_amount=500,  # Minimum ৳500 order
            maximum_discount=500,  # Max ৳500 discount
            usage_limit=None,  # Unlimited total uses
            usage_limit_per_user=1,  # One use per user
            valid_from=timezone.now(),
            valid_until=timezone.now() + timedelta(days=365*2),  # Valid for 2 years
            is_active=True,
            first_order_only=True,
            new_users_only=False,
        )

        self.stdout.write(self.style.SUCCESS(f'Successfully created coupon: {coupon.code}'))
        self.stdout.write(f'  - Discount: {coupon.discount_value}%')
        self.stdout.write(f'  - Minimum Order: ৳{coupon.minimum_order_amount}')
        self.stdout.write(f'  - Maximum Discount: ৳{coupon.maximum_discount}')
        self.stdout.write(f'  - Valid Until: {coupon.valid_until}')
