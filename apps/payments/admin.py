"""
Admin configuration for payments app.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Expense, ManualIncome, Payment, PurchaseReceipt, PurchaseReceiptLine, Refund


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


class PurchaseReceiptLineInline(admin.TabularInline):
    model = PurchaseReceiptLine
    extra = 0
    readonly_fields = [
        'product', 'variant', 'quantity', 'unit_cost', 'discount_type', 'discount_value',
        'line_subtotal', 'discount_amount', 'line_total', 'effective_unit_cost', 'stock_movement',
    ]
    can_delete = False


@admin.register(PurchaseReceipt)
class PurchaseReceiptAdmin(admin.ModelAdmin):
    list_display = [
        'receipt_number', 'purchase_date', 'payee', 'stock_location', 'grand_total', 'status',
    ]
    list_filter = ['status', 'stock_location', 'purchase_date']
    search_fields = ['receipt_number', 'payee', 'invoice_number']
    readonly_fields = [
        'receipt_number', 'total_quantity', 'subtotal', 'total_discount', 'grand_total',
        'created_by', 'cancelled_at', 'created_at', 'updated_at',
    ]
    inlines = [PurchaseReceiptLineInline]


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['voucher_number', 'expense_date', 'category', 'amount', 'payee', 'product']
    list_filter = ['category', 'expense_date']
    search_fields = ['voucher_number', 'description', 'payee', 'product__name']
    readonly_fields = [
        'voucher_number', 'stock_movement', 'purchase_receipt', 'created_by', 'created_at', 'updated_at',
    ]
    fields = [
        'voucher_number', 'expense_date', 'category', 'description', 'comments', 'amount',
        'quantity', 'unit_cost', 'payment_method', 'payee', 'product', 'payment_proof',
        'stock_movement', 'purchase_receipt', 'created_by', 'created_at', 'updated_at',
    ]


@admin.register(ManualIncome)
class ManualIncomeAdmin(admin.ModelAdmin):
    list_display = [
        'voucher_number', 'income_date', 'category', 'share_partner', 'amount', 'created_by',
    ]
    list_filter = ['category', 'share_partner', 'income_date']
    search_fields = ['voucher_number', 'description', 'comments']
    readonly_fields = ['voucher_number', 'created_by', 'created_at', 'updated_at']
    fields = [
        'voucher_number', 'income_date', 'category', 'share_partner', 'description', 'comments',
        'amount', 'payment_proof', 'created_by', 'created_at', 'updated_at',
    ]
