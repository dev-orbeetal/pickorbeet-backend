"""
Load a demo store that mirrors the app and web designs, for local development.

Re-running is safe: catalog rows are matched by name or SKU, orders by order number.
Generated media goes to MEDIA_ROOT/demo/, which is git-ignored.
"""
import shutil
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import barcode
from barcode.writer import ImageWriter
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Address, User
from apps.orders.models import Cart, CartItem, Coupon, CouponUsage, Order, OrderItem, OrderStatusHistory
from apps.products.models import (
    Category, HomepageBanner, HomepageBenefit, HomepageSection, HomepageSectionProduct, Product,
    ProductImage, SubCategory,
)
from apps.shipping.models import Shipment, ShipmentEvent
from apps.shipping.services import tracking_url_for

ASSETS = Path(__file__).resolve().parents[2] / 'demo_assets'
DHAKA = ZoneInfo('Asia/Dhaka')
PASSWORD = 'Demo@12345'


def at(y, m, d, hh=10, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=DHAKA)


CATEGORIES = [
    # name, image, description, tagline
    ('Electronics', 'category-electronics.png', 'Earbuds, neckbands, power banks, and chargers.',
     'Latest Gadgets for Your Everyday Life'),
    ('Fashion', 'category-fashion.png', 'Jackets, sweaters, and winter accessories.', 'Winter Collections'),
    ('Mobile & Accessories', 'category-mobile-accessories.png', 'Phones, stands, cases, and cables.', ''),
    ('Computer & Accessories', 'category-computer-accessories.png', 'Laptops, keyboards, and mice.', ''),
    ('Home & Living', 'category-home-living.png', 'Furniture, lighting, and decor.', ''),
    ('Beauty & Personal Care', 'category-beauty-personal-care.png', 'Skin care and grooming.', ''),
    ('Groceries', 'category-groceries.png', 'Fresh produce and pantry staples.', ''),
    ('Sports & Fitness', 'category-sports-fitness.png', 'Weights, bottles, and training gear.', ''),
    ('Toys & Baby', 'category-toys-baby.png', 'Toys and baby essentials.', ''),
    ('Automotive', 'category-automotive.png', 'Car care and accessories.', ''),
    ('Books & Stationery', 'category-books-stationery.png', 'Books, notebooks, and pens.', ''),
    ('Health & Wellness', 'category-health-wellness.png', 'First aid and everyday health.', ''),
]

# Electronics tiles reuse the store's own images; the Fashion tiles come from the design.
SUBCATEGORIES = {
    'Electronics': [
        ('TWS', 'media:subcategories/Screenshot_From_2026-10-22_12-21-36.png'),
        ('Power Banks', 'media:subcategories/Screenshot_From_2026-10-22_12-21-41.png'),
        ('Adapter', 'media:subcategories/Screenshot_From_2026-10-22_12-21-53.png'),
        ('Neckbands', 'media:subcategories/Screenshot_From_2026-10-22_12-21-48.png', 'Wireless comfort, all day'),
    ],
    'Fashion': [
        ('Jacket', 'subcategory-jacket.png'),
        ('Sweater', 'subcategory-sweater.png'),
        ('Gloves', 'subcategory-gloves.png'),
        ('Socks', 'subcategory-socks.png'),
    ],
}

PRODUCTS = [
    {
        'sku': 'DEMO-BOAT-AD141', 'name': 'boAt Airdopes 141', 'category': 'Electronics', 'sub': 'TWS',
        'price': '1599', 'compare': '1999', 'color': 'Black', 'stock': 48,
        'image': 'product-boat-airdopes-141.png', 'short': 'True Wireless Earbuds',
        'description': 'boAt Airdopes 141 true wireless earbuds.\n\nUp to 42 hours of total playback with the case, '
                       'ENx noise reduction for clear calls, BEAST mode for low-latency gaming, '
                       'IPX4 sweat resistance, and Bluetooth 5.1. USB-C charging.',
    },
    {
        'sku': 'DEMO-MI-PB20K', 'name': 'Mi Power Bank 20000mAh', 'category': 'Electronics', 'sub': 'Power Banks',
        'price': '2099', 'compare': '2499', 'color': 'Black', 'stock': 32,
        'image': 'product-mi-power-bank-20000.png', 'short': 'Fast Charging, USB-C',
        'description': 'Mi Power Bank 20000mAh.\n\n18W two-way fast charging, USB-C and micro-USB input, '
                       'two USB-A outputs, and a low-power mode for earbuds and smart watches.',
    },
    {
        'sku': 'DEMO-ANKER-65W', 'name': 'Anker 65W Charger', 'category': 'Electronics', 'sub': 'Adapter',
        'price': '2699', 'compare': '2999', 'color': 'White', 'stock': 20,
        'image': 'product-anker-65w-charger.png', 'short': '3 Port Fast Charger',
        'description': 'Anker 65W GaN charger.\n\nTwo USB-C ports and one USB-A port. Charges a laptop, phone, '
                       'and earbuds at once, with power shared automatically between ports.',
    },
    {
        'sku': 'DEMO-BOAT-R255', 'name': 'boAt Rockerz 255 Pro+', 'category': 'Electronics', 'sub': 'Neckbands',
        'price': '1799', 'compare': None, 'color': 'Black', 'stock': 26,
        'image': 'product-boat-rockerz-255-pro.png', 'short': 'Wireless Neckband',
        'description': 'boAt Rockerz 255 Pro+ wireless neckband.\n\nUp to 60 hours of playback, '
                       'ASAP fast charging, magnetic earbuds, and IPX7 water resistance.',
    },
    {
        'sku': 'DEMO-HAYLOU-RS4', 'name': 'Haylou RS4 Smart Watch', 'category': 'Electronics', 'sub': None,
        'price': '4499', 'compare': None, 'color': 'Black', 'stock': 14, 'featured': True,
        'image': 'product-haylou-rs4.png', 'short': 'AMOLED Smart Watch',
        'description': 'Haylou RS4 smart watch.\n\nAMOLED display, heart-rate and SpO2 monitoring, '
                       'sleep tracking, multiple sport modes, and IP68 water resistance.',
    },
    {
        'sku': 'DEMO-WINTER-JACKET', 'name': "Men's Winter Jacket", 'category': 'Fashion', 'sub': 'Jacket',
        'price': '3799', 'compare': None, 'color': 'Navy', 'stock': 18,
        'image': 'product-mens-winter-jacket.png', 'short': 'Hooded Puffer Jacket',
        'description': "Men's hooded puffer jacket.\n\nWater-resistant shell, warm padded lining, "
                       'faux-fur hood trim, and zipped pockets.',
    },
    {
        'sku': 'DEMO-UGREEN-STAND', 'name': 'UGREEN Phone Stand', 'category': 'Mobile & Accessories', 'sub': None,
        'price': '699', 'compare': None, 'color': 'Black', 'stock': 40,
        'image': 'product-ugreen-phone-stand.png', 'short': 'Adjustable Desk Stand',
        'description': 'UGREEN adjustable phone stand.\n\nAluminium build, adjustable viewing angle, '
                       'and an anti-slip base. Fits phones and small tablets.',
    },
    # The store's launch catalog, with its own product cutouts.
    {
        'sku': 'ANK-R50I', 'name': 'Anker Soundcore R50i True Wireless Earbuds', 'category': 'Electronics',
        'sub': 'TWS', 'price': '1550', 'compare': None, 'color': 'Black', 'stock': 30,
        'image': 'media:products/ank-r50i-cutout.png', 'short': 'True Wireless Earbuds',
        'description': 'Anker Soundcore R50i true wireless earbuds.\n\nBluetooth 5.3, 10mm drivers, '
                       'IPX5 water resistance, and up to 30 hours of playback with the case.',
    },
    {
        'sku': 'BAS-ADAMAN-20K', 'name': 'Baseus Adaman 22.5W 20000mAh Power Bank', 'category': 'Electronics',
        'sub': 'Power Banks', 'price': '1550', 'compare': '1999', 'color': 'Black', 'stock': 22,
        'image': 'media:products/bas-adaman-20k-cutout.png', 'short': '22.5W Fast Charge, Digital Display',
        'description': 'Baseus Adaman 22.5W 20000mAh power bank.\n\nUp to 22.5W output and a digital display '
                       'showing the remaining charge. USB-C charging.',
    },
    {
        'sku': 'HOC-EQ34P-BLK', 'name': 'Hoco EQ34 Plus Rima True Wireless Earbuds', 'category': 'Electronics',
        'sub': 'TWS', 'price': '599', 'compare': '850', 'color': 'Black', 'stock': 35,
        'image': 'media:products/hoc-eq34p-blk-cutout.png', 'short': 'Hybrid ANC, ENC Calls',
        'description': 'Hoco EQ34 Plus Rima true wireless earbuds.\n\nBluetooth 5.4, hybrid active noise '
                       'cancellation, and up to 28 hours of playback with the case.',
    },
    {
        'sku': 'HOC-J154A', 'name': 'Hoco J154A 22.5W + PD20W 20000mAh Power Bank', 'category': 'Electronics',
        'sub': 'Power Banks', 'price': '1450', 'compare': '1850', 'color': 'Black', 'stock': 16,
        'image': 'media:products/hoc-j154a-cutout.png', 'short': '22.5W and PD 20W Output',
        'description': 'Hoco J154A power bank.\n\n20000mAh capacity with 22.5W output and USB-C '
                       'Power Delivery at 20W.',
    },
    {
        'sku': 'ORA-OEB-311', 'name': 'Oraimo Necklace Lite (OEB-311)', 'category': 'Electronics',
        'sub': 'Neckbands', 'price': '1080', 'compare': '1500', 'color': 'Black', 'stock': 24,
        'image': 'media:products/ora-oeb-311-cutout.png', 'short': 'Up to 30 Hours of Playback',
        'description': 'Oraimo Necklace Lite wireless neckband, model OEB-311.\n\nBluetooth 5.3, call vibration '
                       'alerts, dual-device connection, and IPX4 sweat resistance.',
    },
]

BANNERS = [
    # placement, image, title, link, order
    ('hero', 'media:banners/Everything_You_Love_One_Place.png', 'Everything you love, one place', '/products', 1),
    ('hero', 'hero-upgrade-everyday.png', 'Upgrade your everyday: winter collections', '/category/fashion', 2),
    ('hero', 'media:banners/Cash_on_Delivery_Made_Easy.png', 'Cash on delivery made easy', '/products', 3),
    ('promo', 'promo-authentic.png', '100% real authentic products', '/products', 1),
    ('promo', 'promo-cash-on-delivery.png', 'No pre-payment, only cash on delivery', '/products', 2),
    # Side cards after the first two appear at the bottom of the app's Categories screen.
    ('promo', 'promo-everyday-essentials.png', 'Big savings on everyday essentials', '/category/groceries', 3),
]

SECTIONS = [
    # key, type, title, order, limit, view-all label, url, source
    ('hero', 'hero', 'Hero', 1, 5, '', '', 'manual'),
    ('promos', 'promos', 'Promotions', 2, 2, '', '', 'manual'),
    ('categories', 'categories', 'Categories', 3, 12, 'View All', '/categories', 'manual'),
    ('benefits', 'benefits', 'Benefits', 4, 4, '', '', 'manual'),
    ('trending', 'products', 'Trending Products', 5, 8, 'View All', '/products', 'manual'),
    ('new-arrivals', 'products', 'New Arrivals', 6, 8, 'View All', '/products', 'latest'),
]

BENEFITS = [
    ('100% Authentic', 'Original Products', 'shield'),
    ('Fast Delivery', 'All Over Bangladesh', 'truck'),
    ('Cash on Delivery', 'No Pre Payment', 'cash'),
    ('24/7 Support', 'Always Here', 'support'),
]

TRENDING = [
    'DEMO-BOAT-AD141', 'DEMO-HAYLOU-RS4', 'DEMO-ANKER-65W', 'DEMO-MI-PB20K',
    'DEMO-WINTER-JACKET', 'DEMO-BOAT-R255', 'DEMO-UGREEN-STAND', 'ANK-R50I',
]

CUSTOMERS = {
    'rakib': {
        'email': 'rakib@example.com', 'first_name': 'Rakibul', 'last_name': 'Hasan',
        'phone': '+880 1712 345678', 'address': 'House 12, Road 4, Malibagh', 'city': 'Dhaka',
        'postal_code': '1217',
        'addresses': [
            ('Home', 'Rakibul Hasan', '+880 1712 345678', 'House 12, Road 4', 'Malibagh', 'Dhaka', 'Dhaka', '1217', True),
            ('Office', 'Rakibul Hasan', '+880 1712 345678', 'Level 7, Rangs Babylonia', 'Tejgaon', 'Dhaka', 'Dhaka',
             '1208', False),
        ],
    },
    'nusrat': {
        'email': 'nusrat@example.com', 'first_name': 'Nusrat', 'last_name': 'Jahan',
        'phone': '+880 1812 345678', 'address': 'Holding 7, College Road, Chawkbazar', 'city': 'Chattogram',
        'postal_code': '4203',
        'addresses': [
            ('Home', 'Nusrat Jahan', '+880 1812 345678', 'Holding 7, College Road', 'Chawkbazar', 'Chattogram',
             'Chattogram', '4203', True),
        ],
    },
}

DESIGN_ITEMS = [('DEMO-BOAT-AD141', 1), ('DEMO-MI-PB20K', 1), ('DEMO-ANKER-65W', 1)]

# Each order: number, customer, placed at, items, order status, payment status, coupon, courier status,
# courier message. A courier status of None means the order was never booked.
ORDERS = [
    # Rakibul: 3 open, 12 delivered, 1 cancelled (the dashboard in the design).
    ('PO1234567', 'rakib', at(2025, 10, 22, 10, 24), DESIGN_ITEMS, 'shipped', 'pending', 'SAVE800', 'in_review', ''),
    ('PO1234552', 'rakib', at(2025, 10, 20, 18, 5), [('DEMO-BOAT-R255', 1)], 'shipped', 'pending', None, 'hold',
     'Customer asked for delivery on Saturday.'),
    ('PO1234589', 'rakib', at(2025, 10, 22, 21, 40), [('DEMO-UGREEN-STAND', 2)], 'pending', 'pending', None, None, ''),
    ('PO1234433', 'rakib', at(2025, 10, 2, 13, 15), [('DEMO-WINTER-JACKET', 1)], 'cancelled', 'pending', None,
     'cancelled', 'Customer refused to receive the parcel.'),
    ('PO1234118', 'rakib', at(2025, 5, 4, 11, 2), [('ANK-R50I', 1)], 'delivered', 'paid', None, None, ''),
    ('PO1234139', 'rakib', at(2025, 5, 19, 16, 45), [('HOC-J154A', 1)], 'delivered', 'paid', None, None, ''),
    ('PO1234165', 'rakib', at(2025, 6, 7, 9, 30), [('ORA-OEB-311', 1)], 'delivered', 'paid', None, 'delivered', ''),
    ('PO1234187', 'rakib', at(2025, 6, 23, 20, 12), [('HOC-EQ34P-BLK', 2)], 'delivered', 'paid', None,
     'partial_delivered', 'One item was returned by the customer.'),
    ('PO1234203', 'rakib', at(2025, 7, 5, 12, 0), [('BAS-ADAMAN-20K', 1)], 'delivered', 'paid', None, 'delivered', ''),
    ('PO1234226', 'rakib', at(2025, 7, 21, 17, 38), [('DEMO-HAYLOU-RS4', 1)], 'delivered', 'paid', None,
     'delivered', ''),
    ('PO1234251', 'rakib', at(2025, 8, 3, 10, 50), [('DEMO-MI-PB20K', 1), ('DEMO-BOAT-AD141', 1)], 'delivered',
     'paid', None, 'delivered', ''),
    ('PO1234274', 'rakib', at(2025, 8, 18, 15, 20), [('DEMO-ANKER-65W', 1)], 'delivered', 'paid', None,
     'delivered', ''),
    ('PO1234298', 'rakib', at(2025, 9, 1, 19, 5), [('DEMO-UGREEN-STAND', 1), ('ANK-R50I', 1)], 'delivered',
     'paid', None, 'delivered', ''),
    ('PO1234316', 'rakib', at(2025, 9, 14, 11, 40), [('ORA-OEB-311', 1)], 'delivered', 'paid', None,
     'delivered', ''),
    ('PO1234352', 'rakib', at(2025, 9, 27, 14, 25), [('DEMO-BOAT-R255', 1)], 'delivered', 'paid', None,
     'delivered', ''),
    ('PO1234391', 'rakib', at(2025, 10, 9, 18, 55), [('HOC-EQ34P-BLK', 1)], 'delivered', 'paid', None,
     'delivered', ''),
    # Nusrat: the remaining courier statuses, mostly approval-pending reports.
    ('PO1234602', 'nusrat', at(2025, 10, 21, 12, 10), [('DEMO-BOAT-AD141', 1)], 'shipped', 'pending', None,
     'pending', 'Parcel picked up from the merchant.'),
    ('PO1234615', 'nusrat', at(2025, 10, 19, 16, 30), [('BAS-ADAMAN-20K', 1)], 'shipped', 'pending', None,
     'unknown', ''),
    ('PO1234628', 'nusrat', at(2025, 10, 17, 10, 5), [('DEMO-HAYLOU-RS4', 1)], 'shipped', 'pending', None,
     'delivered_approval_pending', 'Delivered. Waiting for Steadfast to confirm.'),
    ('PO1234641', 'nusrat', at(2025, 10, 15, 19, 45), [('HOC-EQ34P-BLK', 2)], 'shipped', 'pending', None,
     'partial_delivered_approval_pending', 'One item was refused at the door.'),
    ('PO1234654', 'nusrat', at(2025, 10, 13, 9, 20), [('DEMO-WINTER-JACKET', 1)], 'shipped', 'pending', None,
     'cancelled_approval_pending', 'Customer was unreachable after three attempts.'),
    ('PO1234667', 'nusrat', at(2025, 10, 11, 14, 0), [('HOC-J154A', 1)], 'shipped', 'pending', None,
     'unknown_approval_pending', ''),
]

# Courier progress recorded before the final status, so timelines read naturally.
COURIER_STEPS = {
    'in_review': [],
    'pending': ['in_review'],
    'hold': ['in_review', 'pending'],
    'delivered': ['in_review', 'pending'],
    'partial_delivered': ['in_review', 'pending'],
    'cancelled': ['in_review', 'pending', 'hold'],
    'unknown': ['in_review', 'pending'],
    'delivered_approval_pending': ['in_review', 'pending'],
    'partial_delivered_approval_pending': ['in_review', 'pending'],
    'cancelled_approval_pending': ['in_review', 'pending', 'hold'],
    'unknown_approval_pending': ['in_review', 'pending'],
}


class Command(BaseCommand):
    help = 'Load a demo store that mirrors the app and web designs (DEBUG only).'

    def add_arguments(self, parser):
        parser.add_argument('--fresh-orders', action='store_true',
                            help='Delete and recreate the demo customers\' orders.')

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('seed_demo_store only runs with DEBUG=True. It creates demo accounts and orders.')
        with transaction.atomic():
            categories, subcategories = self.seed_categories()
            products = self.seed_products(categories, subcategories)
            self.seed_homepage(products)
            admin = self.seed_admin()
            customers = self.seed_customers()
            coupon = self.seed_coupon()
            self.seed_cart(customers['rakib'], products)
            self.seed_orders(customers, products, coupon, admin, fresh=options['fresh_orders'])
        self.stdout.write(self.style.SUCCESS('\nDemo store ready.'))
        self.stdout.write(f'  Customer: rakib@example.com / {PASSWORD}')
        self.stdout.write(f'  Customer: nusrat@example.com / {PASSWORD}')
        self.stdout.write(f'  Staff:    admin@example.com / {PASSWORD}')
        self.stdout.write('  Voucher:  SAVE800 (৳800 off orders of ৳5,000 or more)')
        self.stdout.write(self.style.WARNING(
            '  Demo shipments use made-up Steadfast consignment IDs. '
            'Do not run sync_shipments with real Steadfast keys against this data.'))

    # Files

    def demo_file(self, name, folder):
        """Copy a bundled asset into MEDIA_ROOT/demo/<folder>/ and return its storage name."""
        source = ASSETS / name
        target = Path(settings.MEDIA_ROOT) / 'demo' / folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.stat().st_size != source.stat().st_size:
            shutil.copyfile(source, target)
        return f'demo/{folder}/{name}'

    def image_name(self, ref, folder):
        """Resolve 'media:<path>' to an existing upload, or a bundled asset name to its demo copy."""
        if not ref:
            return None
        if ref.startswith('media:'):
            path = ref.removeprefix('media:')
            if (Path(settings.MEDIA_ROOT) / path).exists():
                return path
            self.stdout.write(self.style.WARNING(f'  Missing media file {path}; skipped.'))
            return None
        return self.demo_file(ref, folder)

    def barcode_name(self, sku):
        """Write the product's barcode image under demo/ so seeding leaves the tracked barcodes alone."""
        target = Path(settings.MEDIA_ROOT) / 'demo' / 'barcodes' / f'barcode_{sku}.png'
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            code = barcode.get_barcode_class('code128')(sku, writer=ImageWriter())
            with open(target, 'wb') as handle:
                code.write(handle)
        return f'demo/barcodes/barcode_{sku}.png'

    # Catalog

    def seed_categories(self):
        categories, subcategories = {}, {}
        for order, (name, image, description, tagline) in enumerate(CATEGORIES, start=1):
            category, _ = Category.objects.get_or_create(name=name)
            category.description = description
            category.tagline = tagline or None
            category.image.name = self.image_name(image, 'categories')
            category.is_active = True
            category.display_order = order
            category.is_featured = name in SUBCATEGORIES
            category.featured_order = list(SUBCATEGORIES).index(name) + 1 if name in SUBCATEGORIES else 0
            if name == 'Electronics':
                category.banner_image.name = self.image_name('category-electronics-banner.png', 'categories')
            category.save()
            categories[name] = category
        for parent, rows in SUBCATEGORIES.items():
            for order, row in enumerate(rows, start=1):
                name, image, *extra = row
                sub, _ = SubCategory.objects.get_or_create(category=categories[parent], name=name)
                sub.description = extra[0] if extra else sub.description
                sub.display_order = order
                sub.is_active = True
                image_name = self.image_name(image, 'subcategories')
                if image_name:
                    sub.image.name = image_name
                sub.save()
                subcategories[(parent, name)] = sub
        self.stdout.write(f'Categories: {len(categories)}, subcategories: {len(subcategories)}')
        return categories, subcategories

    def seed_products(self, categories, subcategories):
        products = {}
        for spec in PRODUCTS:
            fields = {
                'name': spec['name'],
                'category': categories[spec['category']],
                'subcategory': subcategories.get((spec['category'], spec['sub'])) if spec['sub'] else None,
                'price': Decimal(spec['price']),
                'compare_price': Decimal(spec['compare']) if spec['compare'] else None,
                'color': spec['color'],
                'short_description': spec['short'],
                'description': spec['description'],
                'stock_quantity': spec['stock'],
                'is_featured': spec.get('featured', False),
                'is_active': True,
            }
            product = Product.objects.filter(sku=spec['sku']).first()
            if product is None:
                product = Product(sku=spec['sku'], barcode=spec['sku'], **fields)
                product.barcode_image.name = self.barcode_name(spec['sku'])
                product.save()
            else:
                for key, value in fields.items():
                    setattr(product, key, value)
                product.save()
            image_name = self.image_name(spec['image'], 'products')
            primary = product.images.filter(is_primary=True).first() or product.images.first()
            if image_name and primary is None:
                ProductImage.objects.create(product=product, image=image_name, alt_text=product.name,
                                            is_primary=True, display_order=0)
            elif image_name and primary.image.name != image_name and spec['sku'].startswith('DEMO-'):
                primary.image.name = image_name
                primary.is_primary = True
                primary.save()
            products[spec['sku']] = product
        self.stdout.write(f'Products: {len(products)}')
        return products

    def seed_homepage(self, products):
        keep = []
        for placement, image, title, link, order in BANNERS:
            image_name = self.image_name(image, 'banners')
            if not image_name:
                continue
            banner = HomepageBanner.objects.filter(placement=placement, image=image_name).first()
            banner = banner or HomepageBanner(placement=placement, image=image_name)
            banner.title = title
            banner.link = link
            banner.display_order = order
            banner.is_active = True
            banner.save()
            keep.append(banner.pk)
        HomepageBanner.objects.exclude(pk__in=keep).update(is_active=False)

        for key, kind, title, order, limit, label, url, source in SECTIONS:
            HomepageSection.objects.update_or_create(key=key, defaults={
                'section_type': kind, 'title': title, 'subtitle': '', 'is_enabled': True,
                'display_order': order, 'item_limit': limit, 'view_all_label': label,
                'view_all_url': url, 'product_source': source,
            })
        HomepageSection.objects.exclude(key__in=[row[0] for row in SECTIONS]).update(is_enabled=False)

        for order, (title, description, icon) in enumerate(BENEFITS, start=1):
            HomepageBenefit.objects.update_or_create(title=title, defaults={
                'description': description, 'icon': icon, 'display_order': order, 'is_active': True,
            })
        HomepageBenefit.objects.exclude(title__in=[row[0] for row in BENEFITS]).update(is_active=False)

        trending = HomepageSection.objects.get(key='trending')
        trending.section_products.exclude(product__sku__in=TRENDING).delete()
        for order, sku in enumerate(TRENDING):
            HomepageSectionProduct.objects.update_or_create(
                section=trending, product=products[sku], defaults={'display_order': order})
        self.stdout.write(f'Homepage: {len(keep)} banners, {len(SECTIONS)} sections, {len(BENEFITS)} benefits')

    # People

    def seed_admin(self):
        admin = User.objects.filter(email='admin@example.com').first()
        if admin is None:
            admin = User.objects.create_user(
                email='admin@example.com', password=PASSWORD, first_name='Store', last_name='Admin',
                role='super_admin', is_staff=True, is_superuser=True, is_verified=True)
        return admin

    def seed_customers(self):
        customers = {}
        for key, spec in CUSTOMERS.items():
            user = User.objects.filter(email=spec['email']).first()
            if user is None:
                user = User.objects.create_user(
                    email=spec['email'], password=PASSWORD, first_name=spec['first_name'],
                    last_name=spec['last_name'], role='customer', is_verified=True)
            user.phone = spec['phone']
            user.address = spec['address']
            user.city = spec['city']
            user.postal_code = spec['postal_code']
            user.save()
            for label, name, phone, line1, line2, city, district, postal, default in spec['addresses']:
                Address.objects.update_or_create(user=user, address_line1=line1, defaults={
                    'label': label, 'full_name': name, 'phone': phone, 'address_line2': line2, 'city': city,
                    'district': district, 'postal_code': postal, 'is_default': default,
                    'is_inside_dhaka': district == 'Dhaka', 'address_type': 'shipping',
                })
            customers[key] = user
        return customers

    def seed_coupon(self):
        now = timezone.now()
        coupon, _ = Coupon.objects.update_or_create(code='SAVE800', defaults={
            'name': 'Winter savings ৳800 off',
            'description': '৳800 off orders of ৳5,000 or more.',
            'discount_type': 'fixed',
            'discount_value': Decimal('800'),
            'minimum_order_amount': Decimal('5000'),
            'usage_limit_per_user': 5,
            'valid_from': now - timedelta(days=400),
            'valid_until': now + timedelta(days=365),
            'is_active': True,
        })
        return coupon

    def seed_cart(self, user, products):
        cart, _ = Cart.objects.get_or_create(user=user)
        for sku, quantity in DESIGN_ITEMS:
            CartItem.objects.update_or_create(cart=cart, product=products[sku], variant=None,
                                              defaults={'quantity': quantity})

    # Orders

    def seed_orders(self, customers, products, coupon, admin, fresh=False):
        numbers = [row[0] for row in ORDERS]
        if fresh:
            Order.objects.filter(order_number__in=numbers).delete()
        existing = set(Order.objects.filter(order_number__in=numbers).values_list('order_number', flat=True))
        created = 0
        for index, row in enumerate(ORDERS):
            number = row[0]
            if number in existing:
                continue
            self.create_order(index, row, customers, products, coupon, admin)
            created += 1
        self.stdout.write(f'Orders: {created} created, {len(existing)} already present')

    def create_order(self, index, row, customers, products, coupon, admin):
        number, customer_key, placed, items, status, payment, coupon_code, courier_status, message = row
        user = customers[customer_key]
        address = user.addresses.filter(is_default=True).first()
        inside_dhaka = address.district == 'Dhaka'
        lines = [(products[sku], quantity) for sku, quantity in items]
        subtotal = sum((product.price * quantity for product, quantity in lines), Decimal('0'))
        discount = coupon.calculate_discount(subtotal) if coupon_code else Decimal('0')
        delivery = settings.DELIVERY_CHARGE_INSIDE_DHAKA if inside_dhaka else settings.DELIVERY_CHARGE_OUTSIDE_DHAKA

        order = Order.objects.create(
            order_number=number,
            user=user,
            order_type='online',
            order_status=status,
            payment_status=payment,
            payment_method='cod',
            shipping_name=address.full_name,
            shipping_phone=address.phone,
            shipping_address_line1=address.address_line1,
            shipping_address_line2=address.address_line2,
            shipping_city=address.city,
            shipping_district=address.district,
            shipping_postal_code=address.postal_code,
            is_inside_dhaka=inside_dhaka,
            subtotal=subtotal,
            delivery_charge=Decimal(delivery),
            discount=discount,
            coupon=coupon if coupon_code else None,
            coupon_code=coupon_code,
            stock_reduced=status not in ('pending', 'cancelled'),
        )
        for product, quantity in lines:
            OrderItem.objects.create(
                order=order, product=product, product_name=product.name, product_sku=product.sku,
                color=product.color, quantity=quantity, unit_price=product.price,
                compare_price=product.compare_price)
        if coupon_code:
            CouponUsage.objects.create(coupon=coupon, user=user, order=order, discount_amount=discount)
            Coupon.objects.filter(pk=coupon.pk).update(times_used=coupon.usages.count())

        timeline = [('pending', placed, 'Order placed.')]
        confirmed = placed + timedelta(minutes=12)
        booked = placed + timedelta(minutes=17)
        if status != 'pending':
            timeline.append(('confirmed', confirmed, 'Order confirmed by phone.'))
        if courier_status:
            code = f'SF{123456789 + index * 7919:09d}BD'
            timeline.append(('shipped', booked, f'Booked with Steadfast Courier. Tracking code {code}.'))
        delivered_at = booked + timedelta(days=2, hours=3)
        if status == 'delivered':
            timeline.append(('delivered', delivered_at, 'Delivered to the customer.'))
        if status == 'cancelled':
            timeline.append(('cancelled', booked + timedelta(days=3), message or 'Order cancelled.'))
        for history_status, when, note in timeline:
            entry = OrderStatusHistory.objects.create(order=order, status=history_status, note=note,
                                                      changed_by=None if history_status == 'pending' else admin)
            OrderStatusHistory.objects.filter(pk=entry.pk).update(created_at=when)

        Order.objects.filter(pk=order.pk).update(
            created_at=placed,
            updated_at=timeline[-1][1],
            confirmed_at=confirmed if status != 'pending' else None,
            shipped_at=booked if courier_status else None,
            delivered_at=delivered_at if status == 'delivered' else None,
        )
        if courier_status:
            self.create_shipment(order, index, code, courier_status, message, booked, admin)

    def create_shipment(self, order, index, code, courier_status, message, booked, admin):
        order.refresh_from_db()
        steps = COURIER_STEPS[courier_status] + [courier_status]
        times = [booked + timedelta(hours=6 * position) for position in range(len(steps))]
        if courier_status in ('delivered', 'partial_delivered'):
            times[-1] = booked + timedelta(days=2, hours=3)
        shipment = Shipment.objects.create(
            order=order,
            invoice=order.order_number,
            consignment_id=str(1424107 + index),
            tracking_code=code,
            tracking_url=tracking_url_for(code),
            status=courier_status,
            status_message=message,
            recipient_name=order.shipping_name,
            recipient_phone='0' + ''.join(ch for ch in order.shipping_phone if ch.isdigit())[-10:],
            recipient_address=', '.join(part for part in (
                order.shipping_address_line1, order.shipping_address_line2, order.shipping_city,
                order.shipping_postal_code) if part),
            cod_amount=order.total.quantize(Decimal('1')),  # every demo order is cash on delivery
            delivery_charge=order.delivery_charge if courier_status != 'in_review' else None,
            booked_at=booked,
            booked_by=admin,
            status_updated_at=times[-1],
            last_checked_at=times[-1],
            raw_response={'demo': True},
        )
        for position, (step, when) in enumerate(zip(steps, times)):
            event = ShipmentEvent.objects.create(
                shipment=shipment,
                source='booking' if position == 0 else 'webhook',
                status=step,
                message=message if step == courier_status else '',
                occurred_at=when,
                payload={'demo': True},
            )
            ShipmentEvent.objects.filter(pk=event.pk).update(created_at=when)
        Shipment.objects.filter(pk=shipment.pk).update(created_at=booked, updated_at=times[-1])
