"""Invoice downloads. Links are signed so the PDF opens in a browser without a login."""
import logging

from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffUser

from .emails import order_email, send_invoice_email
from .invoice import (
    APP_LINK_SECONDS,
    build_invoice_pdf,
    invoice_available,
    invoice_filename,
    invoice_url,
    order_id_from_token,
)
from .models import Order

logger = logging.getLogger(__name__)

NOT_READY = 'The invoice is ready once the order has shipped.'


def _orders():
    return Order.objects.select_related('shipment').prefetch_related('items')


def _link_payload(order):
    return {'url': invoice_url(order, APP_LINK_SECONDS), 'expires_in': APP_LINK_SECONDS}


class InvoiceDownloadView(APIView):
    """GET /orders/invoice/<token>/ — the PDF for a signed link from mail, the app or the website."""
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'invoice_download'

    def get(self, request, token):
        order_id = order_id_from_token(token)
        order = _orders().filter(pk=order_id).first() if order_id else None
        if order is None:
            return Response(
                {'detail': 'This invoice link has expired. Open the order to get a new one.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        response = HttpResponse(build_invoice_pdf(order), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{invoice_filename(order)}"'
        response['Cache-Control'] = 'private, no-store'
        response['X-Robots-Tag'] = 'noindex'
        return response


class CustomerInvoiceLinkView(APIView):
    """POST /orders/my-orders/<id>/invoice/link/ — a download link that works for 10 minutes."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        order = Order.objects.filter(pk=pk, user=request.user).first()
        if order is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not invoice_available(order):
            return Response({'code': 'invoice_not_ready', 'detail': NOT_READY}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_link_payload(order))


class AdminInvoiceLinkView(APIView):
    """POST /orders/admin/<id>/invoice/link/ — staff can download any order's invoice."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def post(self, request, pk):
        order = Order.objects.filter(pk=pk).first()
        if order is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(_link_payload(order))


class AdminInvoiceResendView(APIView):
    """POST /orders/admin/<id>/invoice/resend/ — mail the invoice to the customer again."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def post(self, request, pk):
        order = Order.objects.filter(pk=pk).first()
        if order is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not invoice_available(order):
            return Response({'code': 'invoice_not_ready', 'detail': NOT_READY}, status=status.HTTP_400_BAD_REQUEST)
        recipient = order_email(order)
        if not recipient:
            return Response(
                {'code': 'no_email', 'detail': 'This order has no customer email address.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from .tasks import send_invoice_email_task

        try:
            send_invoice_email_task.delay(str(order.pk))
        except Exception:
            logger.warning('Could not queue the invoice email for %s; sending it now', order.pk, exc_info=True)
            try:
                send_invoice_email(order)
            except Exception:
                logger.exception('Invoice email failed for %s', order.pk)
                return Response(
                    {'code': 'email_failed', 'detail': 'The invoice email could not be sent. Try again shortly.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
        return Response({'detail': f'Invoice sent to {recipient}.'})
