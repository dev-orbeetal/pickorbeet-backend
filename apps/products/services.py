"""
Product-domain helpers shared by views and serializers.
"""
from apps.orders.models import OrderItem


def user_can_review_product(user, product) -> bool:
    """True when the shopper has a delivered order that includes ``product``."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    return OrderItem.objects.filter(
        order__user=user,
        order__order_status='delivered',
        product=product,
    ).exists()
