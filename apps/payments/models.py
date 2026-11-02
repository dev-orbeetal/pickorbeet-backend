"""
Payment models for Pickorbeet E-commerce.
"""
from django.db import models
from django.conf import settings
import uuid


def expense_payment_proof_path(instance, filename):
    return f'finance/expenses/{instance.id}/{filename}'


def income_payment_proof_path(instance, filename):
    return f'finance/income/{instance.id}/{filename}'


class Payment(models.Model):
    """Payment transaction model."""
    
    PAYMENT_METHOD_CHOICES = [
        ('sslcommerz', 'SSLCommerz'),
        ('cash', 'Cash'),
        ('card', 'Card (POS)'),
        ('mobile_banking', 'Mobile Banking'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='payments')
    
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='BDT')
    
    # SSLCommerz specific fields
    session_key = models.CharField(max_length=255, blank=True, null=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    val_id = models.CharField(max_length=100, blank=True, null=True)
    bank_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    card_type = models.CharField(max_length=50, blank=True, null=True)
    card_brand = models.CharField(max_length=50, blank=True, null=True)
    
    # Response data
    gateway_response = models.JSONField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.id} - {self.order.order_number}"


class Refund(models.Model):
    """Refund model for order refunds."""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('processed', 'Processed'),
        ('rejected', 'Rejected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='refunds')
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    refund_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='refund_requests'
    )
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_refunds'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Refund'
        verbose_name_plural = 'Refunds'
        ordering = ['-created_at']

    def __str__(self):
        return f"Refund {self.id} - {self.payment.order.order_number}"


class PurchaseReceipt(models.Model):
    """Multi-product purchase that posts stock and one Product Buying expense."""

    STATUS_POSTED = 'posted'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_POSTED, 'Posted'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]
    LOCATION_WAREHOUSE = 'warehouse'
    LOCATION_DEALER = 'dealer'
    LOCATION_CHOICES = [
        (LOCATION_WAREHOUSE, 'Warehouse Stock'),
        (LOCATION_DEALER, 'Dealer Stock'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('mobile_banking', 'Mobile Banking'),
    ]
    DISCOUNT_NONE = 'none'
    DISCOUNT_FIXED = 'fixed'
    DISCOUNT_PERCENT = 'percent'
    ADDITIONAL_DISCOUNT_TYPE_CHOICES = [
        (DISCOUNT_NONE, 'None'),
        (DISCOUNT_FIXED, 'Fixed amount'),
        (DISCOUNT_PERCENT, 'Percentage'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt_number = models.CharField(max_length=24, unique=True)
    purchase_date = models.DateField()
    payee = models.CharField(max_length=200, help_text='Dealer / seller name.')
    invoice_number = models.CharField(max_length=100, blank=True, default='')
    comments = models.TextField(blank=True, default='')
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True, default='',
    )
    stock_location = models.CharField(
        max_length=20, choices=LOCATION_CHOICES, default=LOCATION_WAREHOUSE,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_POSTED)
    total_quantity = models.PositiveIntegerField(default=0)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_discount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Sum of per-line discounts.',
    )
    additional_discount_type = models.CharField(
        max_length=16, choices=ADDITIONAL_DISCOUNT_TYPE_CHOICES, default=DISCOUNT_NONE,
    )
    additional_discount_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    additional_discount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Receipt-level discount applied after line discounts.',
    )
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_receipts_recorded',
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Purchase Receipt'
        verbose_name_plural = 'Purchase Receipts'
        ordering = ['-purchase_date', '-created_at']

    def __str__(self):
        return self.receipt_number


class PurchaseReceiptLine(models.Model):
    """One product row on a purchase receipt."""

    DISCOUNT_NONE = 'none'
    DISCOUNT_FIXED = 'fixed'
    DISCOUNT_PERCENT = 'percent'
    DISCOUNT_TYPE_CHOICES = [
        (DISCOUNT_NONE, 'None'),
        (DISCOUNT_FIXED, 'Fixed amount'),
        (DISCOUNT_PERCENT, 'Percentage'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt = models.ForeignKey(
        PurchaseReceipt, on_delete=models.CASCADE, related_name='lines',
    )
    product = models.ForeignKey(
        'products.Product', on_delete=models.PROTECT, related_name='purchase_receipt_lines',
    )
    variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='purchase_receipt_lines',
    )
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    discount_type = models.CharField(
        max_length=16, choices=DISCOUNT_TYPE_CHOICES, default=DISCOUNT_NONE,
    )
    discount_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    effective_unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    stock_movement = models.OneToOneField(
        'reports.StockMovement',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_receipt_line',
    )
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Purchase Receipt Line'
        verbose_name_plural = 'Purchase Receipt Lines'
        ordering = ['sort_order', 'created_at']

    def __str__(self):
        return f'{self.receipt.receipt_number} · {self.product.name}'


class Expense(models.Model):
    """A business expense voucher.

    Purchase vouchers are created from stock purchases and linked to that
    movement. Product Buying receipts link via purchase_receipt instead.
    Other vouchers are entered by staff and are not copied from sales.
    """

    CATEGORY_CHOICES = [
        ('inventory_purchase', 'Inventory Purchase'),
        ('product_buying', 'Product Buying'),
        ('packaging', 'Packaging'),
        ('transportation', 'Transportation'),
        ('others', 'Others'),
        # Legacy categories kept for existing rows.
        ('shipping', 'Shipping & Delivery'),
        ('marketing', 'Marketing & Ads'),
        ('utilities', 'Utilities'),
        ('rent', 'Rent'),
        ('salaries', 'Salaries'),
        ('software', 'Software & Tools'),
        ('miscellaneous', 'Miscellaneous'),
    ]
    MANUAL_CATEGORIES = {'packaging', 'transportation', 'others'}
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('mobile_banking', 'Mobile Banking'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    voucher_number = models.CharField(max_length=24, unique=True)
    expense_date = models.DateField()
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES)
    description = models.TextField()
    comments = models.TextField(blank=True, default='')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(null=True, blank=True)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    stock_movement = models.OneToOneField(
        'reports.StockMovement',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expense',
    )
    purchase_receipt = models.OneToOneField(
        PurchaseReceipt,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expense',
    )
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True, default=''
    )
    payee = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text='Dealer/seller name. Required for Product Buying.',
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses',
    )
    payment_proof = models.FileField(
        upload_to=expense_payment_proof_path,
        blank=True,
        null=True,
        help_text='Optional image or PDF proving the payment.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='expenses_recorded',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Expense'
        verbose_name_plural = 'Expenses'
        ordering = ['-expense_date', '-created_at']

    def __str__(self):
        return self.voucher_number

    @property
    def is_stock_linked(self):
        return bool(self.stock_movement_id or self.purchase_receipt_id)


class ManualIncome(models.Model):
    """Staff-entered income that is not an order payment."""

    CATEGORY_SHARE = 'share'
    CATEGORY_CHOICES = [
        (CATEGORY_SHARE, 'Share Amount'),
        # Legacy rows may still store "others"; new entries must use share.
        ('others', 'Others (legacy)'),
    ]
    SHARE_PARTNER_CHOICES = [
        ('orbeetal', 'Orbeetal'),
        ('rakib', 'Rakib'),
        ('tasdiq', 'Tasdiq'),
        ('mayeen', 'Mayeen'),
        ('nahiyan', 'Nahiyan'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    voucher_number = models.CharField(max_length=24, unique=True)
    income_date = models.DateField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_SHARE)
    share_partner = models.CharField(
        max_length=20, choices=SHARE_PARTNER_CHOICES, blank=True, default='',
    )
    description = models.TextField()
    comments = models.TextField(blank=True, default='')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_proof = models.FileField(
        upload_to=income_payment_proof_path,
        blank=True,
        null=True,
        help_text='Optional image or PDF proving the payment.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='manual_incomes_recorded',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Manual Income'
        verbose_name_plural = 'Manual Incomes'
        ordering = ['-income_date', '-created_at']

    def __str__(self):
        return self.voucher_number
