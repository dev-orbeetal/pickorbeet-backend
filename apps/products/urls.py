"""
URL patterns for products app.
"""
from django.urls import path
from .views import (
    CategoryListView, CategoryDetailView, SubCategoryListView,
    ProductListView, ProductDetailView, ProductReviewView, FeaturedProductsView, CategoryProductsView,
    HomepageBannerListView, HomepageConfigView, CatalogIndexView,
    AdminHomepageBannerListCreateView, AdminHomepageBannerDetailView,
    AdminCategoryListCreateView, AdminCategoryDetailView,
    AdminSubCategoryListCreateView, AdminSubCategoryDetailView,
    AdminProductListCreateView, AdminProductDetailView,
    ProductImageUploadView, ProductImageDeleteView,
    BarcodeSearchView, ProductStockUpdateView, LowStockProductsView,
    ProductVariantListCreateView, ProductVariantDetailView, VariantSetupView,
    VariantStockUpdateView, InventoryItemsView,
    StoreSettingsView, PublicStoreSettingsView,
    PublicContactSubmitView, AdminContactMessageListView, AdminContactMessageDetailView
)

urlpatterns = [
    # Public endpoints
    path('categories/', CategoryListView.as_view(), name='category_list'),
    path('categories/<slug:slug>/', CategoryDetailView.as_view(), name='category_detail'),
    path('categories/<slug:category_slug>/subcategories/', SubCategoryListView.as_view(), name='subcategory_list'),
    path('', ProductListView.as_view(), name='product_list'),
    path('banners/', HomepageBannerListView.as_view(), name='homepage_banners'),
    path('homepage/', HomepageConfigView.as_view(), name='homepage_config'),
    path('catalog-index/', CatalogIndexView.as_view(), name='catalog_index'),
    path('featured/', FeaturedProductsView.as_view(), name='featured_products'),
    path('by-category/', CategoryProductsView.as_view(), name='products_by_category'),
    path('settings/public/', PublicStoreSettingsView.as_view(), name='public_store_settings'),
    path('<slug:slug>/reviews/', ProductReviewView.as_view(), name='product_reviews'),
    path('<slug:slug>/', ProductDetailView.as_view(), name='product_detail'),
    
    # Admin endpoints
    path('admin/categories/', AdminCategoryListCreateView.as_view(), name='admin_category_list'),
    path('admin/categories/<uuid:pk>/', AdminCategoryDetailView.as_view(), name='admin_category_detail'),
    path('admin/subcategories/', AdminSubCategoryListCreateView.as_view(), name='admin_subcategory_list'),
    path('admin/subcategories/<uuid:pk>/', AdminSubCategoryDetailView.as_view(), name='admin_subcategory_detail'),
    path('admin/products/', AdminProductListCreateView.as_view(), name='admin_product_list'),
    path('admin/products/<uuid:pk>/', AdminProductDetailView.as_view(), name='admin_product_detail'),
    path('admin/products/<uuid:product_id>/images/', ProductImageUploadView.as_view(), name='product_image_upload'),
    path('admin/products/<uuid:product_id>/variant-setup/', VariantSetupView.as_view(), name='product_variant_setup'),
    path('admin/products/<uuid:product_id>/variants/', ProductVariantListCreateView.as_view(), name='product_variant_list'),
    path('admin/products/<uuid:product_id>/variants/<uuid:pk>/', ProductVariantDetailView.as_view(), name='product_variant_detail'),
    path('admin/images/<uuid:pk>/', ProductImageDeleteView.as_view(), name='product_image_delete'),
    path('admin/barcode-search/', BarcodeSearchView.as_view(), name='barcode_search'),
    path('admin/products/<uuid:pk>/stock/', ProductStockUpdateView.as_view(), name='product_stock_update'),
    path('admin/low-stock/', LowStockProductsView.as_view(), name='low_stock_products'),
    path('admin/variants/<uuid:variant_id>/stock/', VariantStockUpdateView.as_view(), name='variant_stock_update'),
    path('admin/inventory/', InventoryItemsView.as_view(), name='inventory_items'),
    path('admin/settings/', StoreSettingsView.as_view(), name='store_settings'),
    path('admin/banners/', AdminHomepageBannerListCreateView.as_view(), name='admin_banner_list'),
    path('admin/banners/<uuid:pk>/', AdminHomepageBannerDetailView.as_view(), name='admin_banner_detail'),
    
    # Contact messages
    path('contact/', PublicContactSubmitView.as_view(), name='contact_submit'),
    path('admin/contact/', AdminContactMessageListView.as_view(), name='admin_contact_list'),
    path('admin/contact/<uuid:pk>/', AdminContactMessageDetailView.as_view(), name='admin_contact_detail'),
]
