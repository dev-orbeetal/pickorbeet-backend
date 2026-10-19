from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.products.models import (
    Category, HomepageBenefit, HomepageSection, HomepageSectionProduct, Product, SubCategory,
)


PRODUCTS = [
    {
        "sku": "ANK-R50I",
        "name": "Anker Soundcore R50i True Wireless Earbuds",
        "price": "1550.00",
        "compare_price": None,
        "color": "Black",
        "subcategory": "True Wireless Earbuds",
        "short_description": "Soundcore R50i true wireless earbuds with Bluetooth 5.3, 10mm drivers, and IPX5 sweat resistance.",
        "description": (
            "Anker Soundcore R50i true wireless earbuds.\n\n"
            "Bluetooth 5.3 with the Soundcore app for EQ and controls. "
            "10mm dynamic drivers, dual microphones for calls, and IPX5 water resistance. "
            "Up to 10 hours of playback on a charge and up to 30 hours with the charging case. "
            "USB-C charging."
        ),
    },
    {
        "sku": "BAS-ADAMAN-20K",
        "name": "Baseus Adaman 22.5W 20000mAh Power Bank",
        "price": "1550.00",
        "compare_price": "1999.00",
        "color": "Black",
        "subcategory": "Power Banks",
        "short_description": "Baseus Adaman 20000mAh power bank with 22.5W fast charge and a digital battery display.",
        "description": (
            "Baseus Adaman 22.5W 20000mAh power bank.\n\n"
            "20000mAh capacity with up to 22.5W output for phones and small devices. "
            "Digital display shows the remaining charge. USB-C charging."
        ),
    },
    {
        "sku": "HOC-EQ34P-BLK",
        "name": "Hoco EQ34 Plus Rima True Wireless Earbuds",
        "price": "599.00",
        "compare_price": "850.00",
        "color": "Black",
        "subcategory": "True Wireless Earbuds",
        "short_description": "Hoco EQ34 Plus Rima TWS earbuds in black, with hybrid ANC, ENC calls, and Bluetooth 5.4.",
        "description": (
            "Hoco EQ34 Plus Rima true wireless earbuds, black.\n\n"
            "Bluetooth 5.4 with hybrid active noise cancellation and dual-microphone ENC for calls. "
            "About 7 hours of playback (about 6 hours with ANC on) and up to 28 hours with the 300mAh case. "
            "Hoco Music app, hall-switch auto pairing, touch controls, and USB-C charging."
        ),
    },
    {
        "sku": "HOC-EQ34P-WHT",
        "name": "Hoco EQ34 Plus Rima True Wireless Earbuds",
        "price": "599.00",
        "compare_price": "899.00",
        "color": "White",
        "subcategory": "True Wireless Earbuds",
        "short_description": "Hoco EQ34 Plus Rima TWS earbuds in white, with hybrid ANC, ENC calls, and Bluetooth 5.4.",
        "description": (
            "Hoco EQ34 Plus Rima true wireless earbuds, white.\n\n"
            "Same EQ34 Plus Rima model: Bluetooth 5.4, hybrid ANC, ENC calls, "
            "about 7 hours of playback, and up to 28 hours with the charging case. USB-C charging."
        ),
    },
    {
        "sku": "HOC-J154A",
        "name": "Hoco J154A 22.5W + PD20W 20000mAh Power Bank",
        "price": "1450.00",
        "compare_price": "1850.00",
        "color": "Black",
        "subcategory": "Power Banks",
        "short_description": "Hoco J154A 20000mAh power bank with 22.5W and USB-C PD 20W output.",
        "description": (
            "Hoco J154A power bank.\n\n"
            "20000mAh capacity. 22.5W output plus USB-C Power Delivery at 20W "
            "for phones, tablets, and other USB-C devices."
        ),
    },
    {
        "sku": "ORA-OEB-311",
        "name": "Oraimo Necklace Lite (OEB-311)",
        "price": "1080.00",
        "compare_price": "1500.00",
        "color": "Black",
        "subcategory": "Neckbands",
        "short_description": "Oraimo Necklace Lite neckband, model OEB-311, with call vibration and up to 30 hours of playback.",
        "description": (
            "Oraimo Necklace Lite wireless neckband earphones, model OEB-311.\n\n"
            "Bluetooth 5.3, 10mm drivers with HavyBass, and call noise reduction. "
            "Call vibration alerts, dual-device connection, low-latency game mode, and IPX4 sweat resistance. "
            "220mAh battery for up to 30 hours of playback. USB-C charging and the oraimo Sound app."
        ),
    },
]


class Command(BaseCommand):
    help = "Seed the Electronics catalog with the PickOrbeet launch products."

    def handle(self, *args, **options):
        category, _ = Category.objects.get_or_create(
            name="Electronics",
            defaults={
                "description": "Earbuds, neckbands, and power banks.",
                "display_order": 1,
                "is_active": True,
            },
        )

        subcategories = {}
        for order, name in enumerate(["True Wireless Earbuds", "Power Banks", "Neckbands"], start=1):
            subcategory, _ = SubCategory.objects.get_or_create(
                category=category,
                name=name,
                defaults={"display_order": order, "is_active": True},
            )
            subcategories[name] = subcategory

        for item in PRODUCTS:
            self._upsert_product(item, category, subcategories.get(item["subcategory"]))
        self._seed_reference_catalog()
        self._seed_homepage()

    def _upsert_product(self, item, category, subcategory, overwrite_copy=True):
        compare = item.get("compare_price")
        fields = {
            "name": item["name"],
            "category": category,
            "subcategory": subcategory,
            "price": Decimal(item["price"]),
            "compare_price": Decimal(compare) if compare else None,
            "color": item.get("color") or "",
            "is_active": True,
        }
        if overwrite_copy:
            fields["short_description"] = item.get("short_description") or ""
            fields["description"] = item.get("description") or ""
        product = Product.objects.filter(sku=item["sku"]).first()
        if product is None:
            product = Product(sku=item["sku"], stock_quantity=0, **fields)
            product.save()
            action = "Created"
        else:
            for key, value in fields.items():
                setattr(product, key, value)
            product.save(update_fields=list(fields.keys()))
            action = "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} {product.sku} — {product.name} — ৳{product.price}"))
        return product

    def _seed_reference_catalog(self):
        names = [
            "Electronics", "Fashion", "Home & Living", "Beauty & Personal Care",
            "Sports & Outdoors", "Books", "Toys & Games", "Showpieces",
        ]
        categories = {}
        for order, name in enumerate(names, start=1):
            category, _ = Category.objects.get_or_create(
                name=name,
                defaults={"display_order": order, "is_active": True},
            )
            categories[name] = category
        extras = [
            {"sku": "AMZ-BIP5", "name": "Amazfit Bip 5 Smart Watch", "price": "8999.00", "compare_price": "12500.00", "category": "Electronics"},
            {"sku": "ACC-RGB-KB", "name": "Mechanical RGB Keyboard", "price": "4200.00", "compare_price": "5600.00", "category": "Electronics"},
            {"sku": "HOME-LED-LAMP", "name": "Smart LED Desk Lamp", "price": "2150.00", "compare_price": "2800.00", "category": "Home & Living"},
            {"sku": "HOME-SHOWPIECE", "name": "Decorative Showpiece", "price": "1350.00", "compare_price": "1990.00", "category": "Showpieces"},
            {"sku": "FASH-HANDBAG", "name": "Women's Handbag", "price": "1950.00", "compare_price": "2650.00", "category": "Fashion"},
            {"sku": "ACC-MOUSE", "name": "Wireless Mouse", "price": "950.00", "compare_price": "1250.00", "category": "Electronics"},
        ]
        for item in extras:
            self._upsert_product(item, categories[item["category"]], None, overwrite_copy=False)

    def _seed_homepage(self):
        sections = [
            ("hero", "hero", "Hero", "", 1, 5, "", "", "manual"),
            ("categories", "categories", "Categories", "", 2, 12, "", "", "manual"),
            ("benefits", "benefits", "Benefits", "", 3, 4, "", "", "manual"),
            ("new-arrivals", "products", "New Arrivals", "", 4, 8, "View All", "/products", "latest"),
            ("promos", "promos", "Promotions", "", 5, 2, "", "", "manual"),
            ("trending", "products", "Trending Products", "", 6, 8, "View All", "/products", "manual"),
        ]
        for key, kind, title, subtitle, order, limit, label, url, source in sections:
            HomepageSection.objects.update_or_create(
                key=key,
                defaults={
                    "section_type": kind,
                    "title": title,
                    "subtitle": subtitle,
                    "is_enabled": True,
                    "display_order": order,
                    "item_limit": limit,
                    "view_all_label": label,
                    "view_all_url": url,
                    "product_source": source,
                },
            )
        benefits = [
            ("100% Original Products", "Trusted Quality", "shield", 1),
            ("Fast & Reliable Delivery", "All over Bangladesh", "truck", 2),
            ("Secure Payment", "Multiple Payment Options", "card", 3),
            ("Easy Returns", "Hassle Free", "returns", 4),
        ]
        for title, description, icon, order in benefits:
            HomepageBenefit.objects.update_or_create(
                title=title,
                defaults={"description": description, "icon": icon, "display_order": order, "is_active": True},
            )
        placements = {
            "new-arrivals": ["ORA-OEB-311", "HOC-J154A", "HOC-EQ34P-WHT", "HOC-EQ34P-BLK", "BAS-ADAMAN-20K"],
            "trending": ["AMZ-BIP5", "ACC-RGB-KB", "HOME-LED-LAMP", "HOME-SHOWPIECE", "FASH-HANDBAG", "ACC-MOUSE"],
        }
        for key, skus in placements.items():
            section = HomepageSection.objects.get(key=key)
            for order, sku in enumerate(skus):
                product = Product.objects.filter(sku=sku).first()
                if not product:
                    continue
                HomepageSectionProduct.objects.update_or_create(
                    section=section,
                    product=product,
                    defaults={"display_order": order},
                )
