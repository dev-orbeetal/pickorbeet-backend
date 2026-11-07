"""
Serializers for courier shipments.
"""
from decimal import Decimal

from rest_framework import serializers

from core.mailer import track_url

from .models import Shipment, ShipmentEvent
from .services import (
    cash_to_collect, cod_mismatch, is_final, portal_url_for, seconds_until_refresh, status_group,
    visible_tracking_events,
)

STAFF_ROLES = {'seller', 'accountant', 'super_admin'}


def _money(value):
    return f'{Decimal(value or 0).quantize(Decimal("0.01")):.2f}'


class ShipmentEventSerializer(serializers.ModelSerializer):
    status_group = serializers.SerializerMethodField()

    class Meta:
        model = ShipmentEvent
        fields = ['id', 'source', 'status', 'status_group', 'message', 'occurred_at', 'created_at']

    def get_status_group(self, obj):
        return status_group(obj.status) if obj.status else None


class ShipmentSerializer(serializers.ModelSerializer):
    """What customers see: tracking details, never booking internals."""

    courier_name = serializers.CharField(source='get_courier_display', read_only=True)
    status_group = serializers.SerializerMethodField()
    status_label = serializers.CharField(read_only=True)
    is_final = serializers.SerializerMethodField()
    refresh_available_in = serializers.SerializerMethodField()
    events = serializers.SerializerMethodField()
    cod_amount = serializers.SerializerMethodField()

    class Meta:
        model = Shipment
        fields = ['id', 'courier', 'courier_name', 'consignment_id', 'tracking_code', 'tracking_url',
                  'status', 'status_group', 'status_label', 'status_message', 'is_final',
                  'cod_amount', 'booked_at', 'status_updated_at', 'last_checked_at',
                  'refresh_available_in', 'events']

    def get_status_group(self, obj):
        return status_group(obj.status)

    def get_is_final(self, obj):
        return is_final(obj.status)

    def get_refresh_available_in(self, obj):
        return seconds_until_refresh(obj)

    def get_cod_amount(self, obj):
        """Cash the rider collects. Steadfast's latest figure replaces the amount booked with the order."""
        return _money(cash_to_collect(obj))

    def get_events(self, obj):
        return ShipmentEventSerializer(visible_tracking_events(obj.events.all()), many=True).data


class AdminShipmentSerializer(ShipmentSerializer):
    booked_by_name = serializers.CharField(source='booked_by.full_name', read_only=True, default=None)
    police_station_name = serializers.CharField(source='police_station.name', read_only=True, default=None)
    portal_url = serializers.SerializerMethodField()
    track_page_url = serializers.SerializerMethodField()
    cod_mismatch = serializers.SerializerMethodField()

    class Meta(ShipmentSerializer.Meta):
        fields = ShipmentSerializer.Meta.fields + [
            'invoice', 'recipient_name', 'recipient_phone', 'recipient_address', 'police_station_name',
            'courier_cod_amount', 'cod_mismatch', 'delivery_charge', 'note', 'booked_by', 'booked_by_name',
            'portal_url', 'track_page_url',
        ]

    def get_cod_amount(self, obj):
        """The amount this order was booked to collect. The rider's amount is ``courier_cod_amount``."""
        cash_to_collect(obj)
        return _money(obj.cod_amount)

    def get_cod_mismatch(self, obj):
        return cod_mismatch(obj)

    def get_portal_url(self, obj):
        return portal_url_for(obj) or None

    def get_track_page_url(self, obj):
        return track_url(obj.order) if obj.order_id else None

    def get_events(self, obj):
        return ShipmentEventSerializer(obj.events.all()[:40], many=True).data


class AdminShipmentOrderSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    order_number = serializers.CharField()
    customer_name = serializers.CharField()
    customer_phone = serializers.CharField()
    order_status = serializers.CharField()
    payment_status = serializers.CharField()
    order_type = serializers.CharField()
    total = serializers.DecimalField(max_digits=12, decimal_places=2)


def _order_summary(order):
    return {
        'id': order.id,
        'order_number': order.order_number,
        'customer_name': order.customer_name,
        'customer_phone': order.customer_phone,
        'order_status': order.order_status,
        'payment_status': order.payment_status,
        'order_type': order.order_type,
        'total': order.total,
    }


class AdminShipmentListSerializer(AdminShipmentSerializer):
    """Row for the admin shipments table (no event timeline)."""

    order = serializers.SerializerMethodField()

    class Meta(AdminShipmentSerializer.Meta):
        fields = [f for f in AdminShipmentSerializer.Meta.fields if f != 'events'] + ['order']

    def get_order(self, obj):
        return AdminShipmentOrderSummarySerializer(_order_summary(obj.order)).data


class AdminShipmentDetailSerializer(AdminShipmentSerializer):
    order = serializers.SerializerMethodField()
    live_trackings = serializers.SerializerMethodField()

    class Meta(AdminShipmentSerializer.Meta):
        fields = AdminShipmentSerializer.Meta.fields + ['order', 'live_trackings']

    def get_order(self, obj):
        return AdminShipmentOrderSummarySerializer(_order_summary(obj.order)).data

    def get_live_trackings(self, obj):
        return self.context.get('live_trackings')


def serialize_shipment(order, context=None):
    """Nested shipment for an order payload, or ``None`` before booking."""
    # The reverse one-to-one raises a DoesNotExist that is also an AttributeError.
    shipment = getattr(order, 'shipment', None)
    if shipment is None:
        return None
    request = (context or {}).get('request')
    user = getattr(request, 'user', None)
    staff = bool(user and user.is_authenticated and getattr(user, 'role', None) in STAFF_ROLES)
    serializer_cls = AdminShipmentSerializer if staff else ShipmentSerializer
    return serializer_cls(shipment, context=context).data


class BookShipmentSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)
    recipient_address = serializers.CharField(required=False, allow_blank=True, max_length=250)
    police_station_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)


class ImportShipmentPreviewSerializer(serializers.Serializer):
    consignment_id = serializers.CharField(required=False, allow_blank=True, max_length=50)
    tracking_code = serializers.CharField(required=False, allow_blank=True, max_length=64)

    def validate(self, attrs):
        consignment_id = (attrs.get('consignment_id') or '').strip()
        tracking_code = (attrs.get('tracking_code') or '').strip()
        if not consignment_id and not tracking_code:
            raise serializers.ValidationError('Provide a consignment ID or tracking code.')
        attrs['consignment_id'] = consignment_id
        attrs['tracking_code'] = tracking_code
        return attrs


class ImportShipmentSerializer(ImportShipmentPreviewSerializer):
    order_id = serializers.UUIDField()
