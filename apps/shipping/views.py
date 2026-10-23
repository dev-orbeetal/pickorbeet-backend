"""
Views for courier shipments.
"""
import hashlib
import hmac
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffUser
from apps.orders.models import Order
from apps.orders.serializers import OrderDetailSerializer

from .models import Shipment
from .serializers import BookShipmentSerializer
from .services import ShipmentCooldown, ShipmentError, apply_courier_status, book_shipment, refresh_shipment

logger = logging.getLogger(__name__)


def _error(exc):
    body = {'error': exc.message, 'code': exc.code}
    headers = {}
    if isinstance(exc, ShipmentCooldown):
        body['retry_after'] = exc.retry_after
        headers['Retry-After'] = str(exc.retry_after)
    return Response(body, status=exc.http_status, headers=headers)


def _order_payload(request, pk, http_status=status.HTTP_200_OK):
    order = Order.objects.select_related('shipment').get(pk=pk)
    return Response(OrderDetailSerializer(order, context={'request': request}).data, status=http_status)


class AdminBookShipmentView(APIView):
    """Staff: send an order to Steadfast."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def post(self, request, pk):
        order = Order.objects.filter(pk=pk).first()
        if order is None:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = BookShipmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            book_shipment(order, request.user, note=serializer.validated_data.get('note', ''))
        except ShipmentError as exc:
            return _error(exc)
        return _order_payload(request, pk, status.HTTP_201_CREATED)


class AdminRefreshShipmentView(APIView):
    """Staff: fetch the latest courier status now, ignoring the cooldown."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def post(self, request, pk):
        shipment = Shipment.objects.filter(order_id=pk).first()
        if shipment is None:
            if not Order.objects.filter(pk=pk).exists():
                return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
            return Response({'error': 'This order has not been sent to Steadfast yet.', 'code': 'not_booked'},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            refresh_shipment(shipment, force=True)
        except ShipmentError as exc:
            return _error(exc)
        return _order_payload(request, pk)


class CustomerRefreshShipmentView(APIView):
    """Customer: refresh the courier status of one of their own orders."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'shipment_refresh'

    def post(self, request, pk):
        if not Order.objects.filter(pk=pk, user=request.user).exists():
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        shipment = Shipment.objects.filter(order_id=pk).first()
        if shipment is None:
            return Response({'error': 'This order has not been handed to the courier yet.', 'code': 'not_booked'},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            refresh_shipment(shipment)
        except ShipmentError as exc:
            return _error(exc)
        return _order_payload(request, pk)


def _parse_courier_time(value):
    """Steadfast sends local (Asia/Dhaka) times such as ``2025-03-02 12:45:30``."""
    if not value:
        return None
    text = str(value).strip().replace('T', ' ').rstrip('Z')
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M'):
        try:
            parsed = datetime.strptime(text[:26], fmt)
        except ValueError:
            continue
        return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
    return None


def _parse_amount(value):
    if value in (None, ''):
        return None
    try:
        return Decimal(str(value)).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        return None


class SteadfastWebhookView(APIView):
    """Steadfast pushes ``delivery_status`` and ``tracking_update`` notifications here."""
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def post(self, request):
        expected = settings.STEADFAST_WEBHOOK_TOKEN or ''
        header = request.META.get('HTTP_AUTHORIZATION', '')
        token = header[7:].strip() if header[:7].lower() == 'bearer ' else ''
        if not expected or not token or not hmac.compare_digest(token.encode(), expected.encode()):
            return Response({'status': 'error', 'message': 'Unauthorized.'}, status=status.HTTP_401_UNAUTHORIZED)

        data = request.data if hasattr(request.data, 'get') else {}
        notification_type = str(data.get('notification_type') or '').strip().lower()
        if notification_type not in {'delivery_status', 'tracking_update'}:
            return Response({'status': 'error', 'message': 'Unsupported notification type.'},
                            status=status.HTTP_400_BAD_REQUEST)

        consignment_id = str(data.get('consignment_id') or '').strip()
        invoice = str(data.get('invoice') or '').strip()
        lookup = Q(pk__in=[])
        if consignment_id:
            lookup |= Q(consignment_id=consignment_id)
        if invoice:
            lookup |= Q(invoice=invoice)
        shipment = Shipment.objects.filter(lookup).first()
        if shipment is None:
            return Response({'status': 'error', 'message': 'Invalid consignment ID.'},
                            status=status.HTTP_404_NOT_FOUND)

        raw_status = str(data.get('status') or '') if notification_type == 'delivery_status' else ''
        message = str(data.get('tracking_message') or '')[:1000]
        updated_at = data.get('updated_at')
        key = (request.headers.get('Idempotency-Key') or '').strip()[:128]
        if not key:
            digest = hashlib.sha256(
                f'{notification_type}|{consignment_id}|{invoice}|{raw_status}|{message}|{updated_at}'.encode()
            ).hexdigest()
            key = f'sf:{digest}'

        try:
            apply_courier_status(
                shipment,
                raw_status,
                source='webhook',
                message=message,
                payload=dict(data.items()) if hasattr(data, 'items') else {},
                idempotency_key=key,
                occurred_at=_parse_courier_time(updated_at),
                delivery_charge=_parse_amount(data.get('delivery_charge')),
            )
        except IntegrityError:
            # A concurrent delivery of the same notification won the insert.
            logger.info('Duplicate Steadfast webhook %s ignored', key)

        return Response({'status': 'success', 'message': 'Webhook received successfully.'})
