"""Build the public homepage payload from admin configuration."""
from django.db.models import F

from .models import HomepageBanner, HomepageBenefit, HomepageSection, Product
from .serializers import HomepageBannerSerializer, ProductListSerializer


def _products_for(section):
    assigned = [
        item.product
        for item in section.section_products.select_related('product').order_by('display_order')
        if item.product.is_active
    ]
    if assigned:
        return assigned[:section.item_limit]

    queryset = Product.objects.filter(is_active=True)
    source = section.product_source
    if source == 'on_sale':
        queryset = queryset.filter(compare_price__isnull=False, compare_price__gt=F('price'))
    elif source == 'featured':
        queryset = queryset.filter(is_featured=True)
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
