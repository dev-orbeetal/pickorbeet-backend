"""Who a campaign reaches. Customers who turned offers off are never included."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.notifications.models import Device, Notification
from apps.orders.models import OrderItem

from .models import (
    AUDIENCE_ALL,
    AUDIENCE_BUYERS,
    AUDIENCE_CART,
    AUDIENCE_CUSTOMERS,
    AUDIENCE_INTERESTED,
    AUDIENCE_WISHLIST,
    Campaign,
)

User = get_user_model()

UNSOLD_ORDER_STATUSES = ('cancelled', 'refunded')


class AudienceError(ValueError):
    pass


def _customers():
    return User.objects.filter(role='customer', is_active=True).exclude(notification_preference__offers=False)


def audience_users(*, audience, product=None, category=None, customer_ids=(), daily_cap=None):
    """Customers for ``audience``. With ``daily_cap``, people who already had that many
    automated product notifications in the last 24 hours are left out."""
    users = _customers()
    if audience == AUDIENCE_ALL:
        pass
    elif audience in {AUDIENCE_INTERESTED, AUDIENCE_WISHLIST, AUDIENCE_CART}:
        if product is None:
            raise AudienceError('Choose a product to find the customers interested in it.')
        saved = Q(wishlist_items__product=product)
        in_cart = Q(cart__items__product=product)
        users = users.filter({AUDIENCE_INTERESTED: saved | in_cart, AUDIENCE_WISHLIST: saved, AUDIENCE_CART: in_cart}[audience])
    elif audience == AUDIENCE_BUYERS:
        category = category or (product.category if product is not None else None)
        if category is None:
            raise AudienceError('Choose a product or a category to find its past buyers.')
        bought = OrderItem.objects.filter(order__user=OuterRef('pk'), product__category=category).exclude(
            order__order_status__in=UNSOLD_ORDER_STATUSES)
        users = users.filter(Exists(bought))
    elif audience == AUDIENCE_CUSTOMERS:
        ids = [str(value) for value in customer_ids or ()]
        if not ids:
            raise AudienceError('Choose at least one customer.')
        users = users.filter(pk__in=ids)
    else:
        raise AudienceError(f'Unknown audience {audience!r}.')

    if daily_cap is not None:
        recent = (
            Notification.objects.filter(
                recipient=OuterRef('pk'),
                campaign__source=Campaign.SOURCE_AUTOMATION,
                created_at__gte=timezone.now() - timedelta(hours=24),
            )
            .values('recipient')
            .annotate(total=Count('pk'))
            .values('total')
        )
        users = users.annotate(
            recent_automated=Coalesce(Subquery(recent, output_field=IntegerField()), Value(0)),
        ).filter(recent_automated__lt=daily_cap)
    return users.distinct()


def for_campaign(campaign, *, daily_cap=None):
    return audience_users(
        audience=campaign.audience,
        product=campaign.product,
        category=campaign.category,
        customer_ids=campaign.customer_ids,
        daily_cap=daily_cap,
    )


def reach(users):
    """How many customers get the inbox row, and how many of them have a phone for the push."""
    with_phone = Device.objects.filter(user=OuterRef('pk'), is_active=True).exclude(token='')
    return {
        'recipients': users.count(),
        'reachable': users.filter(Exists(with_phone)).count(),
    }
