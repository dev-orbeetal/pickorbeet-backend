"""
Views for products app.
"""
import re
import uuid
from decimal import Decimal

from rest_framework import generics, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.db import models
from django.db.models import Avg, Count, F, FloatField, IntegerField, OuterRef, Prefetch, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from .models import (
    Category, SubCategory, Product, ProductImage, ProductVariant, ProductReview,
    ContactMessage, HomepageBanner, with_catalog_stats,
)
from .serializers import (
    CategorySerializer, CategoryListSerializer, SubCategorySerializer,
    ProductListSerializer, ProductDetailSerializer, ProductCreateUpdateSerializer,
    ProductImageSerializer, ProductVariantSerializer, BarcodeProductSerializer,
    ProductStockUpdateSerializer, ContactMessageSubmitSerializer, ContactMessageSerializer,
    HomepageBannerSerializer, ProductReviewSerializer, ProductReviewWriteSerializer,
)
from apps.accounts.permissions import IsStaffUser, IsSeller
from apps.reports.models import StockMovement
from .search import filter_product_search, search_names_catalog


def public_categories():
    """Active categories with active subcategories, in admin display order."""
    active_subcategories = SubCategory.objects.filter(is_active=True).order_by('display_order', 'name')
    return Category.objects.filter(is_active=True).prefetch_related(
        Prefetch('subcategories', queryset=active_subcategories)
    )


def catalog_price(amount):
    """Decimal string with two places, which is what price feeds expect."""
    if amount is None:
        return None
    return f'{Decimal(amount):.2f}'


def catalog_in_stock(product):
    """True when the product, or any active variant, can still be sold."""
    variants = [variant for variant in product.variants.all() if variant.is_active]
    if variants:
        return any(variant.stock_quantity > 0 for variant in variants)
    return product.stock_quantity > 0


def catalog_image(product):
    """Primary image path, then the first image. Relative /media URL, or None."""
    images = list(product.images.all())
    chosen = next((image for image in images if image.is_primary), None)
    if chosen is None and images:
        chosen = images[0]
    if chosen is None or not chosen.image:
        return None
    try:
        return chosen.image.url
    except ValueError:
        return None


def catalog_brand(product):
    """Manufacturer from a specification named Brand, when the shop entered one."""
    for spec in product.specifications.all():
        if (spec.name or '').strip().lower() == 'brand' and (spec.value or '').strip():
            return spec.value.strip()
    return None


# Public Views
class CategoryListView(generics.ListAPIView):
    """List all active categories with subcategories."""
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        return public_categories()


class CategoryDetailView(generics.RetrieveAPIView):
    """Retrieve single category with products."""
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    
    def get_queryset(self):
        return public_categories()


class SubCategoryListView(generics.ListAPIView):
    """List subcategories for a category."""
    serializer_class = SubCategorySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        category_slug = self.kwargs.get('category_slug')
        return SubCategory.objects.filter(
            category__slug=category_slug,
            is_active=True
        )


class ProductSearchBackend(filters.SearchFilter):
    """Text search, plus every product in a category or subcategory the query names."""

    def filter_queryset(self, request, queryset, view):
        return filter_product_search(queryset, request.query_params.get(self.search_param, ''))


class ProductListView(generics.ListAPIView):
    """List products with filtering and search."""
    serializer_class = ProductListSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, ProductSearchBackend, filters.OrderingFilter]
    filterset_fields = ['subcategory', 'is_featured', 'color']
    ordering_fields = ['price', 'created_at', 'name']

    def get_queryset(self):
        queryset = with_catalog_stats(
            Product.objects.filter(is_active=True).select_related('category', 'subcategory')
        )
        
        # Multi-value category filter (comma-separated IDs)
        category_param = self.request.query_params.get('category')
        if category_param:
            category_ids = [c.strip() for c in category_param.split(',') if c.strip()]
            if category_ids:
                queryset = queryset.filter(category__id__in=category_ids)
        
        # Filter by category slug
        category_slug = self.request.query_params.get('category_slug')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        
        # Filter by subcategory slug
        subcategory_slug = self.request.query_params.get('subcategory_slug')
        if subcategory_slug:
            queryset = queryset.filter(subcategory__slug=subcategory_slug)
        
        # Multi-value size filter (comma-separated)
        size_param = self.request.query_params.get('size')
        if size_param:
            sizes = [s.strip() for s in size_param.split(',') if s.strip()]
            if sizes:
                queryset = queryset.filter(size__in=sizes)
        
        # Price range filter
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)

        on_sale = self.request.query_params.get('on_sale')
        if on_sale in ('1', 'true', 'True'):
            queryset = queryset.filter(
                compare_price__isnull=False,
                compare_price__gt=F('price'),
            )

        ids_param = self.request.query_params.get('ids')
        if ids_param is not None:
            valid_ids = []
            for raw in ids_param.split(',')[:50]:
                try:
                    valid_ids.append(uuid.UUID(raw.strip()))
                except (ValueError, AttributeError):
                    continue
            queryset = queryset.filter(id__in=valid_ids) if valid_ids else queryset.none()

        return queryset

    def paginate_queryset(self, queryset):
        # Wishlist lookups ask for a specific id set and should not be clipped
        # by the default page size. A category or subcategory name should return
        # every product under it, not the first page only.
        params = self.request.query_params
        if params.get('ids') is not None or search_names_catalog(params.get('search', '')):
            return None
        return super().paginate_queryset(queryset)


class ProductDetailView(generics.RetrieveAPIView):
    """Retrieve single product with full details."""
    serializer_class = ProductDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    
    def get_queryset(self):
        return with_catalog_stats(
            Product.objects.filter(is_active=True).prefetch_related('images', 'variants')
        )


class ProductReviewView(APIView):
    """Public review list. Signed-in shoppers can leave one review and delete it."""

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_product(self, slug):
        return get_object_or_404(Product, slug=slug, is_active=True)

    def get(self, request, slug):
        product = self.get_product(slug)
        reviews = product.reviews.select_related('user')
        stats = reviews.aggregate(average=Avg('rating'), count=Count('id'))
        mine = None
        if request.user.is_authenticated:
            mine = reviews.filter(user=request.user).first()
        return Response({
            'average': None if stats['average'] is None else round(float(stats['average']), 1),
            'count': stats['count'] or 0,
            'mine': ProductReviewSerializer(mine).data if mine else None,
            'results': ProductReviewSerializer(reviews[:100], many=True).data,
        })

    def post(self, request, slug):
        product = self.get_product(slug)
        serializer = ProductReviewWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review, created = ProductReview.objects.update_or_create(
            product=product,
            user=request.user,
            defaults=serializer.validated_data,
        )
        review = ProductReview.objects.select_related('user').get(pk=review.pk)
        return Response(
            ProductReviewSerializer(review).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, slug):
        product = self.get_product(slug)
        review = get_object_or_404(ProductReview, product=product, user=request.user)
        review.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FeaturedProductsView(generics.ListAPIView):
    """List featured products for homepage."""
    serializer_class = ProductListSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        return with_catalog_stats(Product.objects.filter(is_active=True, is_featured=True))[:12]


class HomepageConfigView(APIView):
    """Public homepage layout driven by admin configuration."""
    permission_classes = [AllowAny]

    def get(self, request):
        from .homepage import build_homepage
        return Response(build_homepage(request))


class CatalogIndexView(APIView):
    """Every active product and category, with no page size, for sitemap and feed."""
    permission_classes = [AllowAny]

    def get(self, request):
        reviews = ProductReview.objects.filter(product_id=OuterRef('pk')).order_by()
        average = reviews.values('product_id').annotate(avg=Avg('rating')).values('avg')[:1]
        total = reviews.values('product_id').annotate(total=Count('pk')).values('total')[:1]
        products = (
            Product.objects.filter(is_active=True)
            .select_related('category')
            .annotate(
                rating_average=Subquery(average, output_field=FloatField()),
                review_count=Coalesce(Subquery(total, output_field=IntegerField()), Value(0)),
            )
            .prefetch_related('specifications', 'images', 'variants')
            .order_by('slug')
        )
        product_rows = []
        for product in products:
            average_rating = product.rating_average
            product_rows.append({
                'slug': product.slug,
                'name': product.name,
                'updated_at': product.updated_at.isoformat(),
                'price': catalog_price(product.price),
                'short_description': product.short_description or '',
                'image': catalog_image(product),
                'in_stock': catalog_in_stock(product),
                'category_slug': product.category.slug if product.category_id else None,
                'brand': catalog_brand(product),
                'rating_average': None if average_rating is None else round(float(average_rating), 1),
                'review_count': int(product.review_count or 0),
            })

        categories = []
        for category in public_categories():
            categories.append({
                'slug': category.slug,
                'name': category.name,
                'updated_at': category.updated_at.isoformat(),
                'subcategories': [
                    {
                        'slug': sub.slug,
                        'name': sub.name,
                        'updated_at': sub.updated_at.isoformat(),
                    }
                    for sub in category.subcategories.all()
                ],
            })
        return Response({'products': product_rows, 'categories': categories})


def _logo_url(settings_obj, request):
    if not settings_obj.logo:
        return None
    url = settings_obj.logo.url
    if request is not None:
        return request.build_absolute_uri(url)
    return url


class AdminHomepageBannerListCreateView(generics.ListCreateAPIView):
    """Admin: list and upload homepage hero slides and side cards."""
    serializer_class = HomepageBannerSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    pagination_class = None
    queryset = HomepageBanner.objects.all()


class AdminHomepageBannerDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Admin: update or delete a homepage banner."""
    serializer_class = HomepageBannerSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    queryset = HomepageBanner.objects.all()


class HomepageBannerListView(generics.ListAPIView):
    """Public list of manually uploaded homepage banners."""
    serializer_class = HomepageBannerSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        queryset = HomepageBanner.objects.filter(is_active=True)
        placement = self.request.query_params.get('placement')
        if placement in ('hero', 'promo'):
            queryset = queryset.filter(placement=placement)
        return queryset


class CategoryProductsView(generics.ListAPIView):
    """List products grouped by category for homepage."""
    permission_classes = [AllowAny]

    def get(self, request):
        categories = Category.objects.filter(is_active=True)[:6]
        result = []
        for category in categories:
            products = with_catalog_stats(Product.objects.filter(
                category=category, is_active=True
            ))[:4]
            result.append({
                'category': CategoryListSerializer(category).data,
                'products': ProductListSerializer(products, many=True).data
            })
        return Response(result)


# Admin/Staff Views
class AdminCategoryListCreateView(generics.ListCreateAPIView):
    """Admin: List and create categories."""
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    queryset = Category.objects.all()


class AdminCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Admin: Retrieve, update, delete category."""
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    queryset = Category.objects.all()


class AdminSubCategoryListCreateView(generics.ListCreateAPIView):
    """Admin: List and create subcategories."""
    serializer_class = SubCategorySerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    queryset = SubCategory.objects.all()


class AdminSubCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Admin: Retrieve, update, delete subcategory."""
    serializer_class = SubCategorySerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    queryset = SubCategory.objects.all()


class AdminProductListCreateView(generics.ListCreateAPIView):
    """Admin: List and create products."""
    permission_classes = [IsAuthenticated, IsStaffUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category', 'subcategory', 'is_active', 'is_featured']
    search_fields = ['name', 'sku', 'barcode']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ProductCreateUpdateSerializer
        return ProductListSerializer

    def get_queryset(self):
        return with_catalog_stats(Product.objects.all().select_related(
            'category', 'subcategory'
        ).prefetch_related('variants'))

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except Exception as e:
            return Response(
                {'detail': f'Failed to create product: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


class AdminProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Admin: Retrieve, update, delete product."""
    permission_classes = [IsAuthenticated, IsStaffUser]
    queryset = Product.objects.all()

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ProductCreateUpdateSerializer
        return ProductDetailSerializer

    def destroy(self, request, *args, **kwargs):
        product = self.get_object()
        # Delete product images from storage
        for img in product.images.all():
            if img.image:
                img.image.delete(save=False)
        if product.barcode_image:
            product.barcode_image.delete(save=False)
        product.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductImageUploadView(generics.CreateAPIView):
    """Admin: Upload product images."""
    serializer_class = ProductImageSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]

    def perform_create(self, serializer):
        product_id = self.kwargs.get('product_id')
        product = Product.objects.get(id=product_id)
        serializer.save(product=product)


class ProductImageDeleteView(generics.DestroyAPIView):
    """Admin: Delete product image."""
    serializer_class = ProductImageSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    queryset = ProductImage.objects.all()


class BarcodeSearchView(APIView):
    """Search product by barcode/SKU for POS.
    
    Logic:
    1. Try variant barcode/SKU first (products with variants should be
       detected at the variant level).
    2. If no variant match, try the product's own barcode/SKU — but only
       return it directly when the product has NO active variants.
       If the product HAS variants, return a list so the POS can prompt
       the user to pick the correct variant.
    """
    permission_classes = [IsAuthenticated, IsSeller]

    def get(self, request):
        barcode = request.query_params.get('barcode', '').strip()
        if not barcode:
            return Response(
                {'error': 'Barcode is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Step 1: Try matching a variant barcode or variant SKU
        try:
            variant = ProductVariant.objects.select_related('product').get(
                Q(barcode=barcode) | Q(sku=barcode),
                is_active=True,
            )
            product = variant.product
            return Response({
                'id': str(product.id),
                'variant_id': str(variant.id),
                'name': product.name,
                'variant_label': f"{variant.size or ''} {variant.color or ''}".strip(),
                'sku': variant.sku,
                'barcode': variant.barcode,
                'price': float(variant.effective_price),
                'stock_quantity': variant.stock_quantity,
                'primary_image': product.primary_image,
                'has_variants': True,
            })
        except ProductVariant.DoesNotExist:
            pass

        # Step 2: Try matching the product barcode or product SKU
        try:
            product = Product.objects.get(
                Q(barcode=barcode) | Q(sku=barcode),
                is_active=True,
            )
            active_variants = product.variants.filter(is_active=True)

            if active_variants.exists():
                # Product has variants — return product info with variant list
                # so the POS can let the user pick the right variant
                variants_data = [
                    {
                        'id': str(v.id),
                        'label': f"{v.size or ''} {v.color or ''}".strip(),
                        'sku': v.sku,
                        'barcode': v.barcode,
                        'price': float(v.effective_price),
                        'stock_quantity': v.stock_quantity,
                    }
                    for v in active_variants
                ]
                return Response({
                    'id': str(product.id),
                    'name': product.name,
                    'sku': product.sku,
                    'barcode': product.barcode,
                    'price': float(product.price),
                    'stock_quantity': product.stock_quantity,
                    'primary_image': product.primary_image,
                    'has_variants': True,
                    'variants': variants_data,
                    'pick_variant': True,
                })
            else:
                # No variants — return the product directly
                data = BarcodeProductSerializer(product).data
                data['has_variants'] = False
                return Response(data)

        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class ProductStockUpdateView(APIView):
    """Update product stock with movement tracking."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def post(self, request, pk):
        serializer = ProductStockUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        quantity = serializer.validated_data['quantity']
        operation = serializer.validated_data['operation']
        reason = request.data.get('reason', 'adjustment')
        note = request.data.get('note', '')
        previous_stock = product.stock_quantity
        
        if operation == 'add':
            product.stock_quantity += quantity
            movement_type = 'in'
            movement_qty = quantity
        elif operation == 'subtract':
            if product.stock_quantity < quantity:
                return Response(
                    {'error': 'Insufficient stock'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            product.stock_quantity -= quantity
            movement_type = 'out'
            movement_qty = -quantity
        else:  # set
            diff = quantity - product.stock_quantity
            product.stock_quantity = quantity
            movement_type = 'adjustment'
            movement_qty = diff
        
        product.save()
        
        StockMovement.objects.create(
            product=product,
            variant=None,
            movement_type=movement_type,
            reason=reason,
            quantity=movement_qty,
            previous_stock=previous_stock,
            new_stock=product.stock_quantity,
            note=note,
            created_by=request.user,
        )
        
        return Response({
            'message': 'Stock updated successfully',
            'new_stock': product.stock_quantity
        })


class VariantStockUpdateView(APIView):
    """Update variant stock with movement tracking."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def post(self, request, variant_id):
        serializer = ProductStockUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            variant = ProductVariant.objects.select_related('product').get(pk=variant_id)
        except ProductVariant.DoesNotExist:
            return Response(
                {'error': 'Variant not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        quantity = serializer.validated_data['quantity']
        operation = serializer.validated_data['operation']
        reason = request.data.get('reason', 'adjustment')
        note = request.data.get('note', '')
        previous_stock = variant.stock_quantity

        if operation == 'add':
            variant.stock_quantity += quantity
            movement_type = 'in'
            movement_qty = quantity
        elif operation == 'subtract':
            if variant.stock_quantity < quantity:
                return Response(
                    {'error': 'Insufficient stock'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            variant.stock_quantity -= quantity
            movement_type = 'out'
            movement_qty = -quantity
        else:  # set
            diff = quantity - variant.stock_quantity
            variant.stock_quantity = quantity
            movement_type = 'adjustment'
            movement_qty = diff

        variant.save()

        StockMovement.objects.create(
            product=variant.product,
            variant=variant,
            movement_type=movement_type,
            reason=reason,
            quantity=movement_qty,
            previous_stock=previous_stock,
            new_stock=variant.stock_quantity,
            note=note,
            created_by=request.user,
        )

        return Response({
            'message': 'Variant stock updated successfully',
            'new_stock': variant.stock_quantity
        })


class InventoryItemsView(APIView):
    """List all products with their variants for inventory management.
    Returns a flat list: products without variants appear as single rows,
    products with variants are returned with their variant details.
    """
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get(self, request):
        search = request.query_params.get('search', '').strip()
        stock_filter = request.query_params.get('stock_status', '')  # all, in_stock, low_stock, out_of_stock
        category_id = request.query_params.get('category', '')

        products = Product.objects.filter(
            is_active=True
        ).select_related('category').prefetch_related(
            models.Prefetch(
                'variants',
                queryset=ProductVariant.objects.filter(is_active=True).order_by('size', 'color')
            )
        ).order_by('name')

        if search:
            products = products.filter(
                Q(name__icontains=search) |
                Q(sku__icontains=search) |
                Q(barcode__icontains=search) |
                Q(variants__sku__icontains=search) |
                Q(variants__barcode__icontains=search)
            ).distinct()

        if category_id:
            products = products.filter(category_id=category_id)

        items = []
        for product in products:
            variants = list(product.variants.all())
            has_variants = len(variants) > 0

            # Compute total stock across variants if applicable
            if has_variants:
                total_variant_stock = sum(v.stock_quantity for v in variants)
            else:
                total_variant_stock = product.stock_quantity

            # Determine low stock status (variant-aware)
            if has_variants:
                is_low = any(v.stock_quantity <= v.low_stock_threshold for v in variants)
                is_out = all(v.stock_quantity == 0 for v in variants)
            else:
                is_low = product.stock_quantity <= product.low_stock_threshold
                is_out = product.stock_quantity == 0

            # Stock status filter
            if stock_filter == 'out_of_stock' and not is_out:
                continue
            if stock_filter == 'low_stock' and (is_out or not is_low):
                continue
            if stock_filter == 'in_stock' and (is_out or is_low):
                continue

            variant_data = []
            for v in variants:
                variant_data.append({
                    'id': str(v.id),
                    'sku': v.sku,
                    'barcode': v.barcode,
                    'size': v.size,
                    'color': v.color,
                    'price': float(v.effective_price),
                    'stock_quantity': v.stock_quantity,
                    'low_stock_threshold': v.low_stock_threshold,
                    'is_active': v.is_active,
                })

            items.append({
                'id': str(product.id),
                'name': product.name,
                'sku': product.sku,
                'barcode': product.barcode,
                'category': product.category.name if product.category else None,
                'price': float(product.price),
                'stock_quantity': product.stock_quantity,
                'total_stock': total_variant_stock,
                'low_stock_threshold': product.low_stock_threshold,
                'has_variants': has_variants,
                'variants': variant_data,
                'primary_image': product.primary_image,
            })

        return Response({
            'count': len(items),
            'items': items,
        })


class LowStockProductsView(generics.ListAPIView):
    """List products with low stock (including variant-level low stock)."""
    serializer_class = ProductListSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get_queryset(self):
        # Products without variants that are low stock
        no_variant_low = models.Q(
            variants__isnull=True,
            stock_quantity__lte=models.F('low_stock_threshold'),
        )
        # Products with at least one variant that is low stock
        variant_low = models.Q(
            variants__is_active=True,
            variants__stock_quantity__lte=models.F('variants__low_stock_threshold'),
        )
        return with_catalog_stats(Product.objects.filter(
            is_active=True
        ).filter(
            no_variant_low | variant_low
        ).distinct().prefetch_related('variants').order_by('name'))


class VariantSetupView(APIView):
    """Replace a product's options and the combinations shoppers can buy."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def put(self, request, product_id):
        from apps.products.variants import SetupError, option_groups, sync_variant_setup

        product = get_object_or_404(Product, pk=product_id)
        try:
            sync_variant_setup(
                product,
                request.data.get('option_groups', []),
                request.data.get('variants', []),
            )
        except SetupError as exc:
            return Response({'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        product = Product.objects.prefetch_related(
            'options__values', 'variants__values__option',
        ).get(pk=product.pk)
        return Response({
            'option_groups': option_groups(product),
            'variants': ProductVariantSerializer(product.variants.all(), many=True).data,
        })


class ProductVariantListCreateView(generics.ListCreateAPIView):
    """List and create product variants."""
    serializer_class = ProductVariantSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get_queryset(self):
        product_id = self.kwargs.get('product_id')
        return ProductVariant.objects.filter(product_id=product_id)

    def perform_create(self, serializer):
        product_id = self.kwargs.get('product_id')
        product = Product.objects.get(id=product_id)
        serializer.save(product=product)


class ProductVariantDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, delete product variant."""
    serializer_class = ProductVariantSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get_queryset(self):
        product_id = self.kwargs.get('product_id')
        return ProductVariant.objects.filter(product_id=product_id)


_BADGE_SIZES = {'small', 'medium', 'large'}
_BADGE_POSITIONS = {'top-left', 'top-right', 'bottom-left', 'bottom-right'}
_BADGE_COLOR = re.compile(r'^#[0-9A-Fa-f]{6}$')


def _clean_official_badge(field, value):
    text = '' if value is None else str(value).strip()
    if field == 'official_badge_size':
        text = text.lower()
        return text if text in _BADGE_SIZES else None
    if field == 'official_badge_position':
        text = text.lower()
        return text if text in _BADGE_POSITIONS else None
    if not text.startswith('#'):
        text = f'#{text}'
    if not _BADGE_COLOR.match(text):
        return None
    return text.upper()


def _official_badge_error(field):
    if field == 'official_badge_size':
        return 'Choose a small, medium, or large official badge.'
    if field == 'official_badge_position':
        return 'Choose a corner for the official badge.'
    return 'Choose a color for the official badge.'


class PublicStoreSettingsView(APIView):
    """Public endpoint for client to fetch store settings (no auth required)."""
    permission_classes = [AllowAny]

    def get(self, request):
        from .models import StoreSettings
        settings = StoreSettings.get_settings()
        return Response({
            'logo': _logo_url(settings, request),
            'popular_searches': settings.popular_searches,
            'contact_address': settings.contact_address,
            'contact_phone_1': settings.contact_phone_1,
            'contact_phone_2': settings.contact_phone_2,
            'contact_email_1': settings.contact_email_1,
            'contact_email_2': settings.contact_email_2,
            'business_hours': settings.business_hours,
            'map_embed_url': settings.map_embed_url,
            'official_badge_size': settings.official_badge_size,
            'official_badge_color': settings.official_badge_color,
            'official_badge_position': settings.official_badge_position,
        })


class StoreSettingsView(APIView):
    """Get and update store settings (admin only)."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    SETTINGS_FIELDS = [
        'barcode_prefix', 'popular_searches',
        'contact_address', 'contact_phone_1', 'contact_phone_2',
        'contact_email_1', 'contact_email_2', 'business_hours',
        'map_embed_url',
    ]
    BADGE_FIELDS = (
        'official_badge_size',
        'official_badge_color',
        'official_badge_position',
    )

    def _payload(self, settings, request):
        data = {field: getattr(settings, field) for field in self.SETTINGS_FIELDS}
        data['logo'] = _logo_url(settings, request)
        for field in self.BADGE_FIELDS:
            data[field] = getattr(settings, field)
        return data

    def get(self, request):
        from .models import StoreSettings
        settings = StoreSettings.get_settings()
        return Response(self._payload(settings, request))

    def patch(self, request):
        from .models import StoreSettings
        settings = StoreSettings.get_settings()
        
        updated = False
        for field in self.SETTINGS_FIELDS:
            value = request.data.get(field)
            if value is not None:
                setattr(settings, field, value)
                updated = True
        for field in self.BADGE_FIELDS:
            if field not in request.data:
                continue
            cleaned = _clean_official_badge(field, request.data.get(field))
            if cleaned is None:
                return Response(
                    {'detail': _official_badge_error(field)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            setattr(settings, field, cleaned)
            updated = True
        if 'logo' in request.FILES:
            settings.logo = request.FILES['logo']
            updated = True
        
        if updated:
            settings.save()
        
        data = self._payload(settings, request)
        data['message'] = 'Settings updated successfully'
        return Response(data)


class PublicContactSubmitView(APIView):
    """Public endpoint for customers to submit contact messages."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ContactMessageSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {'message': 'Your message has been sent successfully. We will get back to you soon.'},
            status=status.HTTP_201_CREATED
        )


class AdminContactMessageListView(generics.ListAPIView):
    """Admin endpoint to list all contact messages."""
    serializer_class = ContactMessageSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get_queryset(self):
        qs = ContactMessage.objects.all()
        # Filter by status
        msg_status = self.request.query_params.get('status')
        if msg_status:
            qs = qs.filter(status=msg_status)
        # Search
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(email__icontains=search) |
                Q(subject__icontains=search) |
                Q(message__icontains=search)
            )
        return qs


class AdminContactMessageDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Admin endpoint to view, update status/notes, or delete a contact message."""
    serializer_class = ContactMessageSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    queryset = ContactMessage.objects.all()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # Auto-mark as read when viewed
        if instance.status == 'new':
            instance.status = 'read'
            instance.save(update_fields=['status', 'updated_at'])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
