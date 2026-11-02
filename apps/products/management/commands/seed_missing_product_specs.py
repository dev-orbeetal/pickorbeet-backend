"""
Fill ProductSpecification rows for catalog products that still have none.

Specs are taken from official manuals / brand pages (Soundcore A3949 & A3959,
Baseus Adaman PPAD000101, HOCO EQ34 Plus, Oraimo OEB-311 & OPB-7200Q).
Safe to re-run: only products with zero specifications are updated.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from apps.products.models import Product, ProductSpecification

# Matched by exact product name on production.
SPECS_BY_NAME = {
    'Anker Soundcore R50i True Wireless Earbuds': [
        ('Brand', 'soundcore (Anker)'),
        ('Model', 'R50i (A3949)'),
        ('Type', 'True wireless earbuds'),
        ('Bluetooth', '5.3'),
        ('Bluetooth range', '10 m / 33 ft'),
        ('Driver', '10 mm dynamic driver'),
        ('Frequency response', '20 Hz – 20 kHz'),
        ('Impedance', '16 Ω'),
        ('Microphones', '2 mics with AI-enhanced calls'),
        ('Water resistance', 'IPX5 (earbuds only; case not rated)'),
        ('Playtime', 'Up to 10 hours (up to 30 hours with charging case)'),
        ('Battery', '60 mAh × 2 (earbuds); 430 mAh (charging case)'),
        ('Charging time', 'Up to 2 hours'),
        ('Fast charge', '10 minutes ≈ 2 hours playtime'),
        ('Charging port', 'USB-C'),
        ('Input', '5 V ⎓ 0.43 A'),
        ('App', 'soundcore app (EQ, find device, firmware)'),
        ('Warranty', '18 months'),
    ],
    'Anker-Soundcore R50i NC TWS Earbuds': [
        ('Brand', 'soundcore (Anker)'),
        ('Model', 'R50i NC (A3959)'),
        ('Type', 'True wireless earbuds with ANC'),
        ('Bluetooth', '5.4'),
        ('Bluetooth range', '10 m'),
        ('Codecs', 'SBC / AAC'),
        ('Driver', '10 mm dynamic driver with BassUp'),
        ('Frequency response', '20 Hz – 20 kHz'),
        ('Impedance', '16 Ω'),
        ('Noise cancelling', 'Adaptive ANC up to 42 dB; Transparency mode'),
        ('Microphones', '4 mics with AI-enhanced calls'),
        ('Multipoint', 'Yes (via soundcore app)'),
        ('Water / dust resistance', 'IP54 (earbuds only; case not rated)'),
        ('Playtime (ANC off)', 'Up to 10 hours / 45 hours with case'),
        ('Playtime (ANC on)', 'Up to 7 hours / 30 hours with case'),
        ('Charging time', 'Earbuds ≈ 1 hour; case ≈ 2.5 hours'),
        ('Fast charge', '10 minutes ≈ 2 hours playtime'),
        ('Charging port', 'USB-C'),
        ('Case', '2-in-1 charging case and phone stand'),
        ('App', 'soundcore app (EQ, ANC levels, multipoint, firmware)'),
        ('Warranty', '18 months'),
    ],
    'Baseus Adaman Power Bank 22.5W 20000mAh': [
        ('Brand', 'Baseus'),
        ('Model', 'Adaman Metal Digital Display (PPAD000101)'),
        ('Type', 'Power bank'),
        ('Capacity', '20000 mAh / 3.7 V / 74 Wh'),
        ('Rated capacity', '12000 mAh (5 V / 3 A)'),
        ('Max output', '22.5 W (SCP / PD / QC compatible)'),
        ('Energy conversion', '≥ 75%'),
        ('Inputs', 'Lightning, Micro-USB, USB-C'),
        ('USB-C input', '5 V / 3 A; 5.5 V / 3 A (SCP); 9 V / 2 A'),
        ('Outputs', '2 × USB-A + 1 × USB-C (bidirectional)'),
        ('USB-A output', 'Up to 4.5 V / 5 A (SCP); 9 V / 2 A; 12 V / 1.5 A'),
        ('USB-C output', '5 V / 3 A; 9 V / 2.22 A; 12 V / 1.5 A'),
        ('Multi-port total', '5 V / 3 A max when ports share power'),
        ('Display', 'LED digital display (level / voltage / current)'),
        ('Shell', 'Aluminium alloy'),
        ('Simultaneous devices', 'Up to 3'),
    ],
    'HOCO EQ34 Plus Earbuds': [
        ('Brand', 'HOCO'),
        ('Model', 'EQ34 Plus (Rima)'),
        ('Type', 'True wireless earbuds'),
        ('Bluetooth', '5.4'),
        ('Chipset', 'Jerry AC7003D4'),
        ('Driver', '13 mm dynamic driver'),
        ('Noise cancellation', 'Hybrid ANC + ENC; Transparency mode'),
        ('Playtime (ANC off)', 'Up to 7 hours'),
        ('Playtime (ANC on)', 'Up to 6 hours'),
        ('Total with case', 'Up to 28 hours'),
        ('Earbud battery', '40 mAh each'),
        ('Case battery', '300 mAh'),
        ('Charging time', 'About 1 hour (earbuds)'),
        ('Charging port', 'USB-C'),
        ('Wireless range', 'About 10 m'),
        ('Controls', 'Touch controls; hall-switch auto pairing'),
        ('App', 'hoco Music'),
        ('Case size', '61 × 51.5 × 28.5 mm'),
        ('Total weight', 'About 44.8 g'),
        ('Material', 'ABS'),
    ],
    'Oraimo Necklace Lite OEB-311': [
        ('Brand', 'oraimo'),
        ('Model', 'Necklace Lite (OEB-311)'),
        ('Type', 'Wireless neckband'),
        ('Bluetooth', '5.3'),
        ('Bluetooth range', '10 m'),
        ('Driver', '10 mm dynamic drivers with HavyBass'),
        ('Battery', '220 mAh'),
        ('Playtime', 'Up to 30 hours'),
        ('Fast charge', '10 minutes ≈ 150 minutes playtime'),
        ('Charging port', 'USB Type-C'),
        ('Charging input', '5 V ⎓ 0.5 A'),
        ('Call features', 'ENC for calls; call vibration alert'),
        ('Connectivity', 'Dual-device connection'),
        ('Game mode', 'Low-latency game mode'),
        ('Water resistance', 'IPX4'),
        ('Other', 'Magnetic earbuds; Oraimo Sound app'),
        ('Warranty', '12 months'),
    ],
    'Oraimo PowerNova Q21 20000mAh 22.5W Power Bank': [
        ('Brand', 'oraimo'),
        ('Model', 'PowerNova Q21 (OPB-7200Q)'),
        ('Type', 'Power bank'),
        ('Capacity', '20000 mAh (74 Wh)'),
        ('Max output', 'Up to 22.5 W'),
        ('Protocols', 'PD 3.0, QC 3.0, SCP, FCP'),
        ('USB-C input', '5 V / 3 A; 9 V / 2.22 A; 12 V / 1.67 A'),
        ('USB-A outputs', '2 × USB-A: 5 V / 3 A; 9 V / 2.22 A; 12 V / 1.67 A; 10 V / 2.25 A'),
        ('USB-C output', '5 V / 3 A; 9 V / 2.22 A; 12 V / 1.67 A; 10 V / 2.25 A'),
        ('Total output', '5 V / 3 A max (shared)'),
        ('Ports', '2 × USB-A + 1 × USB-C; charge up to 3 devices'),
        ('Display', 'Smart digital battery display'),
        ('Protection', '15-layer smart protection'),
        ('Recharge', 'Up to 20 W two-way USB-C'),
        ('Warranty', '12 months'),
    ],
}


class Command(BaseCommand):
    help = 'Seed authentic specifications for products that still have none.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List matches without writing.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        missing = (
            Product.objects.annotate(n=Count('specifications'))
            .filter(n=0)
            .order_by('name')
        )
        seeded = skipped = 0
        for product in missing:
            rows = SPECS_BY_NAME.get(product.name)
            if not rows:
                skipped += 1
                self.stdout.write(self.style.WARNING(f'No spec map for: {product.name}'))
                continue
            self.stdout.write(f'{"Would seed" if dry_run else "Seeding"} {product.name} ({len(rows)} rows)')
            if dry_run:
                seeded += 1
                continue
            for index, (name, value) in enumerate(rows):
                ProductSpecification.objects.create(
                    product=product,
                    name=name[:80],
                    value=value[:255],
                    sort_order=index,
                )
            seeded += 1
        self.stdout.write(self.style.SUCCESS(
            f'Done. seeded={seeded} skipped_unmapped={skipped} dry_run={dry_run}'
        ))
