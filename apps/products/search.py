"""Product search that also understands category and subcategory names."""
from django.db.models import Q

from .models import Category, SubCategory

# A one- or two-letter fragment matches too many names ("a" is inside "Banks").
_CATALOG_CONTAINS_MIN = 3


def normalize_search(value):
    """Collapse whitespace and treat commas as spaces, matching DRF's search terms."""
    if not value:
        return ''
    return ' '.join(str(value).replace('\x00', '').replace(',', ' ').split())


def search_names_catalog(value):
    """True when the query is exactly a category or subcategory name."""
    phrase = normalize_search(value)
    if not phrase:
        return False
    return (
        Category.objects.filter(name__iexact=phrase).exists()
        or SubCategory.objects.filter(name__iexact=phrase).exists()
    )


def _catalog_products(phrase):
    """Products whose category or subcategory name is, or contains, the phrase."""
    if len(phrase) >= _CATALOG_CONTAINS_MIN:
        categories = Category.objects.filter(name__icontains=phrase)
        subcategories = SubCategory.objects.filter(name__icontains=phrase)
    else:
        categories = Category.objects.filter(name__iexact=phrase)
        subcategories = SubCategory.objects.filter(name__iexact=phrase)
    return Q(category_id__in=categories.values('id')) | Q(subcategory_id__in=subcategories.values('id'))


def filter_product_search(queryset, raw):
    """Name, description, and SKU search, plus every product under a named category."""
    phrase = normalize_search(raw)
    if not phrase:
        return queryset

    text = Q()
    for term in phrase.split(' '):
        text &= Q(name__icontains=term) | Q(description__icontains=term) | Q(sku__icontains=term)
    return queryset.filter(text | _catalog_products(phrase))
