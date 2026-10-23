"""
Views for payments app with SSLCommerz integration.
"""
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.conf import settings
from django.utils import timezone
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import uuid
from .models import Payment, Refund
from .serializers import (
    PaymentSerializer, OrderPaymentSerializer, InitiatePaymentSerializer,
    PaymentCallbackSerializer, RefundSerializer, CreateRefundSerializer,
    ProcessRefundSerializer
)
from apps.orders.models import Order
from apps.orders.services import change_order_status, record_online_payment
from apps.notifications.services import notify_refund_requested
from apps.accounts.permissions import IsStaffUser, IsAccountant


class InitiatePaymentView(APIView):
    """Initiate SSLCommerz payment for an order."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = InitiatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            order = Order.objects.get(id=serializer.validated_data['order_id'])
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if order.payment_status == 'paid':
            return Response(
                {'error': 'Order is already paid'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create pending payment
        transaction_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"
        payment = Payment.objects.create(
            order=order,
            payment_method='sslcommerz',
            amount=order.total,
            transaction_id=transaction_id,
        )
        
        # SSLCommerz settings
        store_id = settings.SSLCOMMERZ_STORE_ID
        store_passwd = settings.SSLCOMMERZ_STORE_PASSWORD
        is_sandbox = settings.SSLCOMMERZ_SANDBOX
        
        if not store_id or not store_passwd:
            return Response(
                {'error': 'Payment gateway not configured'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Prepare SSLCommerz request data
        post_body = {
            'store_id': store_id,
            'store_passwd': store_passwd,
            'total_amount': float(order.total),
            'currency': 'BDT',
            'tran_id': transaction_id,
            'success_url': f"{settings.FRONTEND_URL}/payment/success",
            'fail_url': f"{settings.FRONTEND_URL}/payment/failed",
            'cancel_url': f"{settings.FRONTEND_URL}/payment/cancelled",
            'ipn_url': f"{request.build_absolute_uri('/api/v1/payments/ipn/')}",
            'cus_name': order.shipping_name,
            'cus_email': order.customer_email or 'customer@example.com',
            'cus_phone': order.shipping_phone,
            'cus_add1': order.shipping_address_line1,
            'cus_city': order.shipping_city,
            'cus_country': 'Bangladesh',
            'shipping_method': 'Courier',
            'product_name': 'Clothing Items',
            'product_category': 'Clothing',
            'product_profile': 'physical-goods',
            'num_of_item': order.item_count,
            'ship_name': order.shipping_name,
            'ship_add1': order.shipping_address_line1,
            'ship_city': order.shipping_city,
            'ship_country': 'Bangladesh',
        }
        
        # Initialize SSLCommerz session
        try:
            from sslcommerz_lib import SSLCOMMERZ
            
            sslcz = SSLCOMMERZ({
                'store_id': store_id,
                'store_pass': store_passwd,
                'issandbox': is_sandbox
            })
            
            response = sslcz.createSession(post_body)
            
            if response.get('status') == 'SUCCESS':
                payment.session_key = response.get('sessionkey')
                payment.status = 'processing'
                payment.save()
                
                return Response({
                    'payment_url': response.get('GatewayPageURL'),
                    'session_key': response.get('sessionkey'),
                    'transaction_id': transaction_id
                })
            else:
                payment.status = 'failed'
                payment.gateway_response = response
                payment.save()
                
                return Response(
                    {'error': 'Failed to create payment session', 'details': response},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except ImportError:
            # Fallback for development without sslcommerz-lib
            return Response({
                'message': 'SSLCommerz library not available. Using mock response.',
                'payment_url': f"{settings.FRONTEND_URL}/payment/mock?tran_id={transaction_id}",
                'transaction_id': transaction_id
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(csrf_exempt, name='dispatch')
class PaymentIPNView(APIView):
    """Handle SSLCommerz IPN (Instant Payment Notification)."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PaymentCallbackSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        transaction_id = data.get('tran_id')
        payment_status = data.get('status')
        
        try:
            payment = Payment.objects.get(transaction_id=transaction_id)
        except Payment.DoesNotExist:
            return Response(
                {'error': 'Payment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        gateway_fields = {
            'val_id': data.get('val_id'),
            'bank_transaction_id': data.get('bank_tran_id'),
            'card_type': data.get('card_type'),
            'card_brand': data.get('card_brand'),
            'gateway_response': dict(data),
        }
        if payment_status in ('VALID', 'VALIDATED'):
            outcome = 'paid'
        elif payment_status == 'FAILED':
            outcome = 'failed'
        elif payment_status == 'CANCELLED':
            outcome = 'cancelled'
        else:
            for field, value in gateway_fields.items():
                setattr(payment, field, value)
            payment.save()
            return Response({'message': 'IPN processed'})

        record_online_payment(payment, outcome, gateway_fields=gateway_fields)
        return Response({'message': 'IPN processed'})


@method_decorator(csrf_exempt, name='dispatch')
class PaymentSuccessView(APIView):
    """Handle SSLCommerz success callback."""
    permission_classes = [AllowAny]

    def post(self, request):
        transaction_id = request.data.get('tran_id')
        
        try:
            payment = Payment.objects.get(transaction_id=transaction_id)
            
            if payment.status == 'processing':
                record_online_payment(payment, 'paid')
            
            return redirect(f"{settings.FRONTEND_URL}/order-success/{payment.order.order_number}")
        except Payment.DoesNotExist:
            return redirect(f"{settings.FRONTEND_URL}/payment/error")


@method_decorator(csrf_exempt, name='dispatch')
class PaymentFailView(APIView):
    """Handle SSLCommerz fail callback."""
    permission_classes = [AllowAny]

    def post(self, request):
        transaction_id = request.data.get('tran_id')
        
        try:
            payment = Payment.objects.get(transaction_id=transaction_id)
            record_online_payment(payment, 'failed')
        except Payment.DoesNotExist:
            pass
        
        return redirect(f"{settings.FRONTEND_URL}/payment/failed")


@method_decorator(csrf_exempt, name='dispatch')
class PaymentCancelView(APIView):
    """Handle SSLCommerz cancel callback."""
    permission_classes = [AllowAny]

    def post(self, request):
        transaction_id = request.data.get('tran_id')
        
        try:
            payment = Payment.objects.get(transaction_id=transaction_id)
            record_online_payment(payment, 'cancelled')
        except Payment.DoesNotExist:
            pass
        
        return redirect(f"{settings.FRONTEND_URL}/payment/cancelled")


class PaymentListView(generics.ListAPIView):
    """Admin: List all orders as payment records."""
    serializer_class = OrderPaymentSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get_queryset(self):
        return Order.objects.exclude(
            order_status='cancelled'
        ).prefetch_related('payments').order_by('-created_at')


class PaymentDetailView(generics.RetrieveAPIView):
    """Admin: Get payment details."""
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, IsAccountant]
    queryset = Payment.objects.all()


class RefundListCreateView(generics.ListCreateAPIView):
    """Admin: List and create refunds."""
    serializer_class = RefundSerializer
    permission_classes = [IsAuthenticated, IsAccountant]

    def get_queryset(self):
        return Refund.objects.all().select_related('payment', 'payment__order')

    def create(self, request, *args, **kwargs):
        serializer = CreateRefundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            payment = Payment.objects.get(id=serializer.validated_data['payment_id'])
        except Payment.DoesNotExist:
            return Response(
                {'error': 'Payment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if payment.status != 'completed':
            return Response(
                {'error': 'Can only refund completed payments'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        refund = Refund.objects.create(
            payment=payment,
            amount=serializer.validated_data['amount'],
            reason=serializer.validated_data['reason'],
            requested_by=request.user
        )
        notify_refund_requested(refund)
        
        return Response(
            RefundSerializer(refund).data,
            status=status.HTTP_201_CREATED
        )


class ProcessRefundView(APIView):
    """Admin: Process refund request."""
    permission_classes = [IsAuthenticated, IsAccountant]

    def post(self, request, pk):
        serializer = ProcessRefundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            refund = Refund.objects.get(pk=pk)
        except Refund.DoesNotExist:
            return Response(
                {'error': 'Refund not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if refund.status != 'pending':
            return Response(
                {'error': 'Refund already processed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        refund.status = serializer.validated_data['status']
        refund.processed_by = request.user
        refund.processed_at = timezone.now()
        
        if refund.status == 'approved':
            refund.payment.status = 'refunded'
            refund.payment.save(update_fields=['status'])
            change_order_status(
                refund.payment.order,
                'refunded',
                note='Refund approved.',
                changed_by=request.user,
            )
        
        refund.save()
        
        return Response(RefundSerializer(refund).data)
