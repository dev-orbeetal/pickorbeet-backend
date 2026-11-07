"""
Coupon pricing for the cart lines a shopper is buying.

A coupon limited to products or categories discounts only the lines it covers,
and its minimum spend counts only those lines.
"""
from decimal import Decimal

ZERO = Decimal('0')
NOT_COVERED = "This voucher doesn't apply to the items you selected."


def coupon_scope(coupon):
    """(product ids, category ids) the coupon is limited to; both empty means the whole shop."""
    return (
        set(coupon.applicable_products.values_list('id', flat=True)),
        set(coupon.applicable_categories.values_list('id', flat=True)),
    )


def qualifying_subtotal(coupon, lines, scope=None):
    """Total of the cart lines the coupon covers."""
    product_ids, category_ids = scope if scope is not None else coupon_scope(coupon)
    if not (product_ids or category_ids):
        return sum((line.total_price for line in lines), ZERO)
    return sum(
        (
            line.total_price for line in lines
            if line.product_id in product_ids or line.product.category_id in category_ids
        ),
        ZERO,
    )


def quote_coupon(coupon, user, lines, scope=None):
    """(discount, None) when the coupon applies to these lines for this shopper, else (0, reason)."""
    base = qualifying_subtotal(coupon, lines, scope)
    if base <= 0:
        return ZERO, NOT_COVERED
    can_use, message = coupon.can_be_used_by(user, base)
    if not can_use:
        return ZERO, message
    return coupon.calculate_discount(base), None
