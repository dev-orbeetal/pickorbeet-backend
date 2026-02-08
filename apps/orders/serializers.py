"""
Serializers for orders app.
"""
from rest_framework import serializers
from django.conf import settings
from .models import Order, OrderItem, OrderStatusHistory, Cart, CartItem, Coupon, CouponUsage, DeliveryOption
from apps.products.serializers import ProductListSerializer


class DeliveryOptionSerializer(serializers.ModelSerializer):
    """Serializer for delivery options."""

    class Meta:
        model = DeliveryOption
        fields = ['id', 'name', 'charge', 'is_active', 'display_order', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class CouponSerializer(serializers.ModelSerializer):
    """Serializer for Coupon model."""
    status = serializers.ReadOnlyField()
    discount_display = serializers.SerializerMethodField()

    class Meta:
        model = Coupon
        fields = ['id', 'code', 'name', 'description', 'discount_type', 'discount_value',
                  'minimum_order_amount', 'maximum_discount', 'usage_limit', 
                  'usage_limit_per_user', 'times_used', 'valid_from', 'valid_until',
                  'is_active', 'first_order_only', 'new_users_only', 'status', 
                  'discount_display', 'created_at']
        read_only_fields = ['id', 'times_used', 'created_at']

    def get_discount_display(self, obj):
        if obj.discount_type == 'percentage':
            return f"{obj.discount_value}%"
        return f"৳{obj.discount_value}"


class CouponCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating coupons (admin only)."""
    
    class Meta:
        model = Coupon
        fields = ['code', 'name', 'description', 'discount_type', 'discount_value',
                  'minimum_order_amount', 'maximum_discount', 'usage_limit',
                  'usage_limit_per_user', 'valid_from', 'valid_until', 'is_active',
                  'first_order_only', 'new_users_only', 'applicable_categories',
                  'applicable_products']

    def validate_code(self, value):
        return value.upper()

    def validate(self, attrs):
        if attrs.get('valid_from') and attrs.get('valid_until'):
            if attrs['valid_from'] >= attrs['valid_until']:
                raise serializers.ValidationError({
                    'valid_until': 'End date must be after start date.'
                })
        
        if attrs.get('discount_type') == 'percentage' and attrs.get('discount_value', 0) > 100:
            raise serializers.ValidationError({
                'discount_value': 'Percentage discount cannot exceed 100%.'
            })
        
        return attrs


class ValidateCouponSerializer(serializers.Serializer):
    """Serializer for validating a coupon code."""
    code = serializers.CharField(max_length=50)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0)


class ApplyCouponSerializer(serializers.Serializer):
    """Serializer for applying a coupon to cart/checkout."""
    code = serializers.CharField(max_length=50)


class CouponUsageSerializer(serializers.ModelSerializer):
    """Serializer for coupon usage history."""
    coupon_code = serializers.CharField(source='coupon.code', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = CouponUsage
        fields = ['id', 'coupon', 'coupon_code', 'user', 'user_email', 
                  'order', 'order_number', 'discount_amount', 'used_at']


class CartItemSerializer(serializers.ModelSerializer):
    """Serializer for cart items."""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_image = serializers.SerializerMethodField()
    unit_price = serializers.ReadOnlyField()
    total_price = serializers.ReadOnlyField()
    size = serializers.CharField(source='variant.size', read_only=True)
    color = serializers.CharField(source='variant.color', read_only=True)

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'variant', 'product_name', 'product_image',
                  'quantity', 'unit_price', 'total_price', 'size', 'color']

    def get_product_image(self, obj):
        if obj.product.primary_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.product.primary_image)
        return None


class CartSerializer(serializers.ModelSerializer):
    """Serializer for cart."""
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.ReadOnlyField()
    subtotal = serializers.ReadOnlyField()
    delivery_charge_inside_dhaka = serializers.SerializerMethodField()
    delivery_charge_outside_dhaka = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'items', 'total_items', 'subtotal', 
                  'delivery_charge_inside_dhaka', 'delivery_charge_outside_dhaka']

    def get_delivery_charge_inside_dhaka(self, obj):
        return settings.DELIVERY_CHARGE_INSIDE_DHAKA

    def get_delivery_charge_outside_dhaka(self, obj):
        return settings.DELIVERY_CHARGE_OUTSIDE_DHAKA


class AddToCartSerializer(serializers.Serializer):
    """Serializer for adding items to cart."""
    product_id = serializers.UUIDField()
    variant_id = serializers.UUIDField(required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1, default=1)


class UpdateCartItemSerializer(serializers.Serializer):
    """Serializer for updating cart item quantity."""
    quantity = serializers.IntegerField(min_value=1)


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for order items."""
    product_image = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'variant', 'product_name', 'product_sku',
                  'product_image', 'size', 'color', 'quantity', 'unit_price', 'total_price']
        read_only_fields = ['id', 'total_price']

    def get_product_image(self, obj):
        if obj.product:
            img = obj.product.primary_image
            if img:
                request = self.context.get('request')
                if request and not img.startswith('http'):
                    return request.build_absolute_uri(img)
                return img
        return None


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    """Serializer for order status history."""
    changed_by_name = serializers.CharField(source='changed_by.full_name', read_only=True)

    class Meta:
        model = OrderStatusHistory
        fields = ['id', 'status', 'note', 'changed_by', 'changed_by_name', 'created_at']
        read_only_fields = ['id', 'created_at']


class OrderListSerializer(serializers.ModelSerializer):
    """Serializer for order lists."""
    customer_name = serializers.ReadOnlyField()
    item_count = serializers.ReadOnlyField()

    class Meta:
        model = Order
        fields = ['id', 'order_number', 'tracking_number', 'customer_name',
                  'order_type', 'order_status', 'payment_status', 'total',
                  'item_count', 'created_at']


class OrderDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single order."""
    items = OrderItemSerializer(many=True, read_only=True)
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)
    customer_name = serializers.ReadOnlyField()
    customer_email = serializers.ReadOnlyField()
    customer_phone = serializers.ReadOnlyField()
    processed_by_name = serializers.CharField(source='processed_by.full_name', read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'order_number', 'tracking_number', 'user',
                  'customer_name', 'customer_email', 'customer_phone',
                  'guest_email', 'guest_phone', 'guest_name',
                  'order_type', 'order_status', 'payment_status',
                  'shipping_name', 'shipping_phone', 'shipping_address_line1',
                  'shipping_address_line2', 'shipping_city', 'shipping_district',
                  'shipping_postal_code', 'shipping_country', 'is_inside_dhaka',
                  'billing_name', 'billing_phone', 'billing_address_line1',
                  'billing_address_line2', 'billing_city', 'billing_district',
                  'billing_postal_code', 'subtotal', 'delivery_charge',
                  'discount', 'total', 'coupon_code', 'payment_method', 'transaction_id',
                  'processed_by', 'processed_by_name', 'notes',
                  'items', 'status_history', 'created_at', 'updated_at',
                  'confirmed_at', 'shipped_at', 'delivered_at']


class CheckoutSerializer(serializers.Serializer):
    """Serializer for checkout process."""
    # Guest info (optional if authenticated)
    guest_email = serializers.EmailField(required=False, allow_blank=True)
    guest_phone = serializers.CharField(required=False)
    guest_name = serializers.CharField(required=False)
    
    # Shipping address
    shipping_name = serializers.CharField(max_length=200)
    shipping_phone = serializers.CharField(max_length=20)
    shipping_address_line1 = serializers.CharField(max_length=255)
    shipping_address_line2 = serializers.CharField(required=False, allow_blank=True)
    shipping_city = serializers.CharField(max_length=100)
    shipping_district = serializers.CharField(max_length=100)
    shipping_postal_code = serializers.CharField(required=False, allow_blank=True)
    
    # Billing address (optional)
    use_different_billing = serializers.BooleanField(default=False)
    billing_name = serializers.CharField(required=False, allow_blank=True)
    billing_phone = serializers.CharField(required=False, allow_blank=True)
    billing_address_line1 = serializers.CharField(required=False, allow_blank=True)
    billing_address_line2 = serializers.CharField(required=False, allow_blank=True)
    billing_city = serializers.CharField(required=False, allow_blank=True)
    billing_district = serializers.CharField(required=False, allow_blank=True)
    billing_postal_code = serializers.CharField(required=False, allow_blank=True)
    
    # Coupon
    coupon_code = serializers.CharField(required=False, allow_blank=True, max_length=50)
    
    notes = serializers.CharField(required=False, allow_blank=True)


class InShopOrderItemSerializer(serializers.Serializer):
    """Serializer for in-shop order items."""
    product_id = serializers.UUIDField()
    variant_id = serializers.UUIDField(required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1)


class InShopOrderSerializer(serializers.Serializer):
    """Serializer for creating in-shop orders (POS)."""
    customer_name = serializers.CharField(max_length=200, required=False)
    customer_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    customer_email = serializers.EmailField(required=False, allow_blank=True)
    items = InShopOrderItemSerializer(many=True)
    discount = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = serializers.ChoiceField(choices=['cash', 'card', 'mobile_banking'])
    notes = serializers.CharField(required=False, allow_blank=True)


class OrderStatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating order status."""
    status = serializers.ChoiceField(choices=Order.ORDER_STATUS_CHOICES)
    note = serializers.CharField(required=False, allow_blank=True)


class TrackOrderSerializer(serializers.Serializer):
    """Serializer for tracking order."""
    order_number = serializers.CharField(required=False)
    tracking_number = serializers.CharField(required=False)
    phone = serializers.CharField(required=False)

    def validate(self, attrs):
        if not attrs.get('order_number') and not attrs.get('tracking_number'):
            raise serializers.ValidationError(
                "Either order_number or tracking_number is required."
            )
        return attrs
