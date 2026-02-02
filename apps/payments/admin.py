"""
Admin configuration for payments app.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Payment, Refund


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'order_number', 'payment_method', 'status_display', 
                    'amount', 'currency', 'transaction_id', 'created_at']
    list_filter = ['payment_method', 'status', 'created_at']
    search_fields = ['order__order_number', 'transaction_id', 'bank_transaction_id']
    readonly_fields = ['id', 'session_key', 'gateway_response', 'created_at', 'updated_at', 'completed_at']
    ordering = ['-created_at']

    fieldsets = (
        ('Order Info', {
            'fields': ('order', 'payment_method', 'status')
        }),
        ('Amount', {
            'fields': ('amount', 'currency')
        }),
        ('Transaction Details', {
            'fields': ('session_key', 'transaction_id', 'val_id', 'bank_transaction_id')
        }),
        ('Card Info', {
            'fields': ('card_type', 'card_brand')
        }),
        ('Gateway Response', {
            'fields': ('gateway_response',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at')
        }),
    )

    def order_number(self, obj):
        return obj.order.order_number
    order_number.short_description = 'Order'

    def status_display(self, obj):
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'gray',
            'refunded': 'purple',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ['id', 'payment_order', 'amount', 'status_display', 
                    'requested_by', 'processed_by', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['payment__order__order_number', 'payment__transaction_id']
    readonly_fields = ['id', 'created_at', 'processed_at']
    ordering = ['-created_at']

    def payment_order(self, obj):
        return obj.payment.order.order_number
    payment_order.short_description = 'Order'

    def status_display(self, obj):
        colors = {
            'pending': 'orange',
            'approved': 'green',
            'processed': 'blue',
            'rejected': 'red',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'
