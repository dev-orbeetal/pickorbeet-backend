"""
Views for payments app with SSLCommerz integration.
"""
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.conf import settings
from django.db.models import Count, Sum
from django.utils import timezone
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import uuid
from .models import Expense, Payment, Refund
from .serializers import (
    PaymentSerializer, OrderPaymentSerializer, InitiatePaymentSerializer,
    PaymentCallbackSerializer, RefundSerializer, CreateRefundSerializer,
    ProcessRefundSerializer, ExpenseSerializer
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
        queryset = Order.objects.exclude(
            order_status='cancelled'
        ).select_related('user').prefetch_related('payments').order_by('-created_at')
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        return queryset


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


def _iso_date(value):
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return value.date().isoformat()


def _bounded(queryset, field, start_date, end_date):
    if start_date:
        queryset = queryset.filter(**{f'{field}__gte': start_date})
    if end_date:
        queryset = queryset.filter(**{f'{field}__lte': end_date})
    return queryset


class ExpenseListCreateView(generics.ListCreateAPIView):
    """Accountant: list and record expenses. Not copied from sales."""
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated, IsAccountant]
    pagination_class = None

    def get_queryset(self):
        queryset = Expense.objects.select_related('product', 'created_by')
        params = self.request.query_params
        queryset = _bounded(queryset, 'expense_date', params.get('start_date'), params.get('end_date'))
        product_id = params.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset


class ExpenseDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Accountant: review, correct, or remove one expense voucher."""
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated, IsAccountant]
    queryset = Expense.objects.select_related('product', 'created_by')

    def destroy(self, request, *args, **kwargs):
        expense = self.get_object()
        if expense.stock_movement_id:
            return Response(
                {'detail': 'Purchase vouchers are created from stock purchases and cannot be deleted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class FinanceSummaryView(APIView):
    """Current financial position. Actual totals stay separate from estimates."""
    permission_classes = [IsAuthenticated, IsAccountant]

    def get(self, request):
        from .finance import finance_summary
        return Response(finance_summary())


class ProductFinanceView(APIView):
    """Product profit from purchases, completed sales, and stock still on hand."""
    permission_classes = [IsAuthenticated, IsAccountant]

    def get(self, request):
        from .finance import product_finance
        return Response(product_finance())


class ExpenseByProductView(APIView):
    """Sum of recorded expenses grouped by product."""
    permission_classes = [IsAuthenticated, IsAccountant]

    def get(self, request):
        queryset = _bounded(
            Expense.objects.all(),
            'expense_date',
            request.query_params.get('start_date'),
            request.query_params.get('end_date'),
        )
        rows = queryset.values('product_id', 'product__name').annotate(
            total_amount=Sum('amount'),
            expense_count=Count('id'),
        ).order_by('-total_amount')
        return Response([
            {
                'product_id': str(row['product_id']) if row['product_id'] else None,
                'product_name': row['product__name'] or 'Unassigned',
                'total_amount': float(row['total_amount'] or 0),
                'expense_count': row['expense_count'],
            }
            for row in rows
        ])


class AdminIncomeView(APIView):
    """Paid orders as income lines. A completed payment is used once and is not added again as the order total."""
    permission_classes = [IsAuthenticated, IsAccountant]

    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        orders = Order.objects.filter(payment_status='paid').select_related('user').prefetch_related('payments')
        if start_date:
            orders = orders.filter(created_at__date__gte=start_date)
        if end_date:
            orders = orders.filter(created_at__date__lte=end_date)

        lines = []
        income_total = 0
        for order in orders.order_by('-created_at'):
            completed = [payment for payment in order.payments.all() if payment.status == 'completed']
            if completed:
                amount = sum((payment.amount for payment in completed))
                methods = {payment.payment_method for payment in completed}
                source = completed[0].payment_method if len(methods) == 1 else 'mixed'
                reference = order.order_number
                dated = completed[0].completed_at or completed[0].created_at or order.created_at
            else:
                amount = order.total
                source = order.payment_method or ('cash' if order.order_type == 'in_shop' else 'cod')
                reference = order.order_number
                dated = order.created_at
            income_total += amount
            lines.append({
                'id': str(order.id),
                'date': _iso_date(dated),
                'source': source,
                'reference': reference,
                'customer_name': order.customer_name,
                'amount': float(amount),
            })

        refunds = Refund.objects.filter(
            status__in=['approved', 'processed']
        ).select_related('payment__order', 'payment__order__user')
        if start_date:
            refunds = refunds.filter(created_at__date__gte=start_date)
        if end_date:
            refunds = refunds.filter(created_at__date__lte=end_date)

        refund_lines = []
        subtracted = 0
        for refund in refunds.order_by('-created_at'):
            order = refund.payment.order
            still_in_income = order.payment_status == 'paid'
            amount = float(refund.amount)
            if still_in_income:
                subtracted += refund.amount
            refund_lines.append({
                'id': str(refund.id),
                'date': _iso_date(refund.processed_at or refund.created_at),
                'amount': amount,
                'order_number': order.order_number,
                'status': refund.status,
                'subtracted': still_in_income,
            })

        return Response({
            'income': lines,
            'income_total': float(income_total),
            'refunds': refund_lines,
            'refunds_subtracted': float(subtracted),
            'net_income': float(income_total - subtracted),
        })
