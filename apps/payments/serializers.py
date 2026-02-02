"""
Serializers for payments app.
"""
from rest_framework import serializers
from .models import Payment, Refund


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model."""
    order_number = serializers.CharField(source='order.order_number', read_only=True)

    class Meta:
        model = Payment
        fields = ['id', 'order', 'order_number', 'payment_method', 'status',
                  'amount', 'currency', 'transaction_id', 'bank_transaction_id',
                  'card_type', 'card_brand', 'created_at', 'completed_at']
        read_only_fields = ['id', 'created_at', 'completed_at']


class InitiatePaymentSerializer(serializers.Serializer):
    """Serializer for initiating SSLCommerz payment."""
    order_id = serializers.UUIDField()


class PaymentCallbackSerializer(serializers.Serializer):
    """Serializer for SSLCommerz callback data."""
    tran_id = serializers.CharField()
    val_id = serializers.CharField(required=False)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    card_type = serializers.CharField(required=False)
    store_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    card_no = serializers.CharField(required=False)
    bank_tran_id = serializers.CharField(required=False)
    status = serializers.CharField()
    tran_date = serializers.CharField(required=False)
    error = serializers.CharField(required=False)
    currency = serializers.CharField(required=False)
    card_issuer = serializers.CharField(required=False)
    card_brand = serializers.CharField(required=False)
    card_issuer_country = serializers.CharField(required=False)
    card_issuer_country_code = serializers.CharField(required=False)
    currency_type = serializers.CharField(required=False)
    currency_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    verify_sign = serializers.CharField(required=False)
    verify_key = serializers.CharField(required=False)
    risk_level = serializers.CharField(required=False)
    risk_title = serializers.CharField(required=False)


class RefundSerializer(serializers.ModelSerializer):
    """Serializer for Refund model."""
    payment_order_number = serializers.CharField(source='payment.order.order_number', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.full_name', read_only=True)
    processed_by_name = serializers.CharField(source='processed_by.full_name', read_only=True)

    class Meta:
        model = Refund
        fields = ['id', 'payment', 'payment_order_number', 'amount', 'reason',
                  'status', 'refund_transaction_id', 'requested_by', 'requested_by_name',
                  'processed_by', 'processed_by_name', 'created_at', 'processed_at']
        read_only_fields = ['id', 'requested_by', 'processed_by', 'created_at', 'processed_at']


class CreateRefundSerializer(serializers.Serializer):
    """Serializer for creating refund request."""
    payment_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    reason = serializers.CharField()


class ProcessRefundSerializer(serializers.Serializer):
    """Serializer for processing refund."""
    status = serializers.ChoiceField(choices=['approved', 'rejected'])
    note = serializers.CharField(required=False)
