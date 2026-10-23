"""
Small builders shared by the orders and shipping tests.
"""
import shutil
import tempfile
from decimal import Decimal
from itertools import count

from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.orders.models import Order, OrderItem, OrderStatusHistory
from apps.products.models import Category, Product

_seq = count(1)


class ShopTestCase(TestCase):
    """Keeps generated barcode images out of the real media folder."""

    @classmethod
    def setUpClass(cls):
        cls._media = tempfile.mkdtemp(prefix='pob-test-media-')
        cls._media_override = override_settings(MEDIA_ROOT=cls._media)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls._media, ignore_errors=True)

    def setUp(self):
        super().setUp()
        cache.clear()  # throttle counters live in the cache


def make_user(role='customer', **fields):
    n = next(_seq)
    defaults = {'first_name': 'Rakibul', 'last_name': 'Hasan', 'role': role, 'is_verified': True}
    defaults.update(fields)
    email = defaults.pop('email', f'user{n}@example.com')
    return User.objects.create_user(email=email, password='Str0ng-pass!', **defaults)


def make_product(name=None, price='1599.00', compare_price='1999.00', stock=10, **fields):
    n = next(_seq)
    category = fields.pop('category', None) or Category.objects.create(name=f'Electronics {n}')
    return Product.objects.create(
        name=name or f'boAt Airdopes {n}',
        sku=f'SKU-{n}',
        category=category,
        price=Decimal(price),
        compare_price=Decimal(compare_price) if compare_price else None,
        stock_quantity=stock,
        **fields,
    )


def make_order(user=None, products=None, status='pending', payment_status='pending', order_type='online',
               **fields):
    defaults = {
        'shipping_name': 'Rakibul Hasan',
        'shipping_phone': '+880 1712 345678',
        'shipping_address_line1': 'House 12, Road 4',
        'shipping_address_line2': 'Malibagh',
        'shipping_city': 'Dhaka',
        'shipping_district': 'Dhaka',
        'shipping_postal_code': '1217',
    }
    defaults.update(fields)
    products = products if products is not None else [make_product()]
    subtotal = sum((p.price for p in products), Decimal('0'))
    order = Order.objects.create(
        user=user,
        order_type=order_type,
        order_status=status,
        payment_status=payment_status,
        subtotal=subtotal,
        **defaults,
    )
    for product in products:
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            product_sku=product.sku,
            quantity=1,
            unit_price=product.price,
            compare_price=product.compare_price,
        )
    OrderStatusHistory.objects.create(order=order, status=status, note='Order placed')
    return order
