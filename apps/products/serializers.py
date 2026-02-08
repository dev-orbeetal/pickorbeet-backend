"""
Serializers for products app.
"""
from rest_framework import serializers
from .models import Category, SubCategory, Product, ProductImage, ProductVariant, ContactMessage


class ProductImageSerializer(serializers.ModelSerializer):
    """Serializer for product images."""

    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'is_primary', 'display_order']


class ProductVariantSerializer(serializers.ModelSerializer):
    """Serializer for product variants."""
    effective_price = serializers.ReadOnlyField()

    class Meta:
        model = ProductVariant
        fields = ['id', 'sku', 'barcode', 'size', 'color', 'price', 
                  'stock_quantity', 'low_stock_threshold', 'is_active', 'effective_price']


class SubCategorySerializer(serializers.ModelSerializer):
    """Serializer for subcategories."""
    product_count = serializers.ReadOnlyField()

    class Meta:
        model = SubCategory
        fields = ['id', 'category', 'name', 'slug', 'description', 'image', 
                  'is_active', 'display_order', 'product_count']
        read_only_fields = ['slug']


class SubCategoryListSerializer(serializers.ModelSerializer):
    """Minimal serializer for subcategory lists."""

    class Meta:
        model = SubCategory
        fields = ['id', 'name', 'slug', 'image']


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for categories with subcategories."""
    subcategories = SubCategoryListSerializer(many=True, read_only=True)
    product_count = serializers.ReadOnlyField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'tagline', 'image', 'banner_image',
                  'is_active', 'is_featured', 'featured_order', 'display_order', 
                  'subcategories', 'product_count']
        read_only_fields = ['slug']


class CategoryListSerializer(serializers.ModelSerializer):
    """Minimal serializer for category lists."""

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'tagline', 'image', 'banner_image', 'is_featured', 'featured_order']


class ProductListSerializer(serializers.ModelSerializer):
    """Serializer for product lists (minimal data)."""
    category_name = serializers.CharField(source='category.name', read_only=True)
    subcategory_name = serializers.CharField(source='subcategory.name', read_only=True)
    primary_image = serializers.ReadOnlyField()
    discount_percentage = serializers.ReadOnlyField()
    is_low_stock = serializers.ReadOnlyField()
    is_out_of_stock = serializers.ReadOnlyField()
    variants = ProductVariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'sku', 'barcode', 'category', 'category_name', 
                  'subcategory', 'subcategory_name', 'price', 'compare_price',
                  'primary_image', 'discount_percentage', 'stock_quantity',
                  'low_stock_threshold',
                  'is_low_stock', 'is_out_of_stock', 'is_featured', 'is_active',
                  'variants']


class ProductDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single product view."""
    category = CategoryListSerializer(read_only=True)
    subcategory = SubCategoryListSerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    primary_image = serializers.ReadOnlyField()
    discount_percentage = serializers.ReadOnlyField()
    is_low_stock = serializers.ReadOnlyField()
    is_out_of_stock = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'sku', 'barcode', 'barcode_image',
                  'category', 'subcategory', 'description', 'short_description',
                  'price', 'compare_price', 'size', 'color', 'material',
                  'stock_quantity', 'is_low_stock', 'is_out_of_stock',
                  'discount_percentage', 'is_active', 'is_featured',
                  'primary_image', 'images', 'variants', 'created_at', 'updated_at']


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating products."""

    class Meta:
        model = Product
        fields = ['name', 'sku', 'barcode', 'category', 'subcategory',
                  'description', 'short_description', 'price', 'compare_price',
                  'cost_price', 'size', 'color', 'material', 'stock_quantity',
                  'low_stock_threshold', 'is_active', 'is_featured']


class BarcodeProductSerializer(serializers.ModelSerializer):
    """Serializer for barcode scan response."""
    primary_image = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'sku', 'barcode', 'price', 'stock_quantity', 'primary_image']


class ProductStockUpdateSerializer(serializers.Serializer):
    """Serializer for stock updates."""
    quantity = serializers.IntegerField()
    operation = serializers.ChoiceField(choices=['add', 'subtract', 'set'])

    def validate_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Quantity cannot be negative.")
        return value


class ContactMessageSubmitSerializer(serializers.ModelSerializer):
    """Serializer for public contact form submission."""

    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'phone', 'subject', 'message']


class ContactMessageSerializer(serializers.ModelSerializer):
    """Serializer for admin contact message management."""

    class Meta:
        model = ContactMessage
        fields = ['id', 'name', 'email', 'phone', 'subject', 'message',
                  'status', 'admin_notes', 'created_at', 'updated_at']
        read_only_fields = ['id', 'name', 'email', 'phone', 'subject', 'message', 'created_at', 'updated_at']
