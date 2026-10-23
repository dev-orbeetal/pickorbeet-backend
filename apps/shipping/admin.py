"""
Admin configuration for courier shipments.
"""
from django.contrib import admin, messages
from django.utils.html import format_html

from .models import Shipment, ShipmentEvent
from .services import ShipmentError, refresh_shipment, status_group

GROUP_COLORS = {
    'in_review': '#EA6C04',
    'pending': '#2F6AE6',
    'hold': '#7A5FD6',
    'delivered': '#0E9A55',
    'partial_delivered': '#0B8C99',
    'cancelled': '#D92D42',
    'unknown': '#5C647E',
}


def status_badge(shipment):
    color = GROUP_COLORS.get(status_group(shipment.status), '#5C647E')
    return format_html('<span style="color: {}; font-weight: 600;">{}</span>', color, shipment.status_label)


class ShipmentEventInline(admin.TabularInline):
    model = ShipmentEvent
    extra = 0
    can_delete = False
    fields = ['created_at', 'source', 'status', 'message', 'occurred_at']
    readonly_fields = fields
    ordering = ['-created_at']

    def has_add_permission(self, request, obj=None):
        return False


class ShipmentInline(admin.StackedInline):
    """Courier details shown on the order page."""
    model = Shipment
    extra = 0
    max_num = 1
    can_delete = False
    fk_name = 'order'
    fields = ['courier', 'tracking_code', 'consignment_id', 'tracking_link', 'status_display',
              'status_message', 'cod_amount', 'booked_at', 'booked_by', 'last_checked_at']
    readonly_fields = ['tracking_link', 'status_display', 'booked_at', 'booked_by', 'last_checked_at']

    def has_add_permission(self, request, obj=None):
        # Shipments are created by "Book with Steadfast", not typed in by hand.
        return False

    @admin.display(description='Tracking page')
    def tracking_link(self, obj):
        if not obj.tracking_url:
            return '-'
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', obj.tracking_url, obj.tracking_url)

    @admin.display(description='Status')
    def status_display(self, obj):
        return status_badge(obj)


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ['order', 'courier', 'tracking_code', 'status_display', 'cod_amount',
                    'booked_at', 'status_updated_at', 'last_checked_at']
    list_filter = ['courier', 'status', 'booked_at']
    search_fields = ['order__order_number', 'tracking_code', 'consignment_id', 'invoice', 'recipient_phone']
    readonly_fields = ['order', 'booked_at', 'booked_by', 'status_updated_at', 'last_checked_at',
                       'raw_response', 'created_at', 'updated_at']
    inlines = [ShipmentEventInline]
    actions = ['refresh_status']
    ordering = ['-created_at']

    fieldsets = (
        ('Parcel', {
            'fields': ('order', 'courier', 'invoice', 'consignment_id', 'tracking_code', 'tracking_url'),
            'description': 'Edit the consignment or tracking code only to repair a booking made in the Steadfast portal.',
        }),
        ('Status', {
            'fields': ('status', 'status_message', 'status_updated_at', 'last_checked_at'),
        }),
        ('Recipient and cash', {
            'fields': ('recipient_name', 'recipient_phone', 'recipient_address', 'cod_amount',
                       'delivery_charge', 'note'),
        }),
        ('Booking', {
            'fields': ('booked_at', 'booked_by', 'raw_response', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Status')
    def status_display(self, obj):
        return status_badge(obj)

    @admin.action(description='Refresh status from Steadfast')
    def refresh_status(self, request, queryset):
        updated = failed = 0
        for shipment in queryset:
            try:
                refresh_shipment(shipment, force=True)
                updated += 1
            except ShipmentError as exc:
                failed += 1
                self.message_user(request, f'{shipment.order}: {exc.message}', messages.ERROR)
        if updated:
            self.message_user(request, f'Checked {updated} shipment(s).', messages.SUCCESS)


@admin.register(ShipmentEvent)
class ShipmentEventAdmin(admin.ModelAdmin):
    list_display = ['shipment', 'source', 'status', 'message', 'occurred_at', 'created_at']
    list_filter = ['source', 'status', 'created_at']
    search_fields = ['shipment__order__order_number', 'shipment__tracking_code', 'idempotency_key']
    readonly_fields = ['shipment', 'source', 'status', 'message', 'idempotency_key', 'payload',
                       'occurred_at', 'created_at']

    def has_add_permission(self, request):
        return False
