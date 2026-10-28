"""
Serializers for products app.
"""
from django.db.models import Avg, Count
from rest_framework import serializers
from .models import (
    Category, SubCategory, Product, ProductImage, ProductVariant, ProductSpecification,
    ProductReview, ContactMessage, HomepageBanner,
)


class RelativeImageField(serializers.ImageField):
    """Keep image paths on this site (/media/...) instead of another host."""

    def to_representation(self, value):
        if not value:
            return None
        try:
            return value.url
        except AttributeError:
            return None


class ProductImageSerializer(serializers.ModelSerializer):
    """Serializer for product images."""
    image = RelativeImageField()

    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'is_primary', 'display_order']


class ProductSpecificationSerializer(serializers.ModelSerializer):
    """Name/value row. Blank pairs are dropped by the product write serializer."""
    name = serializers.CharField(max_length=80, allow_blank=True, trim_whitespace=True)
    value = serializers.CharField(max_length=255, allow_blank=True, trim_whitespace=True)

    class Meta:
        model = ProductSpecification
        fields = ['id', 'name', 'value', 'sort_order']
        read_only_fields = ['id', 'sort_order']


def review_stats(product):
    """Average and count from the catalog annotation, or one query when it is absent."""
    cached = getattr(product, '_catalog_review_stats', None)
    if cached is not None:
        return cached
    data = product.__dict__
    if 'rating_average' in data or 'review_count' in data:
        average = data.get('rating_average')
        count = data.get('review_count') or 0
    else:
        row = product.reviews.aggregate(average=Avg('rating'), count=Count('id'))
        average = row['average']
        count = row['count']
    stats = {
        'rating_average': None if average is None else round(float(average), 1),
        'review_count': int(count or 0),
    }
    product._catalog_review_stats = stats
    return stats


class ProductVariantSerializer(serializers.ModelSerializer):
    """Serializer for product variants."""
    effective_price = serializers.ReadOnlyField()
    options = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = ['id', 'sku', 'barcode', 'size', 'color', 'price',
                  'stock_quantity', 'low_stock_threshold', 'is_active', 'effective_price',
                  'options']

    def get_options(self, obj):
        from apps.products.variants import variant_options
        return variant_options(obj)


class SubCategorySerializer(serializers.ModelSerializer):
    """Serializer for subcategories."""
    image = RelativeImageField(required=False, allow_null=True)
    product_count = serializers.ReadOnlyField()

    class Meta:
        model = SubCategory
        fields = ['id', 'category', 'name', 'slug', 'description', 'image', 
                  'is_active', 'display_order', 'product_count']
        read_only_fields = ['slug']


class SubCategoryListSerializer(serializers.ModelSerializer):
    """Minimal serializer for subcategory lists."""
    image = RelativeImageField(required=False, allow_null=True)

    class Meta:
        model = SubCategory
        fields = ['id', 'name', 'slug', 'description', 'image', 'display_order']


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for categories with subcategories."""
    image = RelativeImageField(required=False, allow_null=True)
    banner_image = RelativeImageField(required=False, allow_null=True)
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
    image = RelativeImageField(required=False, allow_null=True)
    banner_image = RelativeImageField(required=False, allow_null=True)

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
    specifications = ProductSpecificationSerializer(many=True, read_only=True)
    rating_average = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'sku', 'barcode', 'category', 'category_name', 
                  'subcategory', 'subcategory_name', 'short_description', 'price', 'compare_price',
                  'primary_image', 'discount_percentage', 'stock_quantity',
                  'low_stock_threshold',
                  'is_low_stock', 'is_out_of_stock', 'is_featured', 'is_active',
                  'is_official', 'warranty_period',
                  'variants', 'specifications', 'rating_average', 'review_count']

    def get_rating_average(self, obj):
        return review_stats(obj)['rating_average']

    def get_review_count(self, obj):
        return review_stats(obj)['review_count']


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
    specifications = ProductSpecificationSerializer(many=True, read_only=True)
    option_groups = serializers.SerializerMethodField()
    rating_average = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'sku', 'barcode', 'barcode_image',
                  'category', 'subcategory', 'description', 'short_description',
                  'price', 'compare_price', 'size', 'color', 'material',
                  'stock_quantity', 'is_low_stock', 'is_out_of_stock',
                  'discount_percentage', 'is_active', 'is_featured',
                  'is_official', 'warranty_period',
                  'primary_image', 'images', 'variants', 'specifications',
                  'option_groups',
                  'rating_average', 'review_count', 'created_at', 'updated_at']

    def get_option_groups(self, obj):
        from apps.products.variants import option_groups
        return option_groups(obj)

    def get_rating_average(self, obj):
        return review_stats(obj)['rating_average']

    def get_review_count(self, obj):
        return review_stats(obj)['review_count']


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating products."""
    specifications = ProductSpecificationSerializer(many=True, required=False)

    class Meta:
        model = Product
        fields = ['id', 'name', 'sku', 'barcode', 'category', 'subcategory',
                  'description', 'short_description', 'price', 'compare_price',
                  'cost_price', 'size', 'color', 'material', 'stock_quantity',
                  'low_stock_threshold', 'is_active', 'is_featured',
                  'is_official', 'warranty_period', 'specifications']

    def validate_sku(self, value):
        """Convert empty string to None to avoid unique constraint violation."""
        return value.strip() if value and value.strip() else None

    def validate_barcode(self, value):
        """Convert empty string to None to avoid unique constraint violation."""
        return value.strip() if value and value.strip() else None

    def validate_warranty_period(self, value):
        return (value or '').strip()

    def validate_specifications(self, value):
        cleaned = []
        for row in value:
            name = (row.get('name') or '').strip()
            spec_value = (row.get('value') or '').strip()
            if not name and not spec_value:
                continue
            if not name or not spec_value:
                raise serializers.ValidationError('Each specification needs a name and a value.')
            cleaned.append({'name': name, 'value': spec_value})
        return cleaned

    def _replace_specifications(self, product, rows):
        product.specifications.all().delete()
        for index, row in enumerate(rows):
            ProductSpecification.objects.create(
                product=product,
                name=row['name'],
                value=row['value'],
                sort_order=index,
            )

    def create(self, validated_data):
        rows = validated_data.pop('specifications', None)
        product = super().create(validated_data)
        if rows is not None:
            self._replace_specifications(product, rows)
        return product

    def update(self, instance, validated_data):
        rows = validated_data.pop('specifications', None)
        product = super().update(instance, validated_data)
        if rows is not None:
            self._replace_specifications(product, rows)
        return product


class ProductReviewSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()

    class Meta:
        model = ProductReview
        fields = ['id', 'author', 'rating', 'comment', 'created_at', 'updated_at']

    def get_author(self, obj):
        name = f'{obj.user.first_name} {obj.user.last_name}'.strip()
        return name or 'Customer'


class ProductReviewWriteSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(max_length=2000, trim_whitespace=True)

    def validate_comment(self, value):
        if not value:
            raise serializers.ValidationError('Write a short comment with your rating.')
        return value


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


class HomepageBannerSerializer(serializers.ModelSerializer):
    """Public serializer for uploaded homepage banners."""
    image = RelativeImageField()

    class Meta:
        model = HomepageBanner
        fields = ['id', 'image', 'title', 'subtitle', 'button_label', 'link', 'placement', 'display_order', 'is_active']


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
