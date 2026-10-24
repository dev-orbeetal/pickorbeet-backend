"""Download catalog photos and write manifest.json for seed_category_catalog.

Product copy for the extra departments is original. Photos come from the public
DummyJSON demo catalog and from Openverse results that allow commercial use
(CC0, public domain, or CC BY).
"""
import io
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
IMAGES = ROOT / 'images'
MANIFEST = ROOT / 'manifest.json'
UA = 'PickOrbeetCatalogSeeder/1.0 (https://pickorbeet.com; catalog seed)'
TARGET = 12  # a few extras so a failed photo does not leave a category short

# DummyJSON titles, in the order they should fill each category.
DUMMYJSON = {
    'Fashion': [
        'Blue & Black Check Shirt',
        'Man Plaid Shirt',
        'Man Short Sleeve Shirt',
        'Men Check Shirt',
        'Sports Sneakers Off White & Red',
        'Blue Frock',
        'Girl Summer Dress',
        'Gray Dress',
        'Tartan Dress',
        'Black Women\'s Gown',
        'Blue Women\'s Handbag',
        'Classic Sun Glasses',
    ],
    'Mobile & Accessories': [
        'Selfie Stick Monopod',
        'Monopod',
        'Selfie Lamp with iPhone',
        'iPhone 12 Silicone Case with MagSafe Plum',
        'Beats Flex Wireless Earphones',
        'Apple iPhone Charger',
        'Apple Airpods',
        'Realme C35',
        'Samsung Galaxy S10',
        'Oppo A57',
        'Amazon Echo Plus',
        'Vivo S1',
    ],
    'Computer & Accessories': [
        'Apple MacBook Pro 14 Inch Space Grey',
        'Asus Zenbook Pro Dual Screen Laptop',
        'Huawei Matebook X Pro',
        'Lenovo Yoga 920',
        'New DELL XPS 13 9300 Laptop',
    ],
    'Home & Living': [
        'Annibale Colombo Bed',
        'Annibale Colombo Sofa',
        'Bedside Table African Cherry',
        'Knoll Saarinen Executive Conference Chair',
        'Wooden Bathroom Sink With Mirror',
        'Table Lamp',
        'Plant Pot',
        'House Showpiece Plant',
        'Family Tree Photo Frame',
        'Decoration Swing',
        'Microwave Oven',
        'Spice Rack',
    ],
    'Beauty & Personal Care': [
        'Essence Mascara Lash Princess',
        'Eyeshadow Palette with Mirror',
        'Powder Canister',
        'Red Lipstick',
        'Red Nail Polish',
        'Attitude Super Leaves Hand Soap',
        'Olay Ultra Moisture Shea Butter Body Wash',
        'Vaseline Men Body and Face Lotion',
        'Calvin Klein CK One',
        'Dolce Shine Eau de',
        'Chanel Coco Noir Eau De',
        'Gucci Bloom Eau de',
    ],
    'Groceries': [
        'Rice',
        'Cooking Oil',
        'Honey Jar',
        'Eggs',
        'Milk',
        'Chicken Meat',
        'Nescafe Coffee',
        'Juice',
        'Apple',
        'Beef Steak',
        'Green Bell Pepper',
        'Ice Cream',
    ],
    'Sports & Fitness': [
        'Football',
        'Cricket Bat',
        'Cricket Ball',
        'Cricket Helmet',
        'Tennis Racket',
        'Basketball',
        'Volleyball',
        'Baseball Glove',
        'Feather Shuttlecock',
        'Tennis Ball',
        'American Football',
        'Basketball Rim',
    ],
    'Automotive': [
        'Scooter Motorcycle',
        'Sportbike Motorcycle',
        'Generic Motorcycle',
        'Kawasaki Z800',
        'MotoGP CI.H1',
    ],
}

# Original listings whose photos are searched on Openverse.
CUSTOM = {
    'Computer & Accessories': [
        ('Compact Wireless Keyboard', 'wireless computer keyboard on desk', '1890', '2490', 30,
         'A slim keyboard for everyday desk work.',
         'Low-profile wireless keyboard with quiet keys and a USB receiver. Comfortable for writing, browsing, and light office work.'),
        ('Silent Click Mouse', 'black computer mouse on desk', '890', '1290', 40,
         'A quiet mouse for a shared desk.',
         'Ambidextrous optical mouse with a smooth scroll wheel. The cord is long enough to reach from a laptop to the side of the desk.'),
        ('24-inch Full HD Monitor', 'computer monitor on office desk', '12490', '14990', 12,
         'A clear Full HD screen for work and study.',
         '24-inch LED monitor with a 1920×1080 panel and an adjustable stand. HDMI and VGA inputs cover most laptops and desktop PCs.'),
        ('HD Desk Webcam', 'webcam mounted on laptop', '2490', '3290', 22,
         'A simple webcam for calls and classes.',
         'Clip-on HD webcam with a built-in microphone. It sits on a laptop lid or a desktop monitor and works over USB.'),
        ('Four-Port USB-C Hub', 'usb c hub adapter cables', '1590', '2190', 35,
         'Extra ports for a laptop that only has USB-C.',
         'Compact hub with USB-A ports and a pass-through USB-C port. Useful for a mouse, a flash drive, and charging at the same time.'),
        ('Padded Laptop Sleeve', 'laptop sleeve case', '990', '1290', 26,
         'A padded sleeve for a 14-inch laptop.',
         'Soft sleeve with a felt lining and a zip closure. It fits a 14-inch laptop and a thin charger.'),
    ],
    'Toys & Baby': [
        ('Honey Plush Teddy', 'teddy bear plush toy', '1290', '1690', 28,
         'A soft teddy for bedtime.',
         'Medium plush teddy with stitched features and a huggable fill. Suitable as a gift for a child or a nursery shelf.'),
        ('Wooden Building Blocks', 'wooden toy building blocks', '1590', '1990', 24,
         'Smooth wooden blocks for open-ended play.',
         'A set of solid wood blocks in simple shapes. The edges are sanded, and the pieces stack into houses, towers, and roads.'),
        ('Pull-back Toy Car', 'toy car diecast', '690', '990', 40,
         'A small car that rolls across the floor.',
         'Die-cast pull-back car with a painted body. Wind it back, let go, and it runs a short distance on a smooth floor.'),
        ('500-piece Jigsaw Puzzle', 'jigsaw puzzle pieces', '890', '1190', 20,
         'An evening puzzle for the family.',
         'Five hundred interlocking pieces with a finished picture guide. The pieces are standard thickness and come in a storage box.'),
        ('Soft Story Doll', 'cloth doll toy', '1190', '1490', 18,
         'A cloth doll with a simple outfit.',
         'Soft doll with embroidered features and removable clothes. Light enough for a child to carry around the house.'),
        ('Family Board Game', 'board game box on table', '1490', '1890', 16,
         'A board game for a family evening.',
         'A boxed game for two to four players, with a folded board, tokens, and a short rule sheet. A full round takes about half an hour.'),
        ('Plush Bunny', 'stuffed bunny rabbit toy', '990', '1290', 26,
         'A small bunny that sits on a shelf.',
         'Short-pile plush bunny with long ears and a seated pose. The fill is soft and the seams are double-stitched.'),
        ('Wooden Toy Train', 'wooden toy train', '1790', '2290', 14,
         'A wooden engine with a couple of carriages.',
         'Painted wooden train that links together with magnets. The wheels roll on a table or on a wooden track.'),
        ('Baby Hand Rattle', 'baby rattle toy', '490', '690', 36,
         'A light rattle for little hands.',
         'Smooth plastic rattle with a gentle sound and no small loose parts. Easy to grip during tummy time.'),
        ('Bath Rubber Duck', 'rubber duck bath toy', '350', None, 50,
         'A floating duck for bath time.',
         'Classic rubber duck that floats upright. The surface wipes clean after the bath.'),
        ('Colorful Stacking Rings', 'baby stacking ring toy', '590', '790', 30,
         'Rings that stack on a center post.',
         'Five brightly colored rings in graduating sizes. A first toy for sorting, stacking, and hand-eye practice.'),
        ('Soft Activity Ball', 'colorful soft baby ball', '650', None, 28,
         'A soft ball that is easy to grab.',
         'Lightweight fabric ball with stitched panels. It is quiet indoors and simple for a baby to hold.'),
    ],
    'Books & Stationery': [
        ('A5 Hardcover Notebook', 'hardcover notebook on desk', '450', '590', 40,
         'A ruled notebook with a hard cover.',
         'A5 notebook with lined pages and a ribbon marker. The cover is stiff enough to write on without a desk underneath.'),
        ('Smooth Ballpoint Pen Set', 'ballpoint pens set', '390', '490', 48,
         'A pack of everyday ballpoint pens.',
         'Ten medium-tip ballpoints with blue ink and a comfortable barrel. The ink dries quickly on ordinary notebook paper.'),
        ('24-color Pencil Set', 'colored pencils art set', '690', '890', 22,
         'Colored pencils for school and sketching.',
         'Twenty-four pre-sharpened colored pencils in a tin. The cores are soft enough for coloring and light enough for notes in a margin.'),
        ('Sticky Note Pack', 'sticky notes pad desk', '250', None, 60,
         'A cube of sticky notes for reminders.',
         'Yellow sticky notes in a small cube. Each sheet lifts cleanly and holds on paper, a monitor bezel, or a book page.'),
        ('Plain Sketchbook', 'blank sketchbook drawing', '520', '690', 24,
         'Blank pages for drawing and notes.',
         'A5 sketchbook with thick, blank paper that takes pencil and light marker. The binding lies reasonably flat.'),
        ('Everyday Fountain Pen', 'fountain pen on paper', '890', '1190', 16,
         'A starter fountain pen with a smooth nib.',
         'Metal-trim fountain pen with a medium nib and an ink converter included. It writes a steady line on notebook paper.'),
        ('Canvas Pencil Case', 'pencil case stationery', '420', '550', 32,
         'A zip case for pens and a sharpener.',
         'Canvas pencil case with one main zip. It holds a handful of pens, a ruler, and a small eraser.'),
        ('Desktop Stapler', 'office stapler on desk', '350', None, 30,
         'A small stapler for home and office.',
         'Desktop stapler that takes standard 26/6 staples and pins about twenty sheets. The base has a non-slip pad.'),
        ('Pastel Highlighter Set', 'highlighter pens set', '320', '420', 36,
         'Soft-color highlighters that do not bleed.',
         'A set of five chisel-tip highlighters in pastel shades. The ink sits on the page instead of soaking through thin paper.'),
        ('A4 Ruled Notepad', 'ruled notepad paper', '180', None, 50,
         'A tear-off pad for lists and drafts.',
         'A4 ruled notepad with a cardboard back. Sheets tear off along the top glue binding.'),
        ('Binder Clip Box', 'binder clips office', '220', None, 40,
         'A box of clips for packets of paper.',
         'Mixed-size binder clips with folding wire handles. They hold a few dozen sheets without punching holes.'),
        ('Desk Organizer Tray', 'desk organizer stationery tray', '750', '990', 18,
         'A tray that keeps pens and notes in one place.',
         'Desktop organizer with compartments for pens, clips, and a notepad. The finish wipes clean.'),
    ],
    'Health & Wellness': [
        ('Home First Aid Kit', 'first aid kit box', '890', '1190', 20,
         'A compact kit for cuts, scrapes, and headaches.',
         'Zip case with bandages, antiseptic wipes, gauze, tape, and a few common tablets. Small enough for a cupboard or a car.'),
        ('Digital Thermometer', 'digital thermometer medical', '450', '590', 30,
         'A fast reading for a fever check.',
         'Digital stick thermometer with a beep when the reading is ready. The tip is washable and the display is large.'),
        ('Daily Multivitamin', 'vitamin supplement bottles', '790', '990', 24,
         'A once-a-day multivitamin bottle.',
         'Thirty tablets in a sealed bottle. A general daily supplement for adults, not a replacement for a meal.'),
        ('Aloe Hand Sanitizer', 'hand sanitizer bottle', '220', None, 48,
         'A pocket bottle of hand sanitizer.',
         'Gel sanitizer with aloe so hands do not dry out as quickly. The flip cap closes tightly in a bag.'),
        ('Upper-arm Blood Pressure Monitor', 'blood pressure monitor cuff', '2490', '2990', 12,
         'A home monitor with an upper-arm cuff.',
         'Automatic blood pressure monitor that stores recent readings. The cuff fits a typical adult arm and the screen shows systolic, diastolic, and pulse.'),
        ('Disposable Face Masks', 'disposable medical face masks', '180', None, 80,
         'A pack of disposable face masks.',
         'Three-layer disposable masks with ear loops. They come folded flat in a box for a drawer or a bag.'),
        ('Electric Heating Pad', 'electric heating pad', '1590', '1990', 14,
         'A soft pad for sore shoulders and backs.',
         'Cloth heating pad with a few heat settings and an auto-off timer. It stays flexible so it can wrap a shoulder.'),
        ('Fingertip Pulse Oximeter', 'pulse oximeter fingertip', '990', '1290', 18,
         'A fingertip reading of oxygen and pulse.',
         'Clip-on pulse oximeter with a small OLED screen. One button turns it on; the reading appears after a few seconds.'),
        ('Fabric Bandage Box', 'adhesive bandages box', '160', None, 60,
         'A box of flexible fabric bandages.',
         'Assorted fabric plasters that stretch with the skin. Useful for fingers, knees, and small kitchen cuts.'),
        ('Digital Bathroom Scale', 'digital bathroom weighing scale', '1890', '2290', 16,
         'A slim scale with a clear display.',
         'Tempered-glass bathroom scale that shows weight in kilograms. It switches on when you step on and turns itself off.'),
        ('Reusable Hot Water Bag', 'hot water bottle rubber', '450', '590', 26,
         'A classic hot water bag for cold evenings.',
         'Rubber hot water bag with a ribbed surface and a secure stopper. Fill it with hot, not boiling, water.'),
        ('Weekly Pill Organizer', 'pill organizer box weekly', '350', None, 30,
         'A seven-day box for tablets.',
         'Plastic organizer with a compartment for each day. The lids snap shut so a bag does not spill them.'),
    ],
    'Automotive': [
        ('Dashboard Phone Mount', 'car phone holder dashboard', '690', '890', 30,
         'A mount that holds a phone at the dash.',
         'Adjustable car phone holder with a grip that fits most phones. The base sticks to a dashboard or a windshield.'),
        ('Dual-port Car Charger', 'car usb charger adapter', '550', '750', 36,
         'Two USB ports for the car.',
         '12V car charger with two USB outputs. It charges a phone and a power bank on a long drive.'),
        ('Microfiber Wash Cloths', 'microfiber car cleaning cloths', '390', None, 40,
         'Soft cloths for dust and glass.',
         'A pack of microfiber cloths that pick up dust without scratching a screen or a painted panel. They wash and reuse.'),
        ('Tire Pressure Gauge', 'tire pressure gauge', '480', '650', 22,
         'A pencil gauge for tire pressure.',
         'Analog tire gauge with a pocket clip. Press it on the valve and read the pressure before a highway trip.'),
        ('Citrus Air Freshener', 'car air freshener', '250', None, 50,
         'A light citrus scent for the cabin.',
         'Hanging air freshener with a mild citrus smell. It lasts a few weeks and comes off the mirror when you want it gone.'),
        ('Folding Trunk Organizer', 'car trunk organizer box', '1290', '1690', 14,
         'A collapsible box for the boot.',
         'Fabric trunk organizer with stiff sides and handles. It keeps bottles and tools from sliding, and it folds flat when the boot needs the space.'),
    ],
}

CODES = {
    'Fashion': 'FASH',
    'Mobile & Accessories': 'MOBL',
    'Computer & Accessories': 'COMP',
    'Home & Living': 'HOME',
    'Beauty & Personal Care': 'BEAU',
    'Groceries': 'GROC',
    'Sports & Fitness': 'SPRT',
    'Toys & Baby': 'TOYS',
    'Automotive': 'AUTO',
    'Books & Stationery': 'BOOK',
    'Health & Wellness': 'HLTH',
}


def get_json(url):
    request = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=40) as response:
        return json.load(response)


def get_bytes(url):
    request = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read()


def bdt(usd, discount=0):
    price = max(50, int(round(float(usd) * 120 / 10.0) * 10))
    compare = None
    if discount and float(discount) >= 5:
        original = int(round(price / (1 - float(discount) / 100) / 10.0) * 10)
        if original > price:
            compare = original
    return str(price), None if compare is None else str(compare)


def first_sentence(text, limit=140):
    sentence = text.strip().split('. ')[0].strip().rstrip('.')
    if len(sentence) > limit:
        return sentence[: limit - 1].rstrip() + '…'
    return sentence


def save_jpeg(raw, path):
    image = Image.open(io.BytesIO(raw)).convert('RGB')
    image.thumbnail((1100, 1100))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, 'JPEG', quality=84, optimize=True)
    return path.stat().st_size


def dummy_products():
    payload = get_json('https://dummyjson.com/products?limit=0')
    return {item['title']: item for item in payload['products']}


def from_dummy(title, source):
    item = source[title]
    price, compare = bdt(item['price'], item.get('discountPercentage') or 0)
    description = item['description'].strip()
    brand = (item.get('brand') or '').strip()
    if brand and brand.lower() not in description.lower():
        description = f'{description}\n\nBrand: {brand}.'
    warranty = (item.get('warrantyInformation') or '').strip()
    if warranty and warranty.lower() not in {'no warranty', '1 week warranty'}:
        description = f'{description}\n\n{warranty}.'
    return {
        'name': item['title'],
        'price': price,
        'compare': compare,
        'stock': max(8, min(int(item.get('stock') or 20), 80)),
        'short': first_sentence(item['description']),
        'description': description,
        'image_url': item['images'][0],
    }


def openverse(query):
    params = urllib.parse.urlencode({
        'q': query,
        'license': 'cc0,pdm,by',
        'license_type': 'commercial',
        'page_size': 16,
        'mature': 'false',
    })
    payload = get_json('https://api.openverse.org/v1/images/?' + params)
    for item in payload.get('results') or []:
        license_name = (item.get('license') or '').lower()
        if license_name not in {'cc0', 'pdm', 'by'}:
            continue
        if (item.get('width') or 0) < 600 or (item.get('height') or 0) < 400:
            continue
        title = (item.get('title') or '').lower()
        if 'logo' in title or 'icon' in title or 'screenshot' in title:
            continue
        url = item.get('url')
        if not url:
            continue
        creator = item.get('creator') or 'the photographer'
        return url, f'Photo: {creator} ({license_name.upper()}, via Openverse).'
    return None, None


def main():
    IMAGES.mkdir(parents=True, exist_ok=True)
    catalog = dummy_products()
    manifest = []
    for category, titles in DUMMYJSON.items():
        code = CODES[category]
        for index, title in enumerate(titles, start=1):
            sku = f'PB-{code}-{index:02d}'
            record = from_dummy(title, catalog)
            path = IMAGES / f'{sku}.jpg'
            if not path.exists() or path.stat().st_size < 8000:
                save_jpeg(get_bytes(record.pop('image_url')), path)
            else:
                record.pop('image_url')
            record.update(sku=sku, category=category, image=path.name, credit='')
            manifest.append(record)
            print(f'{sku} {category} {record["name"]} ৳{record["price"]}')
    for category, rows in CUSTOM.items():
        code = CODES[category]
        start = 1 + sum(1 for item in manifest if item['category'] == category)
        for offset, row in enumerate(rows):
            name, query, price, compare, stock, short, description = row
            sku = f'PB-{code}-{start + offset:02d}'
            path = IMAGES / f'{sku}.jpg'
            credit = ''
            if not path.exists() or path.stat().st_size < 8000:
                url, credit = openverse(query)
                if not url:
                    print(f'MISSING PHOTO {sku} {query}')
                    continue
                time.sleep(0.3)
                try:
                    save_jpeg(get_bytes(url), path)
                except Exception as error:
                    print(f'PHOTO FAILED {sku} {error}')
                    continue
            manifest.append({
                'sku': sku,
                'category': category,
                'name': name,
                'price': price,
                'compare': compare,
                'stock': stock,
                'short': short,
                'description': description + (f'\n\n{credit}' if credit else ''),
                'image': path.name,
                'credit': credit,
            })
            print(f'{sku} {category} {name} ৳{price}')
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'Wrote {len(manifest)} products to {MANIFEST}')


if __name__ == '__main__':
    main()
