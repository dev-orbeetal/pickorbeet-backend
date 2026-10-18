"""
Report models for Pickorbeet E-commerce.
"""
from django.db import models
from django.conf import settings
import uuid


class DailySalesReport(models.Model):
    """Daily sales summary report."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField(unique=True)
    
    # Order counts
    total_orders = models.PositiveIntegerField(default=0)
    online_orders = models.PositiveIntegerField(default=0)
    in_shop_orders = models.PositiveIntegerField(default=0)
    
    # Revenue
    gross_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    delivery_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discounts = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Products
    total_items_sold = models.PositiveIntegerField(default=0)
    
    # Payment breakdown
    cash_payments = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    card_payments = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    online_payments = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Generated info
    generated_at = models.DateTimeField(auto_now=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'Daily Sales Report'
        verbose_name_plural = 'Daily Sales Reports'
        ordering = ['-date']

    def __str__(self):
        return f"Sales Report - {self.date}"


class StockReport(models.Model):
    """Stock snapshot report."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField()
    
    total_products = models.PositiveIntegerField(default=0)
    in_stock_products = models.PositiveIntegerField(default=0)
    low_stock_products = models.PositiveIntegerField(default=0)
    out_of_stock_products = models.PositiveIntegerField(default=0)
    
    total_stock_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_units = models.PositiveIntegerField(default=0)
    
    # Generated info
    generated_at = models.DateTimeField(auto_now=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'Stock Report'
        verbose_name_plural = 'Stock Reports'
        ordering = ['-date']

    def __str__(self):
        return f"Stock Report - {self.date}"


class StockMovement(models.Model):
    """Track stock movements (in/out)."""
    
    MOVEMENT_TYPE_CHOICES = [
        ('in', 'Stock In'),
        ('out', 'Stock Out'),
        ('adjustment', 'Adjustment'),
        ('return', 'Return'),
    ]
    
    REASON_CHOICES = [
        ('purchase', 'Purchase/Restock'),
        ('sale', 'Sale'),
        ('return', 'Customer Return'),
        ('damaged', 'Damaged'),
        ('lost', 'Lost/Missing'),
        ('adjustment', 'Manual Adjustment'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='stock_movements')
    variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='stock_movements'
    )
    
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPE_CHOICES)
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    quantity = models.IntegerField()  # Positive for in, negative for out
    
    previous_stock = models.PositiveIntegerField()
    new_stock = models.PositiveIntegerField()
    
    reference_order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    note = models.TextField(blank=True, null=True)
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Stock Movement'
        verbose_name_plural = 'Stock Movements'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product.name} - {self.movement_type} ({self.quantity})"
