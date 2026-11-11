"""Taka added to a scraped shop price before that product is listed.

The bands are the selling price, and the same amount is added to the compare
price when the product has one, so the discount gap stays the same. A missing
price (0) is left alone. Above 20,000 and through 150,000 the add is 500,
except 15,000–20,000 which is 600.
"""
from decimal import Decimal

CENT = Decimal('0.01')

# Upper bound of each band is exclusive. 15,000–20,000 is handled after these.
_BANDS = (
    (Decimal('1000'), Decimal('50')),
    (Decimal('2000'), Decimal('100')),
    (Decimal('3000'), Decimal('200')),
    (Decimal('4000'), Decimal('250')),
    (Decimal('6000'), Decimal('300')),
    (Decimal('10000'), Decimal('400')),
    (Decimal('15000'), Decimal('500')),
)


def catalog_price_increase(price):
    """How many taka to add to a scraped selling price."""
    amount = Decimal(price)
    if amount <= 0:
        return Decimal('0')
    for limit, increase in _BANDS:
        if amount < limit:
            return increase
    if amount <= Decimal('20000'):
        return Decimal('600')
    return Decimal('500')


def raised_catalog_prices(price, compare_price):
    """Return the listed price and compare price after the catalog add."""
    increase = catalog_price_increase(price)
    listed = (Decimal(price) + increase).quantize(CENT)
    if compare_price is None:
        return listed, None
    return listed, (Decimal(compare_price) + increase).quantize(CENT)
