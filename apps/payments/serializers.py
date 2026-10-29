"""
Serializers for payments app.
"""
from django.db import IntegrityError, transaction
from rest_framework import serializers
from .models import Expense, Payment, Refund
from apps.orders.models import Order


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model."""
    order_number = serializers.CharField(source='order.order_number', read_only=True)

    class Meta:
        model = Payment
        fields = ['id', 'order', 'order_number', 'payment_method', 'status',
                  'amount', 'currency', 'transaction_id', 'bank_transaction_id',
                  'card_type', 'card_brand', 'created_at', 'completed_at']
        read_only_fields = ['id', 'created_at', 'completed_at']


class OrderPaymentSerializer(serializers.ModelSerializer):
    """Serializer that presents Order data as payment records."""
    transaction_id = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()
    amount = serializers.DecimalField(source='total', max_digits=10, decimal_places=2)
    status = serializers.SerializerMethodField()
    order = serializers.SerializerMethodField()
    order_number = serializers.CharField(read_only=True)
    customer_name = serializers.SerializerMethodField()
    customer_phone = serializers.SerializerMethodField()
    gateway_response = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'transaction_id', 'order', 'order_number', 'customer_name',
                  'customer_phone', 'payment_method', 'amount',
                  'status', 'created_at', 'gateway_response']

    def get_transaction_id(self, obj):
        return obj.transaction_id or f"ORD-{obj.order_number}"

    def get_payment_method(self, obj):
        if obj.payment_method:
            return obj.payment_method
        return 'cash' if obj.order_type == 'in_shop' else 'cod'

    def get_status(self, obj):
        return obj.payment_status

    def get_customer_name(self, obj):
        return obj.customer_name

    def get_customer_phone(self, obj):
        return obj.customer_phone

    def get_order(self, obj):
        return {
            'id': str(obj.id),
            'order_number': obj.order_number,
            'customer_name': obj.customer_name,
        }

    def get_gateway_response(self, obj):
        # Check if there's a linked Payment record with gateway data
        payment = obj.payments.first() if hasattr(obj, 'payments') else None
        if payment and payment.gateway_response:
            return payment.gateway_response
        return None


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


def next_voucher_number(expense_date):
    """Next EV-YYYYMMDD-#### for this date. Call inside a transaction."""
    prefix = f"EV-{expense_date.strftime('%Y%m%d')}-"
    latest = (
        Expense.objects.select_for_update()
        .filter(voucher_number__startswith=prefix)
        .order_by('-voucher_number')
        .first()
    )
    sequence = 1
    if latest:
        try:
            sequence = int(latest.voucher_number.rsplit('-', 1)[-1]) + 1
        except ValueError:
            sequence = 1
    return f"{prefix}{sequence:04d}"


class ExpenseSerializer(serializers.ModelSerializer):
    """Staff expense voucher. The voucher number is assigned on create."""
    product_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    category_label = serializers.CharField(source='get_category_display', read_only=True)
    payment_method_label = serializers.SerializerMethodField()
    is_purchase_voucher = serializers.SerializerMethodField()

    class Meta:
        model = Expense
        fields = [
            'id', 'voucher_number', 'expense_date', 'category', 'category_label',
            'description', 'amount', 'quantity', 'unit_cost',
            'payment_method', 'payment_method_label',
            'payee', 'product', 'product_name', 'stock_movement', 'is_purchase_voucher',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'voucher_number', 'stock_movement', 'created_by', 'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'payment_method': {'allow_blank': True, 'required': False},
            'payee': {'allow_blank': True, 'required': False},
            'product': {'allow_null': True, 'required': False},
            'quantity': {'required': False, 'allow_null': True},
            'unit_cost': {'required': False, 'allow_null': True},
        }

    def get_product_name(self, obj):
        return obj.product.name if obj.product_id else None

    def get_created_by_name(self, obj):
        user = getattr(obj, 'created_by', None)
        return user.full_name if user else None

    def get_payment_method_label(self, obj):
        return obj.get_payment_method_display() if obj.payment_method else ''

    def get_is_purchase_voucher(self, obj):
        return bool(obj.stock_movement_id)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Amount must be greater than zero.')
        return value

    def validate_payment_method(self, value):
        return value or ''

    def update(self, instance, validated_data):
        if instance.stock_movement_id:
            errors = {}
            if 'amount' in validated_data and validated_data['amount'] != instance.amount:
                errors['amount'] = 'This purchase voucher follows the stock purchase and cannot change this field.'
            if 'category' in validated_data and validated_data['category'] != instance.category:
                errors['category'] = 'This purchase voucher follows the stock purchase and cannot change this field.'
            if 'quantity' in validated_data and validated_data['quantity'] != instance.quantity:
                errors['quantity'] = 'This purchase voucher follows the stock purchase and cannot change this field.'
            if 'unit_cost' in validated_data and validated_data['unit_cost'] != instance.unit_cost:
                errors['unit_cost'] = 'This purchase voucher follows the stock purchase and cannot change this field.'
            if 'product' in validated_data:
                product = validated_data['product']
                product_id = product.pk if product is not None else None
                if product_id != instance.product_id:
                    errors['product'] = 'This purchase voucher follows the stock purchase and cannot change this field.'
            if errors:
                raise serializers.ValidationError(errors)
        return super().update(instance, validated_data)

    def create(self, validated_data):
        expense_date = validated_data['expense_date']
        for _attempt in range(5):
            try:
                with transaction.atomic():
                    return Expense.objects.create(
                        voucher_number=next_voucher_number(expense_date),
                        created_by=self.context['request'].user,
                        **validated_data,
                    )
            except IntegrityError:
                continue
        raise serializers.ValidationError({
            'voucher_number': 'Could not assign a voucher number.',
        })
