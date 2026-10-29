"""
Serializers for products app.
"""
from django.db import transaction
from rest_framework import serializers
from .models import Category, SubCategory, Product, ProductImage, ProductVariant, ContactMessage, HomepageBanner


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


class ProductVariantSerializer(serializers.ModelSerializer):
    """Serializer for product variants."""
    effective_price = serializers.ReadOnlyField()

    class Meta:
        model = ProductVariant
        fields = ['id', 'sku', 'barcode', 'size', 'color', 'price', 
                  'stock_quantity', 'low_stock_threshold', 'is_active', 'effective_price']

    def create(self, validated_data):
        from apps.products.costing import StockError, record_purchase

        stock = int(validated_data.pop('stock_quantity', 0) or 0)
        product = validated_data['product']
        if stock > 0 and not (product.cost_price and product.cost_price > 0):
            raise serializers.ValidationError({
                'stock_quantity': (
                    'Set a cost price on the product before adding opening stock. '
                    'Later purchases are recorded from Inventory.'
                ),
            })
        validated_data['stock_quantity'] = 0
        with transaction.atomic():
            variant = super().create(validated_data)
            if stock > 0:
                try:
                    record_purchase(
                        product=product,
                        variant=variant,
                        quantity=stock,
                        unit_cost=product.cost_price,
                        user=self.context['request'].user,
                        note='Opening variant stock',
                    )
                except StockError as exc:
                    raise serializers.ValidationError({'stock_quantity': exc.message})
                variant.refresh_from_db()
            return variant

    def update(self, instance, validated_data):
        # Stock changes go through Inventory so every purchase has one voucher.
        validated_data.pop('stock_quantity', None)
        return super().update(instance, validated_data)


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

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'sku', 'barcode', 'category', 'category_name', 
                  'subcategory', 'subcategory_name', 'short_description', 'price', 'compare_price',
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


class AdminProductListSerializer(ProductListSerializer):
    """Admin list payload. Adds internal supply fields the public list omits."""
    supplied_by_name = serializers.SerializerMethodField()

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + [
            'supply_type', 'supplied_by', 'supplied_by_name',
        ]

    def get_supplied_by_name(self, obj):
        seller = getattr(obj, 'supplied_by', None)
        return seller.full_name if seller else None


class AdminProductDetailSerializer(ProductDetailSerializer):
    """Admin detail payload. Adds internal supply fields the public detail omits."""
    supplied_by_name = serializers.SerializerMethodField()

    class Meta(ProductDetailSerializer.Meta):
        fields = ProductDetailSerializer.Meta.fields + [
            'supply_type', 'supplied_by', 'supplied_by_name', 'cost_price',
            'low_stock_threshold',
        ]

    def get_supplied_by_name(self, obj):
        seller = getattr(obj, 'supplied_by', None)
        return seller.full_name if seller else None


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating products."""

    class Meta:
        model = Product
        fields = ['id', 'slug', 'name', 'sku', 'barcode', 'category', 'subcategory',
                  'description', 'short_description', 'price', 'compare_price',
                  'cost_price', 'size', 'color', 'material', 'stock_quantity',
                  'low_stock_threshold', 'is_active', 'is_featured',
                  'supply_type', 'supplied_by']
        read_only_fields = ['id', 'slug']

    def validate_sku(self, value):
        """Convert empty string to None to avoid unique constraint violation."""
        return value.strip() if value and value.strip() else None

    def validate_barcode(self, value):
        """Convert empty string to None to avoid unique constraint violation."""
        return value.strip() if value and value.strip() else None

    def validate(self, attrs):
        supply_type = attrs.get(
            'supply_type',
            getattr(self.instance, 'supply_type', Product.SUPPLY_AVAILABLE),
        )
        if 'supplied_by' in attrs:
            seller = attrs.get('supplied_by')
        elif self.instance is not None:
            seller = self.instance.supplied_by
        else:
            seller = None

        if supply_type == Product.SUPPLY_AVAILABLE:
            attrs['supplied_by'] = None
        else:
            if seller is None:
                raise serializers.ValidationError({
                    'supplied_by': 'Select the seller who provides this product.',
                })
            if seller.role != 'seller':
                raise serializers.ValidationError({
                    'supplied_by': 'Seller-provided products must be linked to a seller account.',
                })
            attrs['supplied_by'] = seller
        if self.instance is None:
            stock = attrs.get('stock_quantity') or 0
            cost = attrs.get('cost_price')
            if stock > 0 and (cost is None or cost <= 0):
                raise serializers.ValidationError({
                    'cost_price': 'Enter a cost price to record opening stock as a purchase.',
                })
        return attrs

    def create(self, validated_data):
        from apps.products.costing import StockError, record_purchase

        stock = int(validated_data.pop('stock_quantity', 0) or 0)
        cost = validated_data.get('cost_price')
        validated_data['stock_quantity'] = 0
        with transaction.atomic():
            product = super().create(validated_data)
            if stock > 0:
                try:
                    record_purchase(
                        product=product,
                        quantity=stock,
                        unit_cost=cost,
                        user=self.context['request'].user,
                        note='Opening stock',
                    )
                except StockError as exc:
                    raise serializers.ValidationError({'cost_price': exc.message})
                product.refresh_from_db()
            return product

    def update(self, instance, validated_data):
        # Stock and average cost are maintained by purchases, sales, and inventory adjustments.
        validated_data.pop('stock_quantity', None)
        validated_data.pop('cost_price', None)
        return super().update(instance, validated_data)


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
    reason = serializers.ChoiceField(
        choices=['purchase', 'return', 'damaged', 'lost', 'adjustment'],
        required=False,
        default='adjustment',
    )
    note = serializers.CharField(required=False, allow_blank=True, default='')
    unit_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    payment_method = serializers.ChoiceField(
        choices=['', 'cash', 'card', 'mobile_banking'],
        required=False,
        allow_blank=True,
        default='',
    )
    payee = serializers.CharField(required=False, allow_blank=True, default='')

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
