"""
Views for products app.
"""
import re
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from rest_framework import generics, status, filters
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.db import models, transaction
from django.db.models import (
    Avg, Count, F, FloatField, IntegerField, OuterRef, Prefetch, ProtectedError, Q, Subquery, Value,
)
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import (
    CatalogImport, Category, SubCategory, Product, ProductImage, ProductVideo, ProductVariant,
    ProductReview, ProductReviewImage, ContactMessage, HomepageBanner, public_variant_queryset,
    with_catalog_stats, with_public_catalog,
)
from .serializers import (
    CategorySerializer, CategoryListSerializer, SubCategorySerializer, AdminCategorySerializer,
    ProductListSerializer, ProductDetailSerializer, ProductCreateUpdateSerializer,
    AdminProductListSerializer, AdminProductDetailSerializer, CatalogImportSerializer,
    ProductImageSerializer, ProductVideoSerializer, ProductVariantSerializer, BarcodeProductSerializer,
    ProductStockUpdateSerializer, StockTransferSerializer,
    ContactMessageSubmitSerializer, ContactMessageSerializer,
    HomepageBannerSerializer, HomepageSectionSerializer, ProductReviewSerializer,
    ProductReviewWriteSerializer,
)
from apps.accounts.permissions import IsStaffUser, IsSeller
from core.pagination import AdminPagination
from .costing import StockError, apply_stock_operation, remove_units, transfer_stock
from .homepage import curated_product_sections_queryset
from .search import filter_product_search, search_names_catalog
from .services import user_can_review_product

REVIEW_IMAGE_MAX = 5
REVIEW_IMAGE_MAX_BYTES = 5 * 1024 * 1024
REVIEW_IMAGE_CONTENT_TYPES = {
    'image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/gif',
}
_IMAGE_TYPE_ALIASES = {
    'image/jpg': 'image/jpeg',
    'image/pjpeg': 'image/jpeg',
    'image/x-png': 'image/png',
    'image/x-citrix-jpeg': 'image/jpeg',
    'image/x-citrix-png': 'image/png',
}


def public_categories():
    """Active categories/subcategories that have at least one active product."""
    has_sellable_products = Count(
        'products',
        filter=Q(products__is_active=True),
        distinct=True,
    )
    # Homepage tiles use this when a subcategory has no cover of its own.
    cover = (
        ProductImage.objects.filter(
            product__subcategory=OuterRef('pk'),
            product__is_active=True,
        )
        .order_by('-is_primary', 'display_order', 'id')
        .values('image')[:1]
    )
    active_subcategories = (
        SubCategory.objects.filter(is_active=True)
        .annotate(
            _active_product_count=has_sellable_products,
            _cover_image=Subquery(cover),
        )
        .filter(_active_product_count__gt=0)
        .order_by('display_order', 'name')
    )
    return (
        Category.objects.filter(is_active=True)
        .annotate(_active_product_count=has_sellable_products)
        .filter(_active_product_count__gt=0)
        .prefetch_related(Prefetch('subcategories', queryset=active_subcategories))
    )


def catalog_price(amount):
    """Decimal string with two places, which is what price feeds expect."""
    if amount is None:
        return None
    return f'{Decimal(amount):.2f}'


def catalog_in_stock(product):
    """True when a customer can buy the product."""
    return product.is_available


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
        return (
            SubCategory.objects.filter(
                category__slug=category_slug,
                is_active=True,
            )
            .annotate(
                _active_product_count=Count(
                    'products',
                    filter=Q(products__is_active=True),
                    distinct=True,
                )
            )
            .filter(_active_product_count__gt=0)
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
        queryset = with_public_catalog(
            Product.objects.select_related('category', 'subcategory')
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
        return with_public_catalog(
            Product.objects.prefetch_related('images', 'videos')
        )


def _review_image_files(request):
    files = request.FILES.getlist('images') or request.FILES.getlist('images[]')
    if not files:
        single = request.FILES.get('images') or request.FILES.get('image')
        if single:
            files = [single]
    return list(files)


def _declared_image_type(upload):
    raw = (getattr(upload, 'content_type', None) or '').split(';', 1)[0].strip().lower()
    return _IMAGE_TYPE_ALIASES.get(raw, raw)


def _peek_header(upload, size=16):
    """Read the start of an upload and put the cursor back so the file still saves whole."""
    try:
        position = upload.tell()
        header = upload.read(size) or b''
        upload.seek(position)
    except Exception:
        return b''
    return header


def _sniff_image_type(header):
    if header.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if header.startswith((b'GIF87a', b'GIF89a')):
        return 'image/gif'
    if len(header) >= 12 and header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return 'image/webp'
    return ''


def _validate_review_images(files):
    if len(files) > REVIEW_IMAGE_MAX:
        raise ValidationError({
            'images': [f'You can attach up to {REVIEW_IMAGE_MAX} photos.'],
        })
    for upload in files:
        declared = _declared_image_type(upload)
        # The app sends gallery photos as application/octet-stream. Trust the bytes.
        sniffed = _sniff_image_type(_peek_header(upload))
        if sniffed:
            if declared != sniffed and hasattr(upload, 'content_type'):
                upload.content_type = sniffed
        elif declared not in REVIEW_IMAGE_CONTENT_TYPES:
            raise ValidationError({'images': ['Photos must be JPEG, PNG, WebP, or GIF.']})
        size = getattr(upload, 'size', None)
        if size is not None and size > REVIEW_IMAGE_MAX_BYTES:
            raise ValidationError({'images': ['Each photo must be 5 MB or smaller.']})
    return files


class ProductReviewView(APIView):
    """Public review list with filters. Delivered buyers may leave one review (+ photos)."""

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_product(self, slug):
        return get_object_or_404(Product, slug=slug, is_active=True)

    def get(self, request, slug):
        product = self.get_product(slug)
        base = product.reviews.select_related('user').prefetch_related('images')
        stats = base.aggregate(average=Avg('rating'), count=Count('id'))
        breakdown_rows = (
            base.values('rating')
            .annotate(total=Count('id'))
            .order_by('rating')
        )
        rating_breakdown = {str(star): 0 for star in range(1, 6)}
        for row in breakdown_rows:
            rating_breakdown[str(row['rating'])] = row['total']

        qs = base
        rating = (request.query_params.get('rating') or '').strip()
        if rating:
            try:
                star = int(rating)
            except ValueError:
                star = None
            if star in {1, 2, 3, 4, 5}:
                qs = qs.filter(rating=star)

        with_photos = (request.query_params.get('with_photos') or '').strip().lower()
        if with_photos in {'1', 'true', 'yes'}:
            qs = qs.filter(images__isnull=False).distinct()

        sort = (request.query_params.get('sort') or 'newest').strip().lower()
        if sort == 'highest':
            qs = qs.order_by('-rating', '-created_at')
        elif sort == 'lowest':
            qs = qs.order_by('rating', '-created_at')
        else:
            qs = qs.order_by('-created_at')

        mine = None
        can_review = False
        if request.user.is_authenticated:
            mine = base.filter(user=request.user).first()
            can_review = user_can_review_product(request.user, product)

        paginator = AdminPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        results = ProductReviewSerializer(page, many=True, context={'request': request}).data
        response = paginator.get_paginated_response(results)
        body = response.data
        filtered_count = body.get('count', len(results))
        body.update({
            'average': None if stats['average'] is None else round(float(stats['average']), 1),
            'count': stats['count'] or 0,
            'filtered_count': filtered_count,
            'rating_breakdown': rating_breakdown,
            'can_review': can_review,
            'mine': (
                ProductReviewSerializer(mine, context={'request': request}).data
                if mine else None
            ),
        })
        return Response(body)

    def post(self, request, slug):
        product = self.get_product(slug)
        if not user_can_review_product(request.user, product):
            return Response(
                {
                    'error': 'You can review this product after an order with it is delivered.',
                    'code': 'not_eligible',
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = ProductReviewWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        files = _validate_review_images(_review_image_files(request))
        clear_images = bool(data.pop('clear_images', False))

        review, created = ProductReview.objects.update_or_create(
            product=product,
            user=request.user,
            defaults={'rating': data['rating'], 'comment': data['comment']},
        )
        if files:
            review.images.all().delete()
            for index, upload in enumerate(files):
                ProductReviewImage.objects.create(review=review, image=upload, sort_order=index)
        elif clear_images:
            review.images.all().delete()

        review = (
            ProductReview.objects.select_related('user')
            .prefetch_related('images')
            .get(pk=review.pk)
        )
        return Response(
            ProductReviewSerializer(review, context={'request': request}).data,
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
        return with_public_catalog(
            Product.objects.filter(is_featured=True)
        )[:12]


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
            .prefetch_related(
                'specifications',
                'images',
                Prefetch('variants', queryset=public_variant_queryset()),
            )
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


def _media_url(file_field, request):
    if not file_field:
        return None
    url = file_field.url
    if request is not None:
        return request.build_absolute_uri(url)
    return url


def _logo_url(settings_obj, request):
    return _media_url(settings_obj.logo, request)


def _directory_banner_url(settings_obj, request):
    return _media_url(settings_obj.default_directory_banner, request)


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


class AdminHomepageSectionListView(generics.ListAPIView):
    """Admin: curated homepage product rows (trending, new arrivals)."""
    serializer_class = HomepageSectionSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    pagination_class = None

    def get_queryset(self):
        return curated_product_sections_queryset()


class AdminHomepageSectionDetailView(generics.RetrieveUpdateAPIView):
    """Admin: update a curated homepage product row and its product picks."""
    serializer_class = HomepageSectionSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    lookup_field = 'key'
    http_method_names = ['get', 'put', 'patch', 'head', 'options']

    def get_queryset(self):
        return curated_product_sections_queryset()


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
        result = []
        for category in public_categories()[:6]:
            products = with_public_catalog(Product.objects.filter(
                category=category,
            ))[:4]
            if not products:
                continue
            result.append({
                'category': CategoryListSerializer(category).data,
                'products': ProductListSerializer(products, many=True).data
            })
        return Response(result)


def admin_categories():
    """Categories with product counts for the admin catalog.

    A subcategory counts only the products that share its category, so a stale
    link cannot show one product in two categories. Ordering is explicit because
    Django drops Meta.ordering from grouped queries.
    """
    return Category.objects.annotate(
        catalog_product_count=Count('products', distinct=True),
    ).order_by('display_order', 'name').prefetch_related(Prefetch(
        'subcategories',
        queryset=SubCategory.objects.annotate(catalog_product_count=Count(
            'products', filter=Q(products__category=F('category')), distinct=True,
        )).order_by('display_order', 'name'),
    ))


# Admin/Staff Views
class AdminCategoryListCreateView(generics.ListCreateAPIView):
    """Admin: List and create categories."""
    serializer_class = AdminCategorySerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    pagination_class = None

    def get_queryset(self):
        return admin_categories()


class AdminCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Admin: Retrieve, update, delete category."""
    serializer_class = AdminCategorySerializer
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get_queryset(self):
        return admin_categories()

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        try:
            category.delete()
        except ProtectedError:
            return Response(
                {'detail': f'{category.name} still has products. Move or delete them first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


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
    pagination_class = AdminPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category', 'subcategory', 'is_active', 'is_featured', 'supply_type']
    search_fields = ['name', 'sku', 'barcode']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ProductCreateUpdateSerializer
        return AdminProductListSerializer

    def get_queryset(self):
        queryset = with_catalog_stats(Product.objects.all().select_related(
            'category', 'subcategory', 'supplied_by', 'catalog_import'
        ).prefetch_related('variants'))
        if self.request.query_params.get('direct') == 'true':
            # Keeps null subcategories, and stale links to another category's subcategory.
            queryset = queryset.exclude(subcategory__category=F('category'))
        provider = (self.request.query_params.get('provider') or '').strip().lower()
        if provider == 'store':
            queryset = queryset.filter(catalog_import__isnull=True)
        elif provider in dict(CatalogImport.PROVIDER_CHOICES):
            queryset = queryset.filter(catalog_import__provider=provider)
        elif provider:
            queryset = queryset.none()
        return queryset

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except ValidationError:
            raise
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
        return AdminProductDetailSerializer

    def get_queryset(self):
        return (
            Product.objects.all()
            .select_related('supplied_by', 'catalog_import')
            .prefetch_related('images', 'videos', 'variants')
        )

    def destroy(self, request, *args, **kwargs):
        product = self.get_object()
        files = [img.image for img in product.images.all() if img.image]
        if product.barcode_image:
            files.append(product.barcode_image)
        try:
            product.delete()
        except ProtectedError:
            return Response(
                {'detail': 'This product has purchase records, so it cannot be deleted. Set it to inactive instead.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Delete product images from storage only once the product is really gone.
        for file in files:
            file.delete(save=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _strict_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {'1', 'true', 'yes'}:
            return True
        if lowered in {'0', 'false', 'no'}:
            return False
    return None


class CatalogImportListView(generics.ListAPIView):
    """Staff: imported shop batches, newest first."""
    serializer_class = CatalogImportSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    pagination_class = None

    def get_queryset(self):
        queryset = CatalogImport.objects.annotate(product_count=Count('products')).order_by('-imported_at')
        provider = (self.request.query_params.get('provider') or '').strip().lower()
        if provider:
            queryset = queryset.filter(provider=provider)
        return queryset


class CatalogImportAdjustView(APIView):
    """Staff: change price or listing flags for every product in one import batch.

    A percent is applied to the current price, so a later change stacks on the last edit.
    Compare price moves by the same percent when the product has one. Only fields present
    in the request are written.
    """
    permission_classes = [IsAuthenticated, IsStaffUser]

    def post(self, request, pk):
        batch = get_object_or_404(CatalogImport, pk=pk)
        flags = {}
        if 'is_active' in request.data:
            active = _strict_bool(request.data.get('is_active'))
            if active is None:
                return Response({'detail': 'is_active must be true or false.'}, status=status.HTTP_400_BAD_REQUEST)
            flags['is_active'] = active
        if 'dealer_available' in request.data:
            dealer = _strict_bool(request.data.get('dealer_available'))
            if dealer is None:
                return Response(
                    {'detail': 'dealer_available must be true or false.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            flags['dealer_available'] = dealer
        if 'warranty_period' in request.data:
            warranty = str(request.data.get('warranty_period') or '').strip()
            if len(warranty) > 80:
                return Response(
                    {'detail': 'Warranty text must be 80 characters or fewer.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            flags['warranty_period'] = warranty

        raw_percent = request.data.get('price_percent', None)
        has_price = raw_percent not in (None, '')
        if not has_price and not flags:
            return Response(
                {'detail': 'Send a price percent or a listing field to update.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        multiplier = None
        if has_price:
            try:
                percent = Decimal(str(raw_percent))
            except InvalidOperation:
                return Response(
                    {'detail': 'Enter a price percent such as 10 or -5.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            multiplier = (Decimal('100') + percent) / Decimal('100')
            if multiplier < 0:
                return Response(
                    {'detail': 'A price cannot be reduced below zero.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        now = timezone.now()
        with transaction.atomic():
            if multiplier is None:
                updated = batch.products.update(**flags, updated_at=now)
            else:
                updated = 0
                products = batch.products.select_for_update().order_by('pk')
                for product in products:
                    product.price = (product.price * multiplier).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    update_fields = ['price', 'updated_at']
                    if product.compare_price is not None:
                        product.compare_price = (product.compare_price * multiplier).quantize(
                            Decimal('0.01'), rounding=ROUND_HALF_UP,
                        )
                        update_fields.append('compare_price')
                    for key, value in flags.items():
                        setattr(product, key, value)
                        update_fields.append(key)
                    product.updated_at = now
                    product.save(update_fields=update_fields)
                    updated += 1

        return Response({
            'id': str(batch.id),
            'provider': batch.provider,
            'label': batch.label,
            'updated': updated,
            'product_count': batch.products.count(),
        })


class ProductImageUploadView(generics.CreateAPIView):
    """Admin: Upload product images. Optional variant scopes the image to one SKU."""
    serializer_class = ProductImageSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        product_id = self.kwargs.get('product_id')
        context['product'] = Product.objects.get(id=product_id)
        return context

    def perform_create(self, serializer):
        product = self.get_serializer_context()['product']
        serializer.save(product=product)


class ProductImageDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Admin: Update assignment (variant / primary) or delete a product image."""
    serializer_class = ProductImageSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    queryset = ProductImage.objects.select_related('product', 'variant')
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    def get_serializer_context(self):
        context = super().get_serializer_context()
        image = ProductImage.objects.filter(pk=self.kwargs.get('pk')).select_related('product').first()
        if image:
            context['product'] = image.product
        return context


class ProductVideoCreateView(generics.CreateAPIView):
    """Admin: Attach a YouTube link. Optional variant scopes the video to one SKU."""
    serializer_class = ProductVideoSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        product_id = self.kwargs.get('product_id')
        context['product'] = Product.objects.get(id=product_id)
        return context

    def perform_create(self, serializer):
        product = self.get_serializer_context()['product']
        serializer.save(product=product)


class ProductVideoDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Admin: Update assignment (variant / primary) or delete a product video."""
    serializer_class = ProductVideoSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    queryset = ProductVideo.objects.select_related('product', 'variant')
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    def get_serializer_context(self):
        context = super().get_serializer_context()
        video = ProductVideo.objects.filter(pk=self.kwargs.get('pk')).select_related('product').first()
        if video:
            context['product'] = video.product
        return context


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


def _stock_response(result, message):
    expense = result.get('expense')
    return Response({
        'message': message,
        'new_stock': result['new_stock'],
        'warehouse_stock': result.get('warehouse_stock'),
        'dealer_stock': result.get('dealer_stock'),
        'location_stock': result.get('location_stock'),
        'voucher_number': expense.voucher_number if expense else None,
    })


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

        try:
            result = apply_stock_operation(
                product=product,
                quantity=serializer.validated_data['quantity'],
                operation=serializer.validated_data['operation'],
                reason=serializer.validated_data.get('reason') or 'adjustment',
                note=serializer.validated_data.get('note') or '',
                user=request.user,
                unit_cost=serializer.validated_data.get('unit_cost'),
                payment_method=serializer.validated_data.get('payment_method') or '',
                payee=serializer.validated_data.get('payee') or '',
                location=serializer.validated_data.get('location') or 'warehouse',
            )
        except StockError as exc:
            return Response({'error': exc.message}, status=status.HTTP_400_BAD_REQUEST)

        return _stock_response(result, 'Stock updated successfully')


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

        try:
            result = apply_stock_operation(
                product=variant.product,
                variant=variant,
                quantity=serializer.validated_data['quantity'],
                operation=serializer.validated_data['operation'],
                reason=serializer.validated_data.get('reason') or 'adjustment',
                note=serializer.validated_data.get('note') or '',
                user=request.user,
                unit_cost=serializer.validated_data.get('unit_cost'),
                payment_method=serializer.validated_data.get('payment_method') or '',
                payee=serializer.validated_data.get('payee') or '',
                location=serializer.validated_data.get('location') or 'warehouse',
            )
        except StockError as exc:
            return Response({'error': exc.message}, status=status.HTTP_400_BAD_REQUEST)

        return _stock_response(result, 'Variant stock updated successfully')


class ProductStockTransferView(APIView):
    """Move product stock between warehouse and dealer."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def post(self, request, pk):
        serializer = StockTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = get_object_or_404(Product, pk=pk)
        try:
            result = transfer_stock(
                product=product,
                quantity=serializer.validated_data['quantity'],
                from_location=serializer.validated_data['from_location'],
                to_location=serializer.validated_data['to_location'],
                note=serializer.validated_data.get('note') or '',
                user=request.user,
            )
        except StockError as exc:
            return Response({'error': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': 'Stock transferred successfully', **result})


class VariantStockTransferView(APIView):
    """Move variant stock between warehouse and dealer."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def post(self, request, variant_id):
        serializer = StockTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        variant = get_object_or_404(ProductVariant.objects.select_related('product'), pk=variant_id)
        try:
            result = transfer_stock(
                product=variant.product,
                variant=variant,
                quantity=serializer.validated_data['quantity'],
                from_location=serializer.validated_data['from_location'],
                to_location=serializer.validated_data['to_location'],
                note=serializer.validated_data.get('note') or '',
                user=request.user,
            )
        except StockError as exc:
            return Response({'error': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': 'Variant stock transferred successfully', **result})


class AdminSellerListView(APIView):
    """Active seller accounts for the internal supply classification."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get(self, request):
        from apps.accounts.models import User
        sellers = User.objects.filter(role='seller', is_active=True).order_by(
            'first_name', 'last_name'
        )
        return Response([
            {
                'id': str(seller.id),
                'full_name': seller.full_name,
                'email': seller.email,
            }
            for seller in sellers
        ])


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
        supply_type = request.query_params.get('supply_type', '').strip()

        products = Product.objects.filter(
            is_active=True
        ).select_related('category', 'supplied_by').prefetch_related(
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

        if supply_type in (Product.SUPPLY_AVAILABLE, Product.SUPPLY_SELLER):
            products = products.filter(supply_type=supply_type)

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
            total_warehouse = 0
            total_dealer = 0
            for v in variants:
                total_warehouse += v.warehouse_stock or 0
                total_dealer += v.dealer_stock or 0
                variant_data.append({
                    'id': str(v.id),
                    'sku': v.sku,
                    'size': v.size,
                    'color': v.color,
                    'price': float(v.effective_price),
                    'stock_quantity': v.stock_quantity,
                    'warehouse_stock': v.warehouse_stock,
                    'dealer_stock': v.dealer_stock,
                    'low_stock_threshold': v.low_stock_threshold,
                    'is_active': v.is_active,
                })

            if not has_variants:
                total_warehouse = product.warehouse_stock or 0
                total_dealer = product.dealer_stock or 0

            seller = product.supplied_by
            items.append({
                'id': str(product.id),
                'name': product.name,
                'sku': product.sku,
                'category': product.category.name if product.category else None,
                'price': float(product.price),
                'cost_price': float(product.cost_price) if product.cost_price is not None else None,
                'stock_quantity': product.stock_quantity,
                'warehouse_stock': total_warehouse,
                'dealer_stock': total_dealer,
                'total_stock': total_variant_stock,
                'dealer_available': bool(product.dealer_available),
                'low_stock_threshold': product.low_stock_threshold,
                'has_variants': has_variants,
                'variants': variant_data,
                'primary_image': product.primary_image,
                'supply_type': product.supply_type,
                'supplied_by': str(seller.id) if seller else None,
                'supplied_by_name': seller.full_name if seller else None,
            })

        return Response({
            'count': len(items),
            'items': items,
        })


class InventoryUploadView(APIView):
    """CSV upload for inventory adjustments and warehouse/dealer transfers.

    Columns (header row required):
    sku,location,operation,quantity,reason,unit_cost,note,from_location,to_location

    - operation: add | subtract | set | transfer
    - location: warehouse | dealer (required for add/subtract/set)
    - from_location / to_location: required when operation=transfer
    """
    permission_classes = [IsAuthenticated, IsStaffUser]

    def post(self, request):
        import csv
        import io

        upload = request.FILES.get('file')
        if upload is None:
            return Response({'error': 'Upload a CSV file as "file".'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            text = upload.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            return Response({'error': 'CSV must be UTF-8 encoded.'}, status=status.HTTP_400_BAD_REQUEST)

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            return Response({'error': 'CSV is empty.'}, status=status.HTTP_400_BAD_REQUEST)

        required = {'sku', 'operation', 'quantity'}
        headers = {name.strip().lower() for name in reader.fieldnames if name}
        if not required.issubset(headers):
            return Response(
                {'error': 'CSV must include sku, operation, and quantity columns.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated = 0
        errors = []
        for index, raw in enumerate(reader, start=2):
            row = {(key or '').strip().lower(): (value or '').strip() for key, value in raw.items()}
            sku = row.get('sku')
            operation = (row.get('operation') or '').lower()
            try:
                quantity = int(row.get('quantity') or 0)
            except ValueError:
                errors.append({'row': index, 'error': 'Quantity must be a number.'})
                continue
            if not sku:
                errors.append({'row': index, 'error': 'SKU is required.'})
                continue

            variant = ProductVariant.objects.select_related('product').filter(
                models.Q(sku__iexact=sku) | models.Q(barcode__iexact=sku)
            ).first()
            product = None
            if variant is None:
                product = Product.objects.filter(
                    models.Q(sku__iexact=sku) | models.Q(barcode__iexact=sku)
                ).first()
                if product is None:
                    errors.append({'row': index, 'error': f'No product/variant found for SKU {sku}.'})
                    continue
                if product.variants.exists():
                    errors.append({
                        'row': index,
                        'error': f'{sku} has variants. Use a variant SKU.',
                    })
                    continue
            else:
                product = variant.product

            try:
                if operation == 'transfer':
                    transfer_stock(
                        product=product,
                        variant=variant,
                        quantity=quantity,
                        from_location=row.get('from_location') or 'warehouse',
                        to_location=row.get('to_location') or 'dealer',
                        note=row.get('note') or f'CSV upload row {index}',
                        user=request.user,
                    )
                elif operation in {'add', 'subtract', 'set'}:
                    unit_cost = row.get('unit_cost') or None
                    apply_stock_operation(
                        product=product,
                        variant=variant,
                        quantity=quantity,
                        operation=operation,
                        reason=(row.get('reason') or 'adjustment').lower(),
                        note=row.get('note') or f'CSV upload row {index}',
                        user=request.user,
                        unit_cost=unit_cost,
                        location=(row.get('location') or 'warehouse').lower(),
                    )
                else:
                    errors.append({'row': index, 'error': f'Unknown operation "{operation}".'})
                    continue
                updated += 1
            except StockError as exc:
                errors.append({'row': index, 'error': exc.message})
            except Exception as exc:  # noqa: BLE001 - surface row errors to admin
                errors.append({'row': index, 'error': str(exc)})

        return Response({
            'updated': updated,
            'failed': len(errors),
            'errors': errors[:50],
        })


class LowStockProductsView(generics.ListAPIView):
    """List products with low stock (including variant-level low stock)."""
    serializer_class = AdminProductListSerializer
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

    def perform_destroy(self, instance):
        if instance.stock_quantity:
            remove_units(
                product=instance.product,
                variant=instance,
                quantity=instance.stock_quantity,
                reason='adjustment',
                note='Variant removed',
                user=self.request.user,
                movement_type='adjustment',
            )
        instance.delete()


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


DELIVERY_FIELDS = ('delivery_charge_inside_dhaka', 'delivery_charge_outside_dhaka')
MAX_DELIVERY_CHARGE = Decimal('10000')


def _clean_delivery_charge(value):
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount < 0 or amount > MAX_DELIVERY_CHARGE:
        return None
    return amount.quantize(Decimal('0.01'))


class PublicStoreSettingsView(APIView):
    """Public endpoint for client to fetch store settings (no auth required)."""
    permission_classes = [AllowAny]

    def get(self, request):
        from .models import StoreSettings
        settings = StoreSettings.get_settings()
        return Response({
            'logo': _logo_url(settings, request),
            'default_directory_banner': _directory_banner_url(settings, request),
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
            'delivery_charge_inside_dhaka': settings.delivery_charge_inside_dhaka,
            'delivery_charge_outside_dhaka': settings.delivery_charge_outside_dhaka,
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
        data['default_directory_banner'] = _directory_banner_url(settings, request)
        for field in (*self.BADGE_FIELDS, *DELIVERY_FIELDS):
            data[field] = getattr(settings, field)
        return data

    def get(self, request):
        from .models import StoreSettings
        settings = StoreSettings.get_settings()
        return Response(self._payload(settings, request))

    def patch(self, request):
        from .models import StoreSettings
        charges = [field for field in DELIVERY_FIELDS if field in request.data]
        if charges and not request.user.is_super_admin():
            return Response(
                {'detail': 'Only a super admin can change delivery charges.'},
                status=status.HTTP_403_FORBIDDEN,
            )
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
        for field in charges:
            amount = _clean_delivery_charge(request.data.get(field))
            if amount is None:
                return Response(
                    {'detail': 'Enter a delivery charge between 0 and 10,000 taka.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            setattr(settings, field, amount)
            updated = True
        if 'logo' in request.FILES:
            settings.logo = request.FILES['logo']
            updated = True
        if 'default_directory_banner' in request.FILES:
            settings.default_directory_banner = request.FILES['default_directory_banner']
            updated = True
        clear_banner = str(request.data.get('clear_default_directory_banner') or '').lower()
        if clear_banner in {'1', 'true', 'yes'}:
            if settings.default_directory_banner:
                settings.default_directory_banner.delete(save=False)
            settings.default_directory_banner = None
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
