"""
Serializers for products app.
"""
from django.db import transaction
from django.db.models import Avg, Count
from rest_framework import serializers
from .models import (
    Category, SubCategory, Product, ProductImage, ProductVideo, ProductVariant, ProductSpecification,
    ProductReview, ProductReviewImage, ContactMessage, HomepageBanner, HomepageSection,
    HomepageSectionProduct,
)
from .youtube import extract_youtube_id


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
    """Serializer for product images. variant=null means shared across all variants."""
    image = RelativeImageField()
    variant = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'is_primary', 'display_order', 'variant']

    def validate_variant(self, variant):
        if variant is None:
            return variant
        product = None
        if self.instance is not None:
            product = self.instance.product
        elif self.context.get('product') is not None:
            product = self.context['product']
        if product is not None and variant.product_id != product.id:
            raise serializers.ValidationError('Variant must belong to this product.')
        return variant


class ProductVideoSerializer(serializers.ModelSerializer):
    """YouTube gallery item. variant=null means shared across all variants."""
    variant = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.all(),
        required=False,
        allow_null=True,
    )
    youtube_id = serializers.CharField(read_only=True)

    class Meta:
        model = ProductVideo
        fields = [
            'id', 'youtube_url', 'youtube_id', 'title',
            'is_primary', 'display_order', 'variant',
        ]

    def validate_youtube_url(self, value):
        video_id = extract_youtube_id(value)
        if not video_id:
            raise serializers.ValidationError(
                'Enter a valid YouTube link (watch, youtu.be, shorts, or embed).'
            )
        return value.strip()

    def validate_variant(self, variant):
        if variant is None:
            return variant
        product = None
        if self.instance is not None:
            product = self.instance.product
        elif self.context.get('product') is not None:
            product = self.context['product']
        if product is not None and variant.product_id != product.id:
            raise serializers.ValidationError('Variant must belong to this product.')
        return variant


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
                  'stock_quantity', 'warehouse_stock', 'dealer_stock',
                  'dealer_available',
                  'low_stock_threshold', 'is_active', 'effective_price',
                  'options']
        read_only_fields = ['warehouse_stock', 'dealer_stock']

    def get_options(self, obj):
        from apps.products.variants import variant_options
        return variant_options(obj)

    def create(self, validated_data):
        # Stock is added only via Finance purchase receipts.
        validated_data['stock_quantity'] = 0
        validated_data['warehouse_stock'] = 0
        validated_data['dealer_stock'] = 0
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Stock changes go through Inventory so every purchase has one voucher.
        validated_data.pop('stock_quantity', None)
        validated_data.pop('warehouse_stock', None)
        validated_data.pop('dealer_stock', None)
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


class AdminSubCategoryListSerializer(SubCategoryListSerializer):
    """Subcategory row for the admin catalog. Counts inactive products too."""
    product_count = serializers.SerializerMethodField()

    class Meta(SubCategoryListSerializer.Meta):
        fields = SubCategoryListSerializer.Meta.fields + ['category', 'is_active', 'product_count']

    def get_product_count(self, obj):
        count = getattr(obj, 'catalog_product_count', None)
        if count is None:
            count = obj.products.filter(category_id=obj.category_id).count()
        return count


class AdminCategorySerializer(CategorySerializer):
    """Category for the admin catalog.

    The shared ``product_count`` counts active products for the storefront. Here
    it counts every product, so it matches the rows admins see. A product counts
    once, through its category, however it is linked to a subcategory.
    """
    subcategories = AdminSubCategoryListSerializer(many=True, read_only=True)
    product_count = serializers.SerializerMethodField()
    direct_product_count = serializers.SerializerMethodField()

    class Meta(CategorySerializer.Meta):
        fields = CategorySerializer.Meta.fields + ['direct_product_count']

    def get_product_count(self, obj):
        count = getattr(obj, 'catalog_product_count', None)
        return obj.products.count() if count is None else count

    def get_direct_product_count(self, obj):
        subcategories = self.fields['subcategories'].child
        in_subcategories = sum(
            subcategories.get_product_count(subcategory)
            for subcategory in obj.subcategories.all()
        )
        return self.get_product_count(obj) - in_subcategories


class CategoryListSerializer(serializers.ModelSerializer):
    """Minimal serializer for category lists."""
    image = RelativeImageField(required=False, allow_null=True)
    banner_image = RelativeImageField(required=False, allow_null=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'tagline', 'image', 'banner_image', 'is_featured', 'featured_order']


class PublicProductVariantSerializer(ProductVariantSerializer):
    """Customer-facing variant: availability only, never stock counts."""
    availability = serializers.ReadOnlyField()

    class Meta(ProductVariantSerializer.Meta):
        fields = ['id', 'sku', 'barcode', 'size', 'color', 'price', 'availability',
                  'is_active', 'effective_price', 'options']


class ProductListSerializer(serializers.ModelSerializer):
    """Serializer for product lists (minimal data)."""
    category_name = serializers.CharField(source='category.name', read_only=True)
    subcategory_name = serializers.CharField(source='subcategory.name', read_only=True)
    primary_image = serializers.ReadOnlyField()
    gallery_images = serializers.SerializerMethodField()
    discount_percentage = serializers.ReadOnlyField()
    availability = serializers.ReadOnlyField()
    is_out_of_stock = serializers.SerializerMethodField()
    variants = PublicProductVariantSerializer(many=True, read_only=True)
    specifications = ProductSpecificationSerializer(many=True, read_only=True)
    rating_average = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'sku', 'barcode', 'category', 'category_name', 
                  'subcategory', 'subcategory_name', 'short_description', 'price', 'compare_price',
                  'primary_image', 'gallery_images', 'discount_percentage', 'availability',
                  'is_out_of_stock', 'is_featured', 'is_active',
                  'is_official', 'warranty_period',
                  'variants', 'specifications', 'rating_average', 'review_count']

    def get_is_out_of_stock(self, obj):
        return not obj.is_available

    def get_gallery_images(self, obj):
        """Up to six unique photo URLs for list/card autoplay (primary first)."""
        rows = sorted(
            obj.images.all(),
            key=lambda image: (0 if image.is_primary else 1, getattr(image, 'display_order', 0) or 0),
        )
        urls = []
        seen = set()
        for row in rows:
            try:
                url = row.image.url if row.image else None
            except (ValueError, AttributeError):
                url = None
            if not url or url in seen:
                continue
            seen.add(url)
            urls.append(url)
            if len(urls) >= 6:
                break
        if not urls:
            primary = obj.primary_image
            if primary:
                urls.append(primary)
        return urls

    def get_rating_average(self, obj):
        return review_stats(obj)['rating_average']

    def get_review_count(self, obj):
        return review_stats(obj)['review_count']


class ProductDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single product view."""
    category = CategoryListSerializer(read_only=True)
    subcategory = SubCategoryListSerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    videos = ProductVideoSerializer(many=True, read_only=True)
    variants = PublicProductVariantSerializer(many=True, read_only=True)
    primary_image = serializers.ReadOnlyField()
    discount_percentage = serializers.ReadOnlyField()
    availability = serializers.ReadOnlyField()
    is_out_of_stock = serializers.SerializerMethodField()
    specifications = ProductSpecificationSerializer(many=True, read_only=True)
    option_groups = serializers.SerializerMethodField()
    rating_average = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'sku', 'barcode', 'barcode_image',
                  'category', 'subcategory', 'description', 'short_description',
                  'price', 'compare_price', 'size', 'color', 'material',
                  'availability', 'is_out_of_stock',
                  'discount_percentage', 'is_active', 'is_featured',
                  'is_official', 'warranty_period',
                  'primary_image', 'images', 'videos', 'variants', 'specifications',
                  'option_groups',
                  'rating_average', 'review_count', 'created_at', 'updated_at']

    def get_is_out_of_stock(self, obj):
        return not obj.is_available

    def get_option_groups(self, obj):
        from apps.products.variants import public_option_groups
        return public_option_groups(obj)

    def get_rating_average(self, obj):
        return review_stats(obj)['rating_average']

    def get_review_count(self, obj):
        return review_stats(obj)['review_count']


class AdminProductListSerializer(ProductListSerializer):
    """Admin list payload. Adds stock and supply fields the public list omits."""
    supplied_by_name = serializers.SerializerMethodField()
    warehouse_stock = serializers.SerializerMethodField()
    dealer_stock = serializers.SerializerMethodField()
    is_low_stock = serializers.ReadOnlyField()
    is_out_of_stock = serializers.ReadOnlyField()
    variants = ProductVariantSerializer(many=True, read_only=True)

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + [
            'stock_quantity', 'low_stock_threshold', 'is_low_stock',
            'supply_type', 'supplied_by', 'supplied_by_name',
            'warehouse_stock', 'dealer_stock', 'dealer_available',
        ]

    def get_supplied_by_name(self, obj):
        seller = getattr(obj, 'supplied_by', None)
        return seller.full_name if seller else None

    def _variant_stock_totals(self, obj):
        variants = list(obj.variants.all()) if hasattr(obj, 'variants') else []
        if not variants:
            return None
        return {
            'warehouse': sum(int(v.warehouse_stock or 0) for v in variants),
            'dealer': sum(int(v.dealer_stock or 0) for v in variants),
        }

    def get_warehouse_stock(self, obj):
        totals = self._variant_stock_totals(obj)
        if totals is not None:
            return totals['warehouse']
        return int(obj.warehouse_stock or 0)

    def get_dealer_stock(self, obj):
        totals = self._variant_stock_totals(obj)
        if totals is not None:
            return totals['dealer']
        return int(obj.dealer_stock or 0)


class AdminProductDetailSerializer(ProductDetailSerializer):
    """Admin detail payload. Adds stock and supply fields the public detail omits."""
    supplied_by_name = serializers.SerializerMethodField()
    is_low_stock = serializers.ReadOnlyField()
    is_out_of_stock = serializers.ReadOnlyField()
    variants = ProductVariantSerializer(many=True, read_only=True)

    class Meta(ProductDetailSerializer.Meta):
        fields = ProductDetailSerializer.Meta.fields + [
            'stock_quantity', 'is_low_stock',
            'supply_type', 'supplied_by', 'supplied_by_name', 'cost_price',
            'low_stock_threshold', 'warehouse_stock', 'dealer_stock', 'dealer_available',
        ]

    def get_option_groups(self, obj):
        from apps.products.variants import option_groups
        return option_groups(obj)

    def get_supplied_by_name(self, obj):
        seller = getattr(obj, 'supplied_by', None)
        return seller.full_name if seller else None


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating products."""
    specifications = ProductSpecificationSerializer(many=True, required=False)

    class Meta:
        model = Product
        fields = ['id', 'slug', 'name', 'sku', 'barcode', 'category', 'subcategory',
                  'description', 'short_description', 'price', 'compare_price',
                  'cost_price', 'size', 'color', 'material', 'stock_quantity',
                  'dealer_available',
                  'low_stock_threshold', 'is_active', 'is_featured',
                  'supply_type', 'supplied_by',
                  'is_official', 'warranty_period', 'specifications']
        read_only_fields = ['id', 'slug']

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
        if 'category' in attrs or 'subcategory' in attrs:
            category = attrs.get('category', getattr(self.instance, 'category', None))
            subcategory = attrs.get('subcategory', getattr(self.instance, 'subcategory', None))
            if subcategory is not None and category is not None and subcategory.category_id != category.pk:
                raise serializers.ValidationError({
                    'subcategory': 'Choose a subcategory that belongs to the selected category.',
                })
        if self.instance is None:
            # Products created in admin are published to the storefront immediately.
            # Stock starts at 0 and is increased only via Finance purchase receipts.
            attrs['is_active'] = True
        return attrs

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
        # Ignore any client-sent quantity; stock is detected from purchasing only.
        validated_data.pop('stock_quantity', None)
        validated_data['stock_quantity'] = 0
        validated_data['warehouse_stock'] = 0
        validated_data['dealer_stock'] = 0
        validated_data['is_active'] = True
        with transaction.atomic():
            product = super().create(validated_data)
            if rows is not None:
                self._replace_specifications(product, rows)
            return product

    def update(self, instance, validated_data):
        # Stock and average cost are maintained by purchases, sales, and inventory adjustments.
        rows = validated_data.pop('specifications', None)
        validated_data.pop('stock_quantity', None)
        validated_data.pop('warehouse_stock', None)
        validated_data.pop('dealer_stock', None)
        validated_data.pop('cost_price', None)
        product = super().update(instance, validated_data)
        if rows is not None:
            self._replace_specifications(product, rows)
        return product


class ProductReviewImageSerializer(serializers.ModelSerializer):
    image = RelativeImageField()

    class Meta:
        model = ProductReviewImage
        fields = ['id', 'image', 'sort_order']


class ProductReviewSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    images = ProductReviewImageSerializer(many=True, read_only=True)

    class Meta:
        model = ProductReview
        fields = ['id', 'author', 'rating', 'comment', 'images', 'created_at', 'updated_at']

    def get_author(self, obj):
        name = f'{obj.user.first_name} {obj.user.last_name}'.strip()
        return name or 'Customer'


class ProductReviewWriteSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(max_length=2000, trim_whitespace=True)
    clear_images = serializers.BooleanField(required=False, default=False)

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
    location = serializers.ChoiceField(
        choices=['warehouse', 'dealer'],
        required=False,
        default='warehouse',
    )
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


class StockTransferSerializer(serializers.Serializer):
    """Move units between warehouse and dealer."""
    quantity = serializers.IntegerField(min_value=1)
    from_location = serializers.ChoiceField(choices=['warehouse', 'dealer'])
    to_location = serializers.ChoiceField(choices=['warehouse', 'dealer'])
    note = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        if attrs['from_location'] == attrs['to_location']:
            raise serializers.ValidationError('Choose two different locations for a transfer.')
        return attrs


class HomepageBannerSerializer(serializers.ModelSerializer):
    """Public serializer for uploaded homepage banners."""
    image = RelativeImageField()

    class Meta:
        model = HomepageBanner
        fields = ['id', 'image', 'title', 'subtitle', 'button_label', 'link', 'placement', 'display_order', 'is_active']


class HomepageSectionProductSerializer(serializers.ModelSerializer):
    """Product row inside an admin-managed homepage section."""
    id = serializers.UUIDField(source='product.id', read_only=True)
    name = serializers.CharField(source='product.name', read_only=True)
    sku = serializers.CharField(source='product.sku', read_only=True)
    price = serializers.DecimalField(
        source='product.price', max_digits=10, decimal_places=2, read_only=True
    )
    primary_image = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(source='product.is_active', read_only=True)

    class Meta:
        model = HomepageSectionProduct
        fields = ['id', 'name', 'sku', 'price', 'primary_image', 'is_active', 'display_order']

    def get_primary_image(self, obj):
        return obj.product.primary_image


class HomepageSectionSerializer(serializers.ModelSerializer):
    """Admin serializer for curated homepage product rows."""
    products = HomepageSectionProductSerializer(source='section_products', many=True, read_only=True)
    banner_image = RelativeImageField(required=False, allow_null=True)
    # CharField child: FormData often sends "" for an empty list; UUIDField rejects
    # that before validate_product_ids can normalize it.
    product_ids = serializers.ListField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        write_only=True,
        allow_empty=True,
    )
    clear_banner_image = serializers.BooleanField(required=False, write_only=True, default=False)

    class Meta:
        model = HomepageSection
        fields = [
            'id', 'key', 'section_type', 'title', 'subtitle', 'is_enabled',
            'display_order', 'item_limit', 'view_all_label', 'view_all_url',
            'product_source', 'banner_image', 'clear_banner_image', 'products', 'product_ids',
        ]
        read_only_fields = ['id', 'key', 'section_type', 'display_order']

    def validate_product_source(self, value):
        allowed = {'manual', 'latest', 'on_sale', 'featured'}
        if value not in allowed:
            raise serializers.ValidationError('Invalid product source.')
        return value

    def validate_item_limit(self, value):
        if value < 1 or value > 24:
            raise serializers.ValidationError('Item limit must be between 1 and 24.')
        return value

    def validate_product_ids(self, value):
        if not value:
            return []
        # Empty FormData sentinel or a JSON array string from older clients.
        if len(value) == 1 and isinstance(value[0], str):
            raw = value[0].strip()
            if not raw:
                return []
            if raw.startswith('['):
                import json
                try:
                    value = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise serializers.ValidationError('Invalid product_ids.') from exc

        cleaned = []
        for item in value:
            raw = str(item).strip() if item is not None else ''
            if not raw:
                continue
            try:
                cleaned.append(serializers.UUIDField().to_internal_value(raw))
            except serializers.ValidationError as exc:
                raise serializers.ValidationError('Must be a valid UUID.') from exc

        unique = list(dict.fromkeys(cleaned))
        found = set(
            Product.objects.filter(id__in=unique).values_list('id', flat=True)
        )
        missing = [str(product_id) for product_id in unique if product_id not in found]
        if missing:
            raise serializers.ValidationError(f'Unknown product ids: {", ".join(missing)}')
        return unique

    def update(self, instance, validated_data):
        product_ids = validated_data.pop('product_ids', serializers.empty)
        clear_banner = validated_data.pop('clear_banner_image', False)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if clear_banner and 'banner_image' not in validated_data:
            instance.banner_image = None
        instance.save()

        if product_ids is not serializers.empty:
            # Auto "latest" mode ignores curated picks — clear any leftovers.
            if instance.product_source == 'latest':
                product_ids = []
            instance.section_products.all().delete()
            HomepageSectionProduct.objects.bulk_create([
                HomepageSectionProduct(
                    section=instance,
                    product_id=product_id,
                    display_order=index,
                )
                for index, product_id in enumerate(product_ids)
            ])

        return instance


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
