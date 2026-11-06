"""
Serializers for payments app.
"""
import json

from django.db import IntegrityError, transaction
from rest_framework import serializers
from .models import Expense, ManualIncome, Payment, PurchaseReceipt, PurchaseReceiptLine, Refund
from apps.orders.models import Order

MAX_PAYMENT_PROOF_BYTES = 5 * 1024 * 1024


def _looks_like_payment_proof(header):
    if header.startswith(b'\xff\xd8\xff'):
        return True
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return True
    if len(header) >= 12 and header.startswith(b'RIFF') and header[8:12] == b'WEBP':
        return True
    if header.startswith(b'%PDF'):
        return True
    return False


class PaymentProofField(serializers.FileField):
    """JPEG, PNG, WebP, or PDF up to 5 MB."""

    default_error_messages = {
        'invalid_type': 'Upload a JPEG, PNG, WebP, or PDF payment proof.',
        'max_size': 'Payment proof must be 5 MB or smaller.',
        'empty': 'Choose a payment proof file.',
    }

    def to_internal_value(self, data):
        size = getattr(data, 'size', None)
        if size == 0:
            self.fail('empty')
        if size is not None and size > MAX_PAYMENT_PROOF_BYTES:
            self.fail('max_size')
        if hasattr(data, 'read'):
            header = data.read(16)
            if hasattr(data, 'seek'):
                data.seek(0)
            if not _looks_like_payment_proof(header):
                self.fail('invalid_type')
        return super().to_internal_value(data)

    def to_representation(self, value):
        if not value:
            return None
        try:
            return value.url
        except AttributeError:
            return None


def _apply_payment_proof(instance, uploaded, clear=False):
    previous = instance.payment_proof.name if instance.payment_proof else ''
    storage = instance.payment_proof.storage
    if uploaded is not serializers.empty and uploaded is not None:
        instance.payment_proof = uploaded
        instance.save(update_fields=['payment_proof', 'updated_at'])
    elif clear:
        instance.payment_proof = None
        instance.save(update_fields=['payment_proof', 'updated_at'])
    if previous and (uploaded is not serializers.empty or clear):
        if previous != (instance.payment_proof.name if instance.payment_proof else ''):
            try:
                storage.delete(previous)
            except Exception:
                pass
    return instance


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


def next_voucher_number(model, date_value, prefix_letter, field_name='voucher_number'):
    """Next {prefix}-YYYYMMDD-#### for this date. Call inside a transaction."""
    prefix = f"{prefix_letter}-{date_value.strftime('%Y%m%d')}-"
    latest = (
        model.objects.select_for_update()
        .filter(**{f'{field_name}__startswith': prefix})
        .order_by(f'-{field_name}')
        .first()
    )
    sequence = 1
    if latest:
        try:
            sequence = int(getattr(latest, field_name).rsplit('-', 1)[-1]) + 1
        except ValueError:
            sequence = 1
    return f"{prefix}{sequence:04d}"


def next_expense_voucher_number(expense_date):
    return next_voucher_number(Expense, expense_date, 'EV')


def next_income_voucher_number(income_date):
    return next_voucher_number(ManualIncome, income_date, 'IV')


class PurchaseReceiptLineSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    variant_label = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseReceiptLine
        fields = [
            'id', 'product', 'product_name', 'variant', 'variant_label',
            'quantity', 'unit_cost', 'discount_type', 'discount_value',
            'line_subtotal', 'discount_amount', 'line_total', 'effective_unit_cost',
            'stock_movement', 'sort_order',
        ]
        read_only_fields = fields

    def get_product_name(self, obj):
        return obj.product.name if obj.product_id else None

    def get_variant_label(self, obj):
        variant = obj.variant
        if variant is None:
            return None
        parts = [part for part in (variant.size, variant.color) if part]
        return ' / '.join(parts) if parts else (variant.sku or str(variant.id))


class PurchaseReceiptLineInputSerializer(serializers.Serializer):
    product = serializers.UUIDField()
    variant = serializers.UUIDField(required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1)
    unit_cost = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    discount_type = serializers.ChoiceField(
        choices=[choice[0] for choice in PurchaseReceiptLine.DISCOUNT_TYPE_CHOICES],
        required=False,
        default=PurchaseReceiptLine.DISCOUNT_NONE,
    )
    discount_value = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=0, min_value=0,
    )


class PurchaseReceiptSerializer(serializers.ModelSerializer):
    lines = PurchaseReceiptLineSerializer(many=True, read_only=True)
    stock_location_label = serializers.CharField(
        source='get_stock_location_display', read_only=True,
    )
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    payment_method_label = serializers.SerializerMethodField()
    expense_id = serializers.SerializerMethodField()
    voucher_number = serializers.SerializerMethodField()
    payment_proof = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    line_inputs = PurchaseReceiptLineInputSerializer(many=True, write_only=True, required=False)
    payment_proof_file = PaymentProofField(write_only=True, required=False, allow_null=True)
    clear_payment_proof = serializers.BooleanField(write_only=True, required=False, default=False)
    # Declared so the model's unique check does not reject a retry before create() sees it.
    idempotency_key = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = PurchaseReceipt
        fields = [
            'id', 'receipt_number', 'purchase_date', 'payee', 'invoice_number',
            'comments', 'payment_method', 'payment_method_label',
            'stock_location', 'stock_location_label', 'status', 'status_label',
            'total_quantity', 'subtotal', 'total_discount',
            'additional_discount_type', 'additional_discount_value', 'additional_discount',
            'grand_total',
            'lines', 'line_inputs', 'expense_id', 'voucher_number', 'payment_proof',
            'payment_proof_file', 'clear_payment_proof', 'idempotency_key',
            'created_by', 'created_by_name', 'cancelled_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'receipt_number', 'status', 'total_quantity', 'subtotal',
            'total_discount', 'additional_discount', 'grand_total', 'created_by',
            'cancelled_at', 'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'invoice_number': {'allow_blank': True, 'required': False},
            'comments': {'allow_blank': True, 'required': False},
            'payment_method': {'allow_blank': True, 'required': False},
            'additional_discount_type': {'required': False},
            'additional_discount_value': {'required': False},
        }

    def to_internal_value(self, data):
        # Multipart QueryDict values must be copied into a plain dict before
        # replacing line_inputs with a parsed list.
        if hasattr(data, 'keys'):
            plain = {key: data.get(key) for key in data.keys()}
        else:
            plain = data
        raw_lines = plain.get('line_inputs') if isinstance(plain, dict) else None
        if isinstance(raw_lines, str) and raw_lines.strip():
            try:
                plain['line_inputs'] = json.loads(raw_lines)
            except json.JSONDecodeError as exc:
                raise serializers.ValidationError({
                    'line_inputs': 'Invalid product line data.',
                }) from exc
        # Multipart forms may send the file under payment_proof.
        if isinstance(plain, dict) and 'payment_proof' in plain and 'payment_proof_file' not in plain:
            plain['payment_proof_file'] = plain.get('payment_proof')
        return super().to_internal_value(plain)

    def get_payment_method_label(self, obj):
        return obj.get_payment_method_display() if obj.payment_method else ''

    def get_expense_id(self, obj):
        expense = getattr(obj, 'expense', None)
        return str(expense.id) if expense else None

    def get_voucher_number(self, obj):
        expense = getattr(obj, 'expense', None)
        return expense.voucher_number if expense else None

    def get_payment_proof(self, obj):
        expense = getattr(obj, 'expense', None)
        if expense is None or not expense.payment_proof:
            return None
        try:
            return expense.payment_proof.url
        except AttributeError:
            return None

    def get_created_by_name(self, obj):
        user = getattr(obj, 'created_by', None)
        return user.full_name if user else None

    def validate_payee(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Dealer/seller name is required.')
        return value

    def create(self, validated_data):
        from apps.products.costing import StockError
        from .purchases import create_purchase_receipt

        lines = validated_data.pop('line_inputs', None)
        proof = validated_data.pop('payment_proof_file', serializers.empty)
        validated_data.pop('clear_payment_proof', False)
        if not lines:
            raise serializers.ValidationError({'line_inputs': 'Add at least one product line.'})
        try:
            receipt, expense = create_purchase_receipt(
                purchase_date=validated_data['purchase_date'],
                payee=validated_data['payee'],
                lines=lines,
                stock_location=validated_data.get('stock_location', 'warehouse'),
                invoice_number=validated_data.get('invoice_number', ''),
                comments=validated_data.get('comments', ''),
                payment_method=validated_data.get('payment_method', ''),
                additional_discount_type=validated_data.get(
                    'additional_discount_type', PurchaseReceipt.DISCOUNT_NONE,
                ),
                additional_discount_value=validated_data.get('additional_discount_value', 0),
                idempotency_key=validated_data.get('idempotency_key'),
                user=self.context['request'].user,
            )
        except StockError as exc:
            raise serializers.ValidationError({'detail': exc.message}) from exc
        if expense is not None and proof is not serializers.empty and proof is not None:
            _apply_payment_proof(expense, proof)
        return (
            PurchaseReceipt.objects.select_related('expense', 'created_by')
            .prefetch_related('lines__product', 'lines__variant')
            .get(pk=receipt.pk)
        )

    def update(self, instance, validated_data):
        from apps.products.costing import StockError
        from .purchases import update_purchase_receipt

        lines = validated_data.pop('line_inputs', None)
        proof = validated_data.pop('payment_proof_file', serializers.empty)
        clear_proof = bool(validated_data.pop('clear_payment_proof', False))
        try:
            receipt, expense = update_purchase_receipt(
                instance,
                purchase_date=validated_data.get('purchase_date'),
                payee=validated_data.get('payee'),
                lines=lines,
                stock_location=validated_data.get('stock_location'),
                invoice_number=validated_data.get('invoice_number'),
                comments=validated_data.get('comments'),
                payment_method=validated_data.get('payment_method'),
                additional_discount_type=validated_data.get('additional_discount_type'),
                additional_discount_value=validated_data.get('additional_discount_value'),
                user=self.context['request'].user,
            )
        except StockError as exc:
            raise serializers.ValidationError({'detail': exc.message}) from exc
        if proof is not serializers.empty or clear_proof:
            _apply_payment_proof(expense, proof, clear=clear_proof)
        return (
            PurchaseReceipt.objects.select_related('expense', 'created_by')
            .prefetch_related('lines__product', 'lines__variant')
            .get(pk=receipt.pk)
        )


class ExpenseSerializer(serializers.ModelSerializer):
    """Staff expense voucher. The voucher number is assigned on create."""
    product_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    category_label = serializers.CharField(source='get_category_display', read_only=True)
    payment_method_label = serializers.SerializerMethodField()
    is_purchase_voucher = serializers.SerializerMethodField()
    purchase_receipt_id = serializers.UUIDField(read_only=True)
    purchase_receipt = serializers.SerializerMethodField()
    payment_proof = PaymentProofField(required=False, allow_null=True)
    clear_payment_proof = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = Expense
        fields = [
            'id', 'voucher_number', 'expense_date', 'category', 'category_label',
            'description', 'comments', 'amount', 'quantity', 'unit_cost',
            'payment_method', 'payment_method_label', 'payment_proof', 'clear_payment_proof',
            'payee', 'product', 'product_name', 'stock_movement',
            'purchase_receipt_id', 'purchase_receipt', 'is_purchase_voucher',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'voucher_number', 'stock_movement', 'purchase_receipt_id',
            'created_by', 'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'payment_method': {'allow_blank': True, 'required': False},
            'payee': {'allow_blank': True, 'required': False},
            'comments': {'allow_blank': True, 'required': False},
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
        return bool(obj.stock_movement_id or obj.purchase_receipt_id)

    def get_purchase_receipt(self, obj):
        receipt = getattr(obj, 'purchase_receipt', None)
        if receipt is None:
            return None
        return PurchaseReceiptSerializer(receipt, context=self.context).data

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Amount must be greater than zero.')
        return value

    def validate_payment_method(self, value):
        return value or ''

    def validate(self, attrs):
        category = attrs.get('category', getattr(self.instance, 'category', None))
        if category == 'product_buying' and self.instance is None:
            raise serializers.ValidationError({
                'category': (
                    'Product Buying must be recorded as a purchase receipt so inventory '
                    'updates automatically. Use the purchase receipt form.'
                ),
            })
        payee = attrs.get('payee', getattr(self.instance, 'payee', '') if self.instance else '')
        if category == 'product_buying' and not (payee or '').strip():
            raise serializers.ValidationError({
                'payee': 'Dealer/seller name is required for Product Buying expenses.',
            })
        return attrs

    def update(self, instance, validated_data):
        clear_proof = bool(validated_data.pop('clear_payment_proof', False))
        proof = validated_data.pop('payment_proof', serializers.empty)
        if instance.stock_movement_id or instance.purchase_receipt_id:
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
        instance = super().update(instance, validated_data)
        if proof is not serializers.empty or clear_proof:
            _apply_payment_proof(instance, proof, clear=clear_proof)
        return instance

    def create(self, validated_data):
        validated_data.pop('clear_payment_proof', False)
        proof = validated_data.pop('payment_proof', None)
        expense_date = validated_data['expense_date']
        for _attempt in range(5):
            try:
                with transaction.atomic():
                    expense = Expense.objects.create(
                        voucher_number=next_expense_voucher_number(expense_date),
                        created_by=self.context['request'].user,
                        **validated_data,
                    )
                    if proof:
                        expense.payment_proof = proof
                        expense.save(update_fields=['payment_proof', 'updated_at'])
                    return expense
            except IntegrityError:
                continue
        raise serializers.ValidationError({
            'voucher_number': 'Could not assign a voucher number.',
        })


class ManualIncomeSerializer(serializers.ModelSerializer):
    """Staff-entered income voucher."""
    category_label = serializers.CharField(source='get_category_display', read_only=True)
    share_partner_label = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    payment_proof = PaymentProofField(required=False, allow_null=True)
    clear_payment_proof = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = ManualIncome
        fields = [
            'id', 'voucher_number', 'income_date', 'category', 'category_label',
            'share_partner', 'share_partner_label', 'description', 'comments',
            'amount', 'payment_proof', 'clear_payment_proof',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'voucher_number', 'created_by', 'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'share_partner': {'allow_blank': True, 'required': False},
            'description': {'allow_blank': True, 'required': False},
            'comments': {'allow_blank': True, 'required': False},
        }

    def get_share_partner_label(self, obj):
        return obj.get_share_partner_display() if obj.share_partner else ''

    def get_created_by_name(self, obj):
        user = getattr(obj, 'created_by', None)
        return user.full_name if user else None

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Amount must be greater than zero.')
        return value

    def validate(self, attrs):
        # Manual income is share contributions only — product sales come from orders.
        attrs['category'] = ManualIncome.CATEGORY_SHARE
        partner = attrs.get(
            'share_partner',
            getattr(self.instance, 'share_partner', '') if self.instance else '',
        )
        description = attrs.get(
            'description',
            getattr(self.instance, 'description', '') if self.instance else '',
        )
        if not partner:
            raise serializers.ValidationError({
                'share_partner': 'Select a share partner for Share Amount.',
            })
        if not (description or '').strip():
            partner_label = dict(ManualIncome.SHARE_PARTNER_CHOICES).get(partner, partner)
            attrs['description'] = f'Share — {partner_label}'
        return attrs

    def create(self, validated_data):
        validated_data.pop('clear_payment_proof', False)
        proof = validated_data.pop('payment_proof', None)
        income_date = validated_data['income_date']
        for _attempt in range(5):
            try:
                with transaction.atomic():
                    income = ManualIncome.objects.create(
                        voucher_number=next_income_voucher_number(income_date),
                        created_by=self.context['request'].user,
                        **validated_data,
                    )
                    if proof:
                        income.payment_proof = proof
                        income.save(update_fields=['payment_proof', 'updated_at'])
                    return income
            except IntegrityError:
                continue
        raise serializers.ValidationError({
            'voucher_number': 'Could not assign a voucher number.',
        })

    def update(self, instance, validated_data):
        clear_proof = bool(validated_data.pop('clear_payment_proof', False))
        proof = validated_data.pop('payment_proof', serializers.empty)
        instance = super().update(instance, validated_data)
        if proof is not serializers.empty or clear_proof:
            _apply_payment_proof(instance, proof, clear=clear_proof)
        return instance
