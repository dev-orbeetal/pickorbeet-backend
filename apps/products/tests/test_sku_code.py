from io import StringIO

from django.core.management import call_command

from apps.orders.tests.factories import ShopTestCase, make_product
from apps.products.models import ProductVariant
from apps.products.sku_code import (
    claim_variant_sku,
    color_token,
    plan_changes,
    product_parts,
    size_token,
    variant_parts,
)


class SkuCodeTests(ShopTestCase):
    def test_color_and_size_keep_the_number(self):
        self.assertEqual(variant_parts(['White', 'L']), ['white', 'lg'])
        self.assertEqual(variant_parts(['M', 'Midnight', '128GB']), ['midnight', 'md', '128gb'])
        taken = set()
        self.assertEqual(claim_variant_sku('ORA-OEB-311', ['M', 'Midnight', '128GB'], taken), 'midnight-md-128gb-311')
        self.assertIn('midnight-md-128gb-311', taken)

    def test_a_taken_number_moves_up(self):
        taken = {'white-lg-998'}
        self.assertEqual(claim_variant_sku('998', ['White', 'LG'], taken), 'white-lg-999')

    def test_junk_color_text_is_not_a_color(self):
        self.assertEqual(color_token('Random.'), '')
        self.assertEqual(color_token('Black, Style: Modern'), '')
        self.assertEqual(color_token('Metal Body'), '')
        self.assertEqual(color_token('Ice Blue'), 'ice-blue')
        self.assertEqual(color_token('Pastel Pink'), 'pastel-pink')
        self.assertEqual(size_token('L', allow_letters=True), 'lg')
        self.assertEqual(size_token('L'), '')
        self.assertEqual(size_token('XL'), 'xl')

    def test_title_color_wins_over_a_wrong_color_field(self):
        self.assertEqual(product_parts('TecH BonD Socket (WHITE)', 'Black', ''), ['white'])
        self.assertEqual(product_parts('Anker Nano Charger (45W)- White', '', ''), ['white'])
        self.assertEqual(product_parts('Soundcore R500 Red In-Ear', 'Red', ''), ['red'])
        self.assertEqual(product_parts('Plain Hair Dryer', '20ppm (Draft)', ''), [])
        self.assertEqual(product_parts('Anker PowerCore Select 10000', 'Black', ''), [])
        self.assertEqual(product_parts('Anker Powerline+ USB-C to USB A 3.0 6ft- Gray', 'Black', ''), ['gray'])
        self.assertEqual(product_parts('Xiaomi Diffusion Humidifier Large Capacity', '', ''), [])
        self.assertEqual(product_parts('Silencare Oil-free Air Fryer', '', ''), [])
        self.assertEqual(product_parts('Baseus Golden Contactor Pro', '', ''), [])
        self.assertEqual(product_parts('enchen black head remover', 'Black', ''), [])
        self.assertEqual(product_parts('Plain Dryer', '', 'L'), ['lg'])

    def test_plan_rewrites_supplier_codes_and_keeps_parents(self):
        products = [
            {'id': 'p1', 'sku': 'DX-10055', 'name': 'Soundcore R500 Red', 'color': 'Red', 'size': '', 'variant_count': 0},
            {'id': 'p2', 'sku': 'MC-10055', 'name': 'Other Red Cable', 'color': 'Red', 'size': '', 'variant_count': 0},
            {'id': 'p3', 'sku': '', 'name': 'Anker Charger', 'color': '', 'size': '', 'variant_count': 2},
            {'id': 'p4', 'sku': 'HM-1', 'name': 'Plain Dryer', 'color': '', 'size': '', 'variant_count': 0},
        ]
        variants = [
            {'id': 'v1', 'sku': 'ITEM-WHITE', 'product_sku': '', 'labels': ['White']},
            {'id': 'v2', 'sku': 'ITEM-BLACK-2', 'product_sku': '', 'labels': ['Black']},
        ]
        product_changes, variant_changes, skipped, bumped = plan_changes(products, variants)
        self.assertEqual(product_changes[0][2], 'red-10055')
        self.assertEqual(product_changes[1][2], 'red-10056')
        self.assertEqual(bumped, 1)
        self.assertEqual(skipped, 1)
        self.assertEqual([change[2] for change in variant_changes], ['black-10057', 'white-10058'])
        # The parent with variants is not given a color code of its own.
        self.assertNotIn('p3', [change[0] for change in product_changes])

    def test_command_rewrites_a_colored_product(self):
        product = make_product(name='Esonic Monitor White')
        product.sku = 'IT-22143'
        product.color = 'White'
        product.save(update_fields=['sku', 'color'])
        parent = make_product(name='Anker Cable')
        parent.sku = 'DX-9'
        parent.save(update_fields=['sku'])
        ProductVariant.objects.create(product=parent, sku='ITEM-WHITE', color='White')

        out = StringIO()
        call_command('normalize_catalog_skus', '--dry-run', stdout=out)
        product.refresh_from_db()
        self.assertEqual(product.sku, 'IT-22143')
        self.assertIn('white-22143', out.getvalue())

        call_command('normalize_catalog_skus', stdout=StringIO())
        product.refresh_from_db()
        parent.refresh_from_db()
        variant = parent.variants.get()
        self.assertEqual(product.sku, 'white-22143')
        self.assertEqual(parent.sku, 'DX-9')
        self.assertEqual(variant.sku, 'white-9')
