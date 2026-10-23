"""
Order models for Pickorbeet E-commerce.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid
import random
import string


def generate_order_number():
    """Generate unique order number."""
    timestamp = timezone.now().strftime('%Y%m%d')
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"ORD-{timestamp}-{random_str}"


class DeliveryOption(models.Model):
    """Configurable delivery options with custom names and charges."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, help_text='e.g. Inside Dhaka, Outside Dhaka')
    charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Delivery Option'
        verbose_name_plural = 'Delivery Options'
        ordering = ['display_order', 'name']

    def __str__(self):
        return f"{self.name} — ৳{self.charge}"


class Coupon(models.Model):
    """Coupon/Discount code model for promotional offers."""
    
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('expired', 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=200, help_text="Internal name for the coupon")
    description = models.TextField(blank=True, null=True)
    
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES, default='percentage')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, help_text="Percentage or fixed amount")
    
    # Constraints
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Minimum order value required")
    maximum_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Maximum discount cap (for percentage type)")
    
    # Usage limits
    usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Total times coupon can be used (leave empty for unlimited)")
    usage_limit_per_user = models.PositiveIntegerField(default=1, help_text="Times each user can use this coupon")
    times_used = models.PositiveIntegerField(default=0)
    
    # Validity period
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    
    # Restrictions
    is_active = models.BooleanField(default=True)
    first_order_only = models.BooleanField(default=False, help_text="Only for users with no previous orders")
    new_users_only = models.BooleanField(default=False, help_text="Only for newly registered users (within 7 days)")
    
    # Category/Product restrictions (optional)
    applicable_categories = models.ManyToManyField(
        'products.Category', 
        blank=True, 
        related_name='coupons',
        help_text="Leave empty for all categories"
    )
    applicable_products = models.ManyToManyField(
        'products.Product', 
        blank=True, 
        related_name='coupons',
        help_text="Leave empty for all products"
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_coupons'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Coupon'
        verbose_name_plural = 'Coupons'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        self.code = self.code.upper()
        super().save(*args, **kwargs)

    @property
    def status(self):
        """Get current status of the coupon."""
        now = timezone.now()
        if not self.is_active:
            return 'inactive'
        if now < self.valid_from or now > self.valid_until:
            return 'expired'
        if self.usage_limit and self.times_used >= self.usage_limit:
            return 'expired'
        return 'active'

    @property
    def is_valid(self):
        """Check if coupon is currently valid."""
        return self.status == 'active'

    def calculate_discount(self, order_subtotal):
        """Calculate discount amount for given order subtotal."""
        if self.discount_type == 'percentage':
            discount = (order_subtotal * self.discount_value) / 100
            if self.maximum_discount:
                discount = min(discount, self.maximum_discount)
        else:
            discount = self.discount_value
        return min(discount, order_subtotal)  # Don't exceed order total

    def can_be_used_by(self, user, order_subtotal=0):
        """Check if coupon can be used by a specific user."""
        from datetime import timedelta
        
        # Check basic validity
        if not self.is_valid:
            return False, "This coupon is no longer valid."
        
        # Check minimum order amount
        if order_subtotal < self.minimum_order_amount:
            return False, f"Minimum order amount of ৳{self.minimum_order_amount} required."
        
        # Check usage limit
        if self.usage_limit and self.times_used >= self.usage_limit:
            return False, "This coupon has reached its usage limit."
        
        if user and user.is_authenticated:
            # Check per-user usage limit
            user_usage = CouponUsage.objects.filter(coupon=self, user=user).count()
            if user_usage >= self.usage_limit_per_user:
                return False, "You have already used this coupon."
            
            # Check first order only
            if self.first_order_only:
                has_orders = Order.objects.filter(user=user, payment_status='paid').exists()
                if has_orders:
                    return False, "This coupon is only valid for your first order."
            
            # Check new users only
            if self.new_users_only:
                days_since_registration = (timezone.now() - user.created_at).days
                if days_since_registration > 7:
                    return False, "This coupon is only valid for new users."
        
        return True, "Coupon is valid!"


class CouponUsage(models.Model):
    """Track coupon usage by users."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usages')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='coupon_usages'
    )
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='coupon_usage')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Coupon Usage'
        verbose_name_plural = 'Coupon Usages'

    def __str__(self):
        return f"{self.coupon.code} used by {self.user or 'Guest'}"


def generate_tracking_number():
    """Generate tracking number."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))


class Order(models.Model):
    """Order model for both online and in-shop orders."""
    
    ORDER_TYPE_CHOICES = [
        ('online', 'Online Order'),
        ('in_shop', 'In-Shop Order'),
    ]
    
    ORDER_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=50, unique=True, default=generate_order_number)
    tracking_number = models.CharField(max_length=50, unique=True, default=generate_tracking_number)
    
    # Customer info (can be null for anonymous orders)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='orders'
    )
    
    # Guest checkout info
    guest_email = models.EmailField(blank=True, null=True)
    guest_phone = models.CharField(max_length=20, blank=True, null=True)
    guest_name = models.CharField(max_length=200, blank=True, null=True)
    
    order_type = models.CharField(max_length=20, choices=ORDER_TYPE_CHOICES, default='online')
    order_status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # Shipping Address
    shipping_name = models.CharField(max_length=200)
    shipping_phone = models.CharField(max_length=20)
    shipping_address_line1 = models.CharField(max_length=255)
    shipping_address_line2 = models.CharField(max_length=255, blank=True, null=True)
    shipping_city = models.CharField(max_length=100)
    shipping_district = models.CharField(max_length=100)
    shipping_postal_code = models.CharField(max_length=20, blank=True, null=True)
    shipping_country = models.CharField(max_length=100, default='Bangladesh')
    is_inside_dhaka = models.BooleanField(default=False)
    
    # Billing Address (optional, same as shipping if not provided)
    billing_name = models.CharField(max_length=200, blank=True, null=True)
    billing_phone = models.CharField(max_length=20, blank=True, null=True)
    billing_address_line1 = models.CharField(max_length=255, blank=True, null=True)
    billing_address_line2 = models.CharField(max_length=255, blank=True, null=True)
    billing_city = models.CharField(max_length=100, blank=True, null=True)
    billing_district = models.CharField(max_length=100, blank=True, null=True)
    billing_postal_code = models.CharField(max_length=20, blank=True, null=True)
    
    # Pricing
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Coupon
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders'
    )
    coupon_code = models.CharField(max_length=50, blank=True, null=True)  # Snapshot of code used
    
    # Payment info
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Staff info
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_orders'
    )
    
    notes = models.TextField(blank=True, null=True)
    stock_reduced = models.BooleanField(default=False, help_text='Whether stock has been deducted for this order')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    shipped_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']

    def __str__(self):
        return self.order_number

    def save(self, *args, **kwargs):
        # Auto-calculate delivery charge based on location
        if not self.delivery_charge:
            dhaka_areas = ['dhaka', 'mirpur', 'uttara', 'gulshan', 'banani', 'dhanmondi', 'mohammadpur']
            self.is_inside_dhaka = self.shipping_city.lower() in dhaka_areas or self.shipping_district.lower() == 'dhaka'
            
            if self.order_type == 'in_shop':
                self.delivery_charge = 0
            elif self.is_inside_dhaka:
                self.delivery_charge = settings.DELIVERY_CHARGE_INSIDE_DHAKA
            else:
                self.delivery_charge = settings.DELIVERY_CHARGE_OUTSIDE_DHAKA
        
        # Calculate total
        self.total = self.subtotal + self.delivery_charge - self.discount
        
        super().save(*args, **kwargs)

    @property
    def customer_name(self):
        if self.user:
            return self.user.full_name
        return self.guest_name or 'Anonymous'

    @property
    def customer_email(self):
        if self.user:
            return self.user.email
        return self.guest_email

    @property
    def customer_phone(self):
        if self.user:
            return self.user.phone
        return self.guest_phone

    @property
    def item_count(self):
        return self.items.count()


class OrderItem(models.Model):
    """Order item model."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items')
    variant = models.ForeignKey(
        'products.ProductVariant', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='order_items'
    )
    
    product_name = models.CharField(max_length=255)  # Snapshot of product name
    product_sku = models.CharField(max_length=50, blank=True, null=True)
    size = models.CharField(max_length=10, blank=True, null=True)
    color = models.CharField(max_length=50, blank=True, null=True)
    
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True,
        help_text='Snapshot of the product compare-at price when the order was placed',
    )
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"

    def save(self, *args, **kwargs):
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)


class OrderStatusHistory(models.Model):
    """Track order status changes."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    status = models.CharField(max_length=20, choices=Order.ORDER_STATUS_CHOICES)
    note = models.TextField(blank=True, null=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Order Status History'
        verbose_name_plural = 'Order Status Histories'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order.order_number} - {self.status}"


class Cart(models.Model):
    """Shopping cart model."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cart'
    )
    session_key = models.CharField(max_length=255, blank=True, null=True)  # For guest carts
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cart'
        verbose_name_plural = 'Carts'

    def __str__(self):
        if self.user:
            return f"Cart - {self.user.email}"
        return f"Cart - {self.session_key}"

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self):
        return sum(item.total_price for item in self.items.all())


class CartItem(models.Model):
    """Cart item model."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    quantity = models.PositiveIntegerField(default=1)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cart Item'
        verbose_name_plural = 'Cart Items'
        unique_together = ['cart', 'product', 'variant']

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    @property
    def unit_price(self):
        if self.variant and self.variant.price:
            return self.variant.price
        return self.product.price

    @property
    def total_price(self):
        return self.unit_price * self.quantity
