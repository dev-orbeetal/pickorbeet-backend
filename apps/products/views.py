"""
Views for products app.
"""
from rest_framework import generics, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.db import models
from django.db.models import Q
from .models import Category, SubCategory, Product, ProductImage, ProductVariant
from .serializers import (
    CategorySerializer, CategoryListSerializer, SubCategorySerializer,
    ProductListSerializer, ProductDetailSerializer, ProductCreateUpdateSerializer,
    ProductImageSerializer, ProductVariantSerializer, BarcodeProductSerializer,
    ProductStockUpdateSerializer
)
from apps.accounts.permissions import IsStaffUser, IsSeller


# Public Views
class CategoryListView(generics.ListAPIView):
    """List all active categories with subcategories."""
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        return Category.objects.filter(is_active=True).prefetch_related('subcategories')


class CategoryDetailView(generics.RetrieveAPIView):
    """Retrieve single category with products."""
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    
    def get_queryset(self):
        return Category.objects.filter(is_active=True)


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


class ProductListView(generics.ListAPIView):
    """List products with filtering and search."""
    serializer_class = ProductListSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['subcategory', 'is_featured', 'color']
    search_fields = ['name', 'description', 'sku']
    ordering_fields = ['price', 'created_at', 'name']

    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True).select_related('category', 'subcategory')
        
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
        
        return queryset


class ProductDetailView(generics.RetrieveAPIView):
    """Retrieve single product with full details."""
    serializer_class = ProductDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    
    def get_queryset(self):
        return Product.objects.filter(is_active=True).prefetch_related('images', 'variants')


class FeaturedProductsView(generics.ListAPIView):
    """List featured products for homepage."""
    serializer_class = ProductListSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        return Product.objects.filter(is_active=True, is_featured=True)[:12]


class CategoryProductsView(generics.ListAPIView):
    """List products grouped by category for homepage."""
    permission_classes = [AllowAny]

    def get(self, request):
        categories = Category.objects.filter(is_active=True)[:6]
        result = []
        for category in categories:
            products = Product.objects.filter(
                category=category, is_active=True
            )[:4]
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
        return Product.objects.all().select_related('category', 'subcategory')


class AdminProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Admin: Retrieve, update, delete product."""
    permission_classes = [IsAuthenticated, IsStaffUser]
    queryset = Product.objects.all()

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ProductCreateUpdateSerializer
        return ProductDetailSerializer


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
    """Search product by barcode for POS."""
    permission_classes = [IsAuthenticated, IsSeller]

    def get(self, request):
        barcode = request.query_params.get('barcode')
        if not barcode:
            return Response(
                {'error': 'Barcode is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            product = Product.objects.get(Q(barcode=barcode) | Q(sku=barcode))
            return Response(BarcodeProductSerializer(product).data)
        except Product.DoesNotExist:
            # Try variants
            try:
                variant = ProductVariant.objects.get(barcode=barcode)
                return Response({
                    'id': str(variant.product.id),
                    'variant_id': str(variant.id),
                    'name': f"{variant.product.name} - {variant.size} - {variant.color}",
                    'sku': variant.sku,
                    'barcode': variant.barcode,
                    'price': float(variant.effective_price),
                    'stock_quantity': variant.stock_quantity,
                })
            except ProductVariant.DoesNotExist:
                return Response(
                    {'error': 'Product not found'},
                    status=status.HTTP_404_NOT_FOUND
                )


class ProductStockUpdateView(APIView):
    """Update product stock."""
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
        
        if operation == 'add':
            product.stock_quantity += quantity
        elif operation == 'subtract':
            if product.stock_quantity < quantity:
                return Response(
                    {'error': 'Insufficient stock'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            product.stock_quantity -= quantity
        else:  # set
            product.stock_quantity = quantity
        
        product.save()
        return Response({
            'message': 'Stock updated successfully',
            'new_stock': product.stock_quantity
        })


class LowStockProductsView(generics.ListAPIView):
    """List products with low stock."""
    serializer_class = ProductListSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get_queryset(self):
        return Product.objects.filter(
            stock_quantity__lte=models.F('low_stock_threshold'),
            is_active=True
        ).order_by('stock_quantity')


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


class PublicStoreSettingsView(APIView):
    """Public endpoint for client to fetch store settings (no auth required)."""
    permission_classes = [AllowAny]

    def get(self, request):
        from .models import StoreSettings
        settings = StoreSettings.get_settings()
        return Response({
            'popular_searches': settings.popular_searches,
            'contact_address': settings.contact_address,
            'contact_phone_1': settings.contact_phone_1,
            'contact_phone_2': settings.contact_phone_2,
            'contact_email_1': settings.contact_email_1,
            'contact_email_2': settings.contact_email_2,
            'business_hours': settings.business_hours,
            'map_embed_url': settings.map_embed_url,
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

    def get(self, request):
        from .models import StoreSettings
        settings = StoreSettings.get_settings()
        data = {field: getattr(settings, field) for field in self.SETTINGS_FIELDS}
        return Response(data)

    def patch(self, request):
        from .models import StoreSettings
        settings = StoreSettings.get_settings()
        
        updated = False
        for field in self.SETTINGS_FIELDS:
            value = request.data.get(field)
            if value is not None:
                setattr(settings, field, value)
                updated = True
        
        if updated:
            settings.save()
        
        data = {field: getattr(settings, field) for field in self.SETTINGS_FIELDS}
        data['message'] = 'Settings updated successfully'
        return Response(data)
