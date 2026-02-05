"""
Admin configuration for orders app.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Order, OrderItem, OrderStatusHistory, Cart, CartItem, Coupon, CouponUsage


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'variant', 'product_name', 'product_sku', 
                       'size', 'color', 'quantity', 'unit_price', 'total_price']
    can_delete = False


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ['status', 'note', 'changed_by', 'created_at']
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'customer_display', 'order_type', 'order_status_display',
                    'payment_status_display', 'total', 'item_count', 'created_at']
    list_filter = ['order_status', 'payment_status', 'order_type', 'is_inside_dhaka', 'created_at']
    search_fields = ['order_number', 'tracking_number', 'shipping_name', 'shipping_phone',
                     'guest_name', 'guest_phone', 'guest_email']
    readonly_fields = ['order_number', 'tracking_number', 'subtotal', 'total', 'created_at', 
                       'updated_at', 'confirmed_at', 'shipped_at', 'delivered_at']
    ordering = ['-created_at']
    inlines = [OrderItemInline, OrderStatusHistoryInline]
    
    fieldsets = (
        ('Order Info', {
            'fields': ('order_number', 'tracking_number', 'order_type', 'order_status', 'payment_status')
        }),
        ('Customer', {
            'fields': ('user', 'guest_name', 'guest_email', 'guest_phone')
        }),
        ('Shipping Address', {
            'fields': ('shipping_name', 'shipping_phone', 'shipping_address_line1', 
                       'shipping_address_line2', 'shipping_city', 'shipping_district',
                       'shipping_postal_code', 'is_inside_dhaka')
        }),
        ('Billing Address', {
            'fields': ('billing_name', 'billing_phone', 'billing_address_line1',
                       'billing_address_line2', 'billing_city', 'billing_district', 'billing_postal_code'),
            'classes': ('collapse',)
        }),
        ('Pricing & Coupon', {
            'fields': ('subtotal', 'delivery_charge', 'coupon', 'coupon_code', 'discount', 'total')
        }),
        ('Payment', {
            'fields': ('payment_method', 'transaction_id')
        }),
        ('Staff & Notes', {
            'fields': ('processed_by', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'confirmed_at', 'shipped_at', 'delivered_at'),
            'classes': ('collapse',)
        }),
    )

    def customer_display(self, obj):
        return obj.customer_name
    customer_display.short_description = 'Customer'

    def order_status_display(self, obj):
        colors = {
            'pending': 'orange',
            'confirmed': 'blue',
            'processing': 'purple',
            'shipped': 'teal',
            'out_for_delivery': 'cyan',
            'delivered': 'green',
            'cancelled': 'red',
            'refunded': 'gray',
        }
        color = colors.get(obj.order_status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_order_status_display()
        )
    order_status_display.short_description = 'Order Status'

    def payment_status_display(self, obj):
        colors = {
            'pending': 'orange',
            'paid': 'green',
            'failed': 'red',
            'refunded': 'gray',
        }
        color = colors.get(obj.payment_status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_payment_status_display()
        )
    payment_status_display.short_description = 'Payment Status'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product_name', 'product_sku', 'size', 'color', 
                    'quantity', 'unit_price', 'total_price']
    list_filter = ['order__order_status']
    search_fields = ['order__order_number', 'product_name', 'product_sku']


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ['order', 'status', 'changed_by', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['order__order_number']


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'session_key', 'total_items', 'subtotal', 'updated_at']
    list_filter = ['updated_at']
    search_fields = ['user__email', 'session_key']
    inlines = [CartItemInline]


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['cart', 'product', 'variant', 'quantity', 'unit_price', 'total_price']
    list_filter = ['created_at']
    search_fields = ['product__name']


class CouponUsageInline(admin.TabularInline):
    model = CouponUsage
    extra = 0
    readonly_fields = ['user', 'order', 'discount_amount', 'used_at']
    can_delete = False


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'discount_display', 'status_display', 'times_used', 
                    'usage_limit', 'valid_from', 'valid_until', 'is_active']
    list_filter = ['discount_type', 'is_active', 'first_order_only', 'new_users_only', 
                   'valid_from', 'valid_until', 'created_at']
    search_fields = ['code', 'name', 'description']
    readonly_fields = ['times_used', 'created_at', 'updated_at']
    filter_horizontal = ['applicable_categories', 'applicable_products']
    ordering = ['-created_at']
    inlines = [CouponUsageInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'description', 'is_active')
        }),
        ('Discount Settings', {
            'fields': ('discount_type', 'discount_value', 'minimum_order_amount', 'maximum_discount')
        }),
        ('Usage Limits', {
            'fields': ('usage_limit', 'usage_limit_per_user', 'times_used')
        }),
        ('Validity Period', {
            'fields': ('valid_from', 'valid_until')
        }),
        ('Restrictions', {
            'fields': ('first_order_only', 'new_users_only'),
            'classes': ('collapse',)
        }),
        ('Product/Category Restrictions', {
            'fields': ('applicable_categories', 'applicable_products'),
            'classes': ('collapse',),
            'description': 'Leave empty to apply to all products/categories'
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def discount_display(self, obj):
        if obj.discount_type == 'percentage':
            return f"{obj.discount_value}%"
        return f"৳{obj.discount_value}"
    discount_display.short_description = 'Discount'

    def status_display(self, obj):
        colors = {
            'active': 'green',
            'inactive': 'gray',
            'expired': 'red',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.status.title()
        )
    status_display.short_description = 'Status'

    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ['coupon', 'user', 'order', 'discount_amount', 'used_at']
    list_filter = ['used_at', 'coupon']
    search_fields = ['coupon__code', 'user__email', 'order__order_number']
    readonly_fields = ['coupon', 'user', 'order', 'discount_amount', 'used_at']
