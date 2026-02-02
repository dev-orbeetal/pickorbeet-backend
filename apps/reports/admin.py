"""
Admin configuration for reports app.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import DailySalesReport, StockReport, StockMovement


@admin.register(DailySalesReport)
class DailySalesReportAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_orders', 'online_orders', 'in_shop_orders',
                    'gross_revenue', 'net_revenue', 'total_items_sold', 'generated_at']
    list_filter = ['date', 'generated_at']
    ordering = ['-date']
    readonly_fields = ['id', 'generated_at']

    fieldsets = (
        ('Date', {
            'fields': ('date',)
        }),
        ('Orders', {
            'fields': ('total_orders', 'online_orders', 'in_shop_orders')
        }),
        ('Revenue', {
            'fields': ('gross_revenue', 'delivery_charges', 'discounts', 'net_revenue')
        }),
        ('Products', {
            'fields': ('total_items_sold',)
        }),
        ('Payments', {
            'fields': ('cash_payments', 'card_payments', 'online_payments')
        }),
        ('Meta', {
            'fields': ('generated_at', 'generated_by')
        }),
    )


@admin.register(StockReport)
class StockReportAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_products', 'in_stock_products', 'low_stock_products',
                    'out_of_stock_products', 'total_units', 'total_stock_value', 'generated_at']
    list_filter = ['date', 'generated_at']
    ordering = ['-date']
    readonly_fields = ['id', 'generated_at']


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ['product', 'movement_type_display', 'reason', 'quantity_display',
                    'previous_stock', 'new_stock', 'created_by', 'created_at']
    list_filter = ['movement_type', 'reason', 'created_at']
    search_fields = ['product__name', 'product__sku']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at']

    def movement_type_display(self, obj):
        colors = {
            'in': 'green',
            'out': 'red',
            'adjustment': 'blue',
            'return': 'orange',
        }
        color = colors.get(obj.movement_type, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_movement_type_display()
        )
    movement_type_display.short_description = 'Type'

    def quantity_display(self, obj):
        if obj.quantity > 0:
            return format_html('<span style="color: green;">+{}</span>', obj.quantity)
        return format_html('<span style="color: red;">{}</span>', obj.quantity)
    quantity_display.short_description = 'Quantity'
