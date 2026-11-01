"""Build the public homepage payload from admin configuration."""
from django.db.models import F, Prefetch

from .models import (
    HomepageBanner, HomepageBenefit, HomepageSection, HomepageSectionProduct,
    Product, with_catalog_stats,
)
from .serializers import HomepageBannerSerializer, ProductListSerializer

# Keys the admin panel manages as curated product rows.
CURATED_PRODUCT_SECTION_DEFAULTS = (
    {
        'key': 'trending',
        'title': 'Trending Products',
        'display_order': 5,
        'item_limit': 8,
        'view_all_label': 'View All',
        'view_all_url': '/products?featured=true',
        'product_source': 'featured',
    },
    {
        'key': 'new-arrivals',
        'title': 'New Arrivals',
        'display_order': 6,
        'item_limit': 8,
        'view_all_label': 'View All',
        'view_all_url': '/products',
        'product_source': 'latest',
    },
)


def ensure_curated_product_sections():
    """Create the default trending / new-arrivals rows if they are missing."""
    sections = []
    for defaults in CURATED_PRODUCT_SECTION_DEFAULTS:
        section, _ = HomepageSection.objects.get_or_create(
            key=defaults['key'],
            defaults={
                'section_type': 'products',
                'title': defaults['title'],
                'subtitle': '',
                'is_enabled': True,
                'display_order': defaults['display_order'],
                'item_limit': defaults['item_limit'],
                'view_all_label': defaults['view_all_label'],
                'view_all_url': defaults['view_all_url'],
                'product_source': defaults['product_source'],
            },
        )
        sections.append(section)

    # Empty "custom list" trending is not useful — use Featured toggles instead.
    trending = next((section for section in sections if section.key == 'trending'), None)
    if (
        trending
        and trending.product_source == 'manual'
        and not trending.section_products.exists()
    ):
        trending.product_source = 'featured'
        trending.view_all_url = trending.view_all_url or '/products?featured=true'
        trending.save(update_fields=['product_source', 'view_all_url'])
    return sections


def curated_product_sections_queryset():
    ensure_curated_product_sections()
    keys = [row['key'] for row in CURATED_PRODUCT_SECTION_DEFAULTS]
    return HomepageSection.objects.filter(
        key__in=keys, section_type='products'
    ).prefetch_related(
        Prefetch(
            'section_products',
            queryset=HomepageSectionProduct.objects.select_related('product').order_by('display_order'),
        )
    ).order_by('display_order', 'title')


def _ordered_products(products, limit):
    ids = [product.id for product in products[:limit]]
    indexed = {
        product.id: product
        for product in with_catalog_stats(Product.objects.filter(id__in=ids))
    }
    return [indexed[product_id] for product_id in ids if product_id in indexed]


def _products_for(section):
    source = section.product_source
    assigned = [
        item.product
        for item in section.section_products.select_related('product').order_by('display_order')
        if item.product.is_active
    ]

    # Custom list: only show what admin picked (empty list = hide the row's products).
    if source == 'manual':
        return _ordered_products(assigned, section.item_limit) if assigned else []

    # Curated picks still win for featured / on_sale when present.
    if assigned:
        return _ordered_products(assigned, section.item_limit)

    queryset = with_catalog_stats(Product.objects.filter(is_active=True))
    if source == 'on_sale':
        queryset = queryset.filter(compare_price__isnull=False, compare_price__gt=F('price'))
    elif source == 'featured':
        queryset = queryset.filter(is_featured=True).order_by('-updated_at', '-created_at')
        return list(queryset[:section.item_limit])
    return list(queryset.order_by('-created_at')[:section.item_limit])


def build_homepage(request):
    banners = HomepageBanner.objects.filter(is_active=True)
    banner_data = HomepageBannerSerializer(banners, many=True, context={'request': request}).data
    heroes = [banner for banner in banner_data if banner['placement'] == 'hero']
    promos = [banner for banner in banner_data if banner['placement'] == 'promo']
    benefits = [
        {
            'id': str(item.id),
            'title': item.title,
            'description': item.description,
            'icon': item.icon,
        }
        for item in HomepageBenefit.objects.filter(is_active=True)
    ]

    sections = []
    for section in HomepageSection.objects.filter(is_enabled=True):
        payload = {
            'key': section.key,
            'type': section.section_type,
            'title': section.title,
            'subtitle': section.subtitle,
            'view_all_label': section.view_all_label,
            'view_all_url': section.view_all_url,
        }
        if section.section_type == 'hero':
            payload['banners'] = heroes
        elif section.section_type == 'promos':
            payload['banners'] = promos
        elif section.section_type == 'benefits':
            payload['items'] = benefits
        elif section.section_type == 'products':
            payload['products'] = ProductListSerializer(
                _products_for(section), many=True, context={'request': request}
            ).data
        sections.append(payload)
    return {'sections': sections}
