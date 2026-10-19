"""
Admin configuration for products app.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Category, SubCategory, Product, ProductImage, ProductVariant, StoreSettings,
    HomepageBanner, HomepageSection, HomepageSectionProduct, HomepageBenefit,
)


class SubCategoryInline(admin.TabularInline):
    model = SubCategory
    extra = 1
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'display_order', 'is_active', 'product_count', 'image_preview']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['display_order', 'name']
    inlines = [SubCategoryInline]

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" />', obj.image.url)
        return '-'
    image_preview.short_description = 'Image'


@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'slug', 'display_order', 'is_active', 'product_count']
    list_filter = ['is_active', 'category']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['category', 'display_order', 'name']


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'category', 'subcategory', 'price', 'stock_quantity', 
                    'stock_status', 'is_active', 'is_featured', 'image_preview']
    list_filter = ['is_active', 'is_featured', 'category', 'subcategory', 'size', 'color']
    search_fields = ['name', 'sku', 'barcode', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['barcode_image']
    ordering = ['-created_at']
    inlines = [ProductImageInline, ProductVariantInline]
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'slug', 'sku', 'barcode', 'barcode_image')
        }),
        ('Category', {
            'fields': ('category', 'subcategory')
        }),
        ('Description', {
            'fields': ('short_description', 'description')
        }),
        ('Pricing', {
            'fields': ('price', 'compare_price', 'cost_price')
        }),
        ('Attributes', {
            'fields': ('size', 'color', 'material')
        }),
        ('Inventory', {
            'fields': ('stock_quantity', 'low_stock_threshold')
        }),
        ('Status', {
            'fields': ('is_active', 'is_featured')
        }),
    )

    def stock_status(self, obj):
        if obj.is_out_of_stock:
            return format_html('<span style="color: red; font-weight: bold;">Out of Stock</span>')
        elif obj.is_low_stock:
            return format_html('<span style="color: orange; font-weight: bold;">Low Stock ({})</span>', obj.stock_quantity)
        return format_html('<span style="color: green;">In Stock ({})</span>', obj.stock_quantity)
    stock_status.short_description = 'Stock Status'

    def image_preview(self, obj):
        if obj.primary_image:
            return format_html('<img src="{}" width="50" height="50" />', obj.primary_image)
        return '-'
    image_preview.short_description = 'Image'


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['product', 'is_primary', 'display_order', 'image_preview']
    list_filter = ['is_primary']
    search_fields = ['product__name']

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" />', obj.image.url)
        return '-'
    image_preview.short_description = 'Preview'


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['product', 'sku', 'size', 'color', 'price', 'stock_quantity', 'is_active']
    list_filter = ['is_active', 'size', 'color']
    search_fields = ['product__name', 'sku', 'barcode']


@admin.register(HomepageBanner)
class HomepageBannerAdmin(admin.ModelAdmin):
    list_display = ['placement', 'title', 'display_order', 'is_active', 'link', 'image_preview']
    list_filter = ['placement', 'is_active']
    list_editable = ['display_order', 'is_active']
    ordering = ['placement', 'display_order']
    fields = ['image', 'title', 'subtitle', 'button_label', 'link', 'placement', 'display_order', 'is_active']

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="80" height="40" style="object-fit:cover" />', obj.image.url)
        return '-'
    image_preview.short_description = 'Preview'


class HomepageSectionProductInline(admin.TabularInline):
    model = HomepageSectionProduct
    extra = 0
    autocomplete_fields = ['product']
    ordering = ['display_order']


@admin.register(HomepageSection)
class HomepageSectionAdmin(admin.ModelAdmin):
    list_display = ['title', 'key', 'section_type', 'is_enabled', 'display_order', 'item_limit', 'product_source']
    list_filter = ['section_type', 'is_enabled', 'product_source']
    list_editable = ['is_enabled', 'display_order', 'item_limit']
    search_fields = ['title', 'key', 'subtitle']
    prepopulated_fields = {'key': ('title',)}
    inlines = [HomepageSectionProductInline]
    fieldsets = (
        (None, {'fields': ('title', 'key', 'section_type', 'subtitle', 'is_enabled', 'display_order')}),
        ('Product row', {'fields': ('product_source', 'item_limit', 'view_all_label', 'view_all_url')}),
    )


@admin.register(HomepageBenefit)
class HomepageBenefitAdmin(admin.ModelAdmin):
    list_display = ['title', 'description', 'icon', 'display_order', 'is_active']
    list_editable = ['display_order', 'is_active']
    list_filter = ['is_active']
    search_fields = ['title', 'description']


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    list_display = ['barcode_prefix', 'updated_at']
    
    def has_add_permission(self, request):
        # Only allow one instance
        return not StoreSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False
