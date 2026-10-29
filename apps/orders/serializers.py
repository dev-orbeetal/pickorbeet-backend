"""
Serializers for orders app.
"""
from rest_framework import serializers
from django.conf import settings
from .models import Order, OrderItem, OrderStatusHistory, Cart, CartItem, Coupon, CouponUsage, DeliveryOption
from apps.products.serializers import ProductListSerializer
from apps.shipping.serializers import serialize_shipment
from apps.shipping.services import ShipmentError, normalize_phone, status_group
from .services import can_edit_delivery


def discount_percent(compare_price, price):
    """Whole-percent saving, matching Product.discount_percentage."""
    if compare_price and price is not None and compare_price > price:
        return int(((compare_price - price) / compare_price) * 100)
    return 0


def absolute_media(request, path):
    if not path:
        return None
    if request and not path.startswith('http'):
        return request.build_absolute_uri(path)
    return path


def _sorted_items(order):
    """Prefetched lines, oldest first, so the card shows what was bought first."""
    return sorted(order.items.all(), key=lambda item: (item.created_at, str(item.id)))


def _item_image_url(item, request):
    product = item.product
    if product is None:
        return None
    product_images = list(product.images.all())
    image = next((img for img in product_images if img.is_primary), None)
    image = image or (product_images[0] if product_images else None)
    if image is None:
        return None
    return absolute_media(request, image.image.url)


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
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    product_image = serializers.SerializerMethodField()
    short_description = serializers.CharField(source='product.short_description', read_only=True)
    unit_price = serializers.ReadOnlyField()
    total_price = serializers.ReadOnlyField()
    compare_price = serializers.DecimalField(source='product.compare_price', max_digits=10,
                                             decimal_places=2, read_only=True)
    discount_percentage = serializers.SerializerMethodField()
    stock_quantity = serializers.SerializerMethodField()
    is_out_of_stock = serializers.SerializerMethodField()
    size = serializers.SerializerMethodField()
    color = serializers.SerializerMethodField()
    options = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'variant', 'product_name', 'product_slug', 'product_image',
                  'short_description', 'quantity', 'unit_price', 'total_price', 'compare_price',
                  'discount_percentage', 'stock_quantity', 'is_out_of_stock', 'size', 'color',
                  'options']

    def get_size(self, obj):
        return obj.variant.size if obj.variant and obj.variant.size else None

    def get_color(self, obj):
        return obj.variant.color if obj.variant and obj.variant.color else None

    def get_options(self, obj):
        from apps.products.variants import variant_options
        return variant_options(obj.variant)

    def get_discount_percentage(self, obj):
        return discount_percent(obj.product.compare_price, obj.unit_price)

    def get_stock_quantity(self, obj):
        return obj.variant.stock_quantity if obj.variant else obj.product.stock_quantity

    def get_is_out_of_stock(self, obj):
        if obj.variant:
            return obj.variant.stock_quantity == 0 or not obj.variant.is_active
        return obj.product.is_out_of_stock

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
    product_slug = serializers.SerializerMethodField()
    discount_percentage = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'variant', 'product_name', 'product_sku', 'product_slug',
                  'product_image', 'size', 'color', 'options', 'quantity', 'unit_price', 'compare_price',
                  'discount_percentage', 'total_price']
        read_only_fields = ['id', 'total_price']

    def get_product_slug(self, obj):
        return obj.product.slug if obj.product else None

    def get_discount_percentage(self, obj):
        return discount_percent(obj.compare_price, obj.unit_price)

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
    shipment_status = serializers.SerializerMethodField()
    shipment_status_group = serializers.SerializerMethodField()
    shipment_status_label = serializers.SerializerMethodField()
    tracking_code = serializers.SerializerMethodField()
    tracking_url = serializers.SerializerMethodField()
    preview_images = serializers.SerializerMethodField()
    preview_item = serializers.SerializerMethodField()
    extra_item_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'order_number', 'tracking_number', 'customer_name',
                  'order_type', 'order_status', 'payment_status', 'total',
                  'item_count', 'extra_item_count', 'created_at', 'updated_at',
                  'shipped_at', 'delivered_at', 'is_inside_dhaka',
                  'shipment_status', 'shipment_status_group', 'shipment_status_label',
                  'tracking_code', 'tracking_url', 'preview_images', 'preview_item']

    def _shipment(self, obj):
        return getattr(obj, 'shipment', None)

    def get_shipment_status(self, obj):
        shipment = self._shipment(obj)
        return shipment.status if shipment else None

    def get_shipment_status_group(self, obj):
        shipment = self._shipment(obj)
        return status_group(shipment.status) if shipment else None

    def get_shipment_status_label(self, obj):
        shipment = self._shipment(obj)
        return shipment.status_label if shipment else None

    def get_tracking_code(self, obj):
        shipment = self._shipment(obj)
        if shipment is None:
            return None
        return shipment.tracking_code or None

    def get_tracking_url(self, obj):
        shipment = self._shipment(obj)
        if shipment is None:
            return None
        return shipment.tracking_url or None

    def get_preview_images(self, obj):
        request = self.context.get('request')
        images = []
        for item in _sorted_items(obj):
            if len(images) == 3:
                break
            # Works on prefetched images instead of one query per product.
            url = _item_image_url(item, request)
            if url:
                images.append(url)
        return images

    def get_extra_item_count(self, obj):
        return max(len(_sorted_items(obj)) - 1, 0)

    def get_preview_item(self, obj):
        """The first line, enough for the order card without loading the whole order."""
        items = _sorted_items(obj)
        if not items:
            return None
        item = items[0]
        return {
            'product_id': str(item.product_id) if item.product_id else None,
            'variant_id': str(item.variant_id) if item.variant_id else None,
            'product_name': item.product_name,
            'product_sku': item.product_sku or '',
            'product_slug': item.product.slug if item.product_id and item.product else None,
            'product_image': _item_image_url(item, self.context.get('request')),
            'size': item.size or '',
            'color': item.color or '',
            'options': item.options or [],
            'quantity': item.quantity,
            'unit_price': format(item.unit_price, 'f'),
            'compare_price': format(item.compare_price, 'f') if item.compare_price is not None else None,
        }


class OrderDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single order."""
    items = OrderItemSerializer(many=True, read_only=True)
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)
    customer_name = serializers.ReadOnlyField()
    customer_email = serializers.ReadOnlyField()
    customer_phone = serializers.ReadOnlyField()
    processed_by_name = serializers.CharField(source='processed_by.full_name', read_only=True)
    item_count = serializers.ReadOnlyField()
    shipment = serializers.SerializerMethodField()
    can_edit_delivery = serializers.SerializerMethodField()

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
                  'processed_by', 'processed_by_name', 'notes', 'item_count',
                  'items', 'status_history', 'shipment', 'can_edit_delivery',
                  'created_at', 'updated_at', 'confirmed_at', 'shipped_at', 'delivered_at']

    def get_shipment(self, obj):
        return serialize_shipment(obj, self.context)

    def get_can_edit_delivery(self, obj):
        return can_edit_delivery(obj)


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

    # bKash, Nagad, and cards continue through SSLCommerz after the order is created.
    payment_method = serializers.ChoiceField(
        choices=['bkash', 'nagad', 'card', 'cod'],
        required=False,
    )

    # Optional subset of cart line ids. Omit to order the whole cart.
    item_ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_empty=False,
                                     max_length=100)


class DeliveryUpdateSerializer(serializers.Serializer):
    """Fields a customer may change on a pending order (send only what changes)."""
    shipping_name = serializers.CharField(max_length=200, required=False)
    shipping_phone = serializers.CharField(max_length=20, required=False)
    shipping_address_line1 = serializers.CharField(max_length=255, required=False)
    shipping_address_line2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    shipping_city = serializers.CharField(max_length=100, required=False)
    shipping_district = serializers.CharField(max_length=100, required=False)
    shipping_postal_code = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_shipping_phone(self, value):
        try:
            return normalize_phone(value)
        except ShipmentError as exc:
            raise serializers.ValidationError(exc.message)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('Send at least one delivery field to change.')
        return attrs


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
    order_number = serializers.CharField(required=False, allow_blank=True)
    tracking_number = serializers.CharField(required=False, allow_blank=True)
    tracking_code = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not any(attrs.get(key) for key in ('order_number', 'tracking_number', 'tracking_code')):
            raise serializers.ValidationError(
                "Enter an order number or a Steadfast tracking code."
            )
        return attrs
