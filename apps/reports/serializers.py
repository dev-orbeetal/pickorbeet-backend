"""
Serializers for reports app.
"""
from rest_framework import serializers
from .models import DailySalesReport, StockReport, StockMovement


class DailySalesReportSerializer(serializers.ModelSerializer):
    """Serializer for daily sales report."""
    generated_by_name = serializers.CharField(source='generated_by.full_name', read_only=True)

    class Meta:
        model = DailySalesReport
        fields = ['id', 'date', 'total_orders', 'online_orders', 'in_shop_orders',
                  'gross_revenue', 'delivery_charges', 'discounts', 'net_revenue',
                  'total_items_sold', 'cash_payments', 'card_payments', 'online_payments',
                  'generated_at', 'generated_by', 'generated_by_name']


class StockReportSerializer(serializers.ModelSerializer):
    """Serializer for stock report."""
    generated_by_name = serializers.CharField(source='generated_by.full_name', read_only=True)

    class Meta:
        model = StockReport
        fields = ['id', 'date', 'total_products', 'in_stock_products',
                  'low_stock_products', 'out_of_stock_products',
                  'total_stock_value', 'total_units',
                  'generated_at', 'generated_by', 'generated_by_name']


class StockMovementSerializer(serializers.ModelSerializer):
    """Serializer for stock movements."""
    product_name = serializers.CharField(source='product.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)

    class Meta:
        model = StockMovement
        fields = ['id', 'product', 'product_name', 'variant', 'movement_type',
                  'reason', 'quantity', 'previous_stock', 'new_stock',
                  'reference_order', 'note', 'created_by', 'created_by_name', 'created_at']


class DateRangeSerializer(serializers.Serializer):
    """Serializer for date range queries."""
    start_date = serializers.DateField()
    end_date = serializers.DateField()

    def validate(self, attrs):
        if attrs['start_date'] > attrs['end_date']:
            raise serializers.ValidationError("start_date must be before end_date")
        return attrs


class SalesSummarySerializer(serializers.Serializer):
    """Serializer for sales summary response."""
    total_orders = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_items_sold = serializers.IntegerField()
    average_order_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    online_orders = serializers.IntegerField()
    in_shop_orders = serializers.IntegerField()


class TopProductSerializer(serializers.Serializer):
    """Serializer for top selling products."""
    product_id = serializers.UUIDField()
    product_name = serializers.CharField()
    total_sold = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)


class CategorySalesSerializer(serializers.Serializer):
    """Serializer for category-wise sales."""
    category_id = serializers.UUIDField()
    category_name = serializers.CharField()
    total_orders = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
