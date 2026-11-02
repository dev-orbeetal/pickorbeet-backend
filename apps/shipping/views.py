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
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffUser
from apps.orders.models import Order
from apps.orders.serializers import OrderDetailSerializer
from core.pagination import AdminPagination

from .models import Shipment
from .serializers import (
    AdminShipmentDetailSerializer,
    AdminShipmentListSerializer,
    BookShipmentSerializer,
    ImportShipmentPreviewSerializer,
    ImportShipmentSerializer,
)
from .services import (
    FINAL_STATUSES,
    STATUS_GROUP_ORDER,
    ShipmentCooldown,
    ShipmentError,
    apply_courier_status,
    book_shipment,
    bulk_refresh_shipments,
    import_shipment,
    preview_import,
    refresh_shipment,
    status_group,
    statuses_for_group,
)
from .steadfast import SteadfastClient, SteadfastError, SteadfastNotFoundError

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


def _shipment_queryset():
    return Shipment.objects.select_related('order', 'booked_by').prefetch_related('events')


def _filtered_shipments(request):
    qs = _shipment_queryset()
    status_value = (request.query_params.get('status') or '').strip()
    status_group_value = (request.query_params.get('status_group') or '').strip()
    search = (request.query_params.get('search') or '').strip()
    booked_from = parse_date((request.query_params.get('booked_from') or '').strip())
    booked_to = parse_date((request.query_params.get('booked_to') or '').strip())
    open_only = (request.query_params.get('open') or '').strip().lower() in {'1', 'true', 'yes'}

    if status_value:
        qs = qs.filter(status=status_value)
    if status_group_value:
        qs = qs.filter(status__in=statuses_for_group(status_group_value) or [status_group_value])
    if open_only:
        qs = qs.exclude(status__in=FINAL_STATUSES)
    if search:
        qs = qs.filter(
            Q(invoice__icontains=search)
            | Q(tracking_code__icontains=search)
            | Q(consignment_id__icontains=search)
            | Q(recipient_phone__icontains=search)
            | Q(recipient_name__icontains=search)
            | Q(order__order_number__icontains=search)
            | Q(order__shipping_phone__icontains=search)
        )
    if booked_from:
        qs = qs.filter(booked_at__date__gte=booked_from)
    if booked_to:
        qs = qs.filter(booked_at__date__lte=booked_to)
    return qs.order_by('-booked_at', '-created_at')


class AdminShipmentListView(APIView):
    """Staff: paginated local shipment list with filters."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get(self, request):
        qs = _filtered_shipments(request)
        paginator = AdminPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = AdminShipmentListSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class AdminShipmentSummaryView(APIView):
    """Staff: KPI counts by status group and open COD totals."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get(self, request):
        qs = _filtered_shipments(request)
        # Group counts from the filtered set (ignore status filters so chips stay useful).
        base = Shipment.objects.all()
        booked_from = parse_date((request.query_params.get('booked_from') or '').strip())
        booked_to = parse_date((request.query_params.get('booked_to') or '').strip())
        if booked_from:
            base = base.filter(booked_at__date__gte=booked_from)
        if booked_to:
            base = base.filter(booked_at__date__lte=booked_to)

        raw_counts = {row['status']: row['c'] for row in base.values('status').annotate(c=Count('id'))}
        by_group = {key: 0 for key in STATUS_GROUP_ORDER}
        for raw_status, count in raw_counts.items():
            group = status_group(raw_status)
            by_group[group] = by_group.get(group, 0) + count

        open_qs = base.exclude(status__in=FINAL_STATUSES)
        open_agg = open_qs.aggregate(open_count=Count('id'), open_cod=Sum('cod_amount'))
        return Response({
            'total': sum(by_group.values()),
            'by_status_group': by_group,
            'open_count': open_agg['open_count'] or 0,
            'open_cod_total': str(open_agg['open_cod'] or Decimal('0.00')),
            'filtered_count': qs.count(),
        })


class AdminShipmentDetailView(APIView):
    """Staff: shipment detail with local events; optional live Steadfast timeline."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get(self, request, pk):
        shipment = _shipment_queryset().filter(pk=pk).first()
        if shipment is None:
            return Response({'error': 'Shipment not found'}, status=status.HTTP_404_NOT_FOUND)

        live_trackings = None
        want_live = (request.query_params.get('live') or '').strip().lower() in {'1', 'true', 'yes'}
        if want_live and shipment.invoice:
            client = SteadfastClient()
            if client.is_configured:
                try:
                    live_trackings = client.trackings_by_invoice(shipment.invoice)
                except SteadfastNotFoundError:
                    live_trackings = []
                except SteadfastError as exc:
                    logger.info('Live tracking unavailable for %s: %s', shipment.invoice, exc)
                    live_trackings = None

        data = AdminShipmentDetailSerializer(
            shipment,
            context={'request': request, 'live_trackings': live_trackings},
        ).data
        return Response(data)


class AdminShipmentRefreshView(APIView):
    """Staff: force-refresh one shipment by id."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def post(self, request, pk):
        shipment = _shipment_queryset().filter(pk=pk).first()
        if shipment is None:
            return Response({'error': 'Shipment not found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            shipment, _ = refresh_shipment(shipment, force=True, source='manual')
        except ShipmentError as exc:
            return _error(exc)
        return Response(AdminShipmentDetailSerializer(shipment, context={'request': request}).data)


class AdminShipmentBulkRefreshView(APIView):
    """Staff: refresh up to N open (or explicitly listed) shipments."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def post(self, request):
        ids = request.data.get('ids') if hasattr(request.data, 'get') else None
        try:
            limit = int(request.data.get('limit', 50))
        except (TypeError, ValueError):
            limit = 50
        limit = max(1, min(limit, 100))
        try:
            pause = float(request.data.get('pause', 0.25))
        except (TypeError, ValueError):
            pause = 0.25
        pause = max(0.0, min(pause, 2.0))

        if ids:
            qs = _shipment_queryset().filter(pk__in=ids)
        else:
            qs = (
                _filtered_shipments(request)
                .exclude(status__in=FINAL_STATUSES)
                .exclude(consignment_id='', tracking_code='')
                .order_by('last_checked_at')
            )
        try:
            result = bulk_refresh_shipments(qs, limit=limit, pause=pause)
        except ShipmentError as exc:
            return _error(exc)
        return Response(result)


class AdminSteadfastBalanceView(APIView):
    """Staff: live merchant balance from Steadfast."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get(self, request):
        client = SteadfastClient()
        if not client.is_configured:
            return Response({'configured': False, 'current_balance': None})
        try:
            balance = client.get_balance()
        except SteadfastError as exc:
            return Response(
                {'configured': True, 'current_balance': None, 'error': str(exc.message)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({'configured': True, 'current_balance': balance})


class AdminShipmentImportPreviewView(APIView):
    """Staff: look up a Steadfast parcel before linking it to an order."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def post(self, request):
        serializer = ImportShipmentPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            preview = preview_import(**serializer.validated_data)
        except ShipmentError as exc:
            return _error(exc)
        return Response(preview)


class AdminShipmentImportView(APIView):
    """Staff: import an existing Steadfast consignment onto a PickOrbeet order."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def post(self, request):
        serializer = ImportShipmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        order = Order.objects.filter(pk=data['order_id']).first()
        if order is None:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            shipment = import_shipment(
                order,
                request.user,
                consignment_id=data.get('consignment_id', ''),
                tracking_code=data.get('tracking_code', ''),
            )
        except ShipmentError as exc:
            return _error(exc)
        shipment = _shipment_queryset().get(pk=shipment.pk)
        return Response(
            AdminShipmentDetailSerializer(shipment, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


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
