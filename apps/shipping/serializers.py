"""
Serializers for courier shipments.
"""
from rest_framework import serializers

from .models import Shipment, ShipmentEvent
from .services import is_final, seconds_until_refresh, status_group

STAFF_ROLES = {'seller', 'accountant', 'super_admin'}


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

    def get_events(self, obj):
        return ShipmentEventSerializer(obj.events.all()[:20], many=True).data


class AdminShipmentSerializer(ShipmentSerializer):
    booked_by_name = serializers.CharField(source='booked_by.full_name', read_only=True, default=None)

    class Meta(ShipmentSerializer.Meta):
        fields = ShipmentSerializer.Meta.fields + [
            'invoice', 'recipient_name', 'recipient_phone', 'recipient_address',
            'delivery_charge', 'note', 'booked_by', 'booked_by_name',
        ]


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
