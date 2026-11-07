"""Invoice PDF for an order, and the signed links that download it.

Noto Sans covers Latin text; Noto Sans Bengali covers the taka sign and Bangla
names. Both are under the SIL Open Font License (fonts/OFL.txt).
"""
import time
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core import signing
from django.urls import reverse
from fpdf import FPDF
from fpdf.enums import XPos, YPos

from core.mailer import format_taka, format_when

FONT_DIR = Path(__file__).resolve().parent / 'fonts'
SIGNING_SALT = 'orders.invoice'
EMAIL_LINK_SECONDS = 30 * 24 * 60 * 60
APP_LINK_SECONDS = 10 * 60
INVOICE_STATUSES = {'shipped', 'out_for_delivery', 'delivered'}

INK = (23, 32, 51)
MUTED = (104, 115, 134)
LINE = (227, 233, 244)
ACCENT = (40, 100, 232)


def invoice_available(order):
    return order.order_type in ('online', 'external') and order.order_status in INVOICE_STATUSES


def invoice_filename(order):
    return f'PickOrbeet-invoice-{order.order_number}.pdf'


# -- links -----------------------------------------------------------------------------

def invoice_token(order, seconds):
    return signing.dumps({'o': str(order.pk), 'exp': int(time.time()) + int(seconds)}, salt=SIGNING_SALT)


def order_id_from_token(token):
    """The order id in a valid, unexpired token, else None."""
    try:
        payload = signing.loads(token, salt=SIGNING_SALT)
    except signing.BadSignature:
        return None
    if not isinstance(payload, dict) or int(payload.get('exp') or 0) < time.time():
        return None
    return payload.get('o')


def invoice_url(order, seconds=EMAIL_LINK_SECONDS):
    path = reverse('invoice_download', kwargs={'token': invoice_token(order, seconds)})
    return f'{settings.API_PUBLIC_URL.rstrip("/")}{path}'


# -- PDF -------------------------------------------------------------------------------

def _store():
    from apps.products.models import StoreSettings

    return StoreSettings.objects.first()


def _address_lines(name, phone, line1, line2, city, post_office, district, postal_code, email=''):
    place = ', '.join(part for part in (city, post_office) if part)
    region = ' '.join(part for part in (district, postal_code) if part)
    return [part for part in (name, phone, email, line1, line2, place, region) if part]


def _item_details(item):
    details = []
    for option in item.options or []:
        if isinstance(option, dict) and option.get('label'):
            details.append(f"{option.get('name') or 'Option'}: {option['label']}")
    if not details:
        details += [f'Size: {item.size}'] if item.size else []
        details += [f'Color: {item.color}'] if item.color else []
    if item.product_sku:
        details.append(f'SKU: {item.product_sku}')
    return ' · '.join(details)


class _InvoicePDF(FPDF):
    def __init__(self, footer_text):
        super().__init__(format='A4', unit='mm')
        self.footer_text = footer_text
        self.add_font('Noto', '', str(FONT_DIR / 'NotoSans-Regular.ttf'))
        self.add_font('Noto', 'B', str(FONT_DIR / 'NotoSans-Bold.ttf'))
        self.add_font('NotoBengali', '', str(FONT_DIR / 'NotoSansBengali-Regular.ttf'))
        self.add_font('NotoBengali', 'B', str(FONT_DIR / 'NotoSansBengali-Bold.ttf'))
        self.set_fallback_fonts(['NotoBengali'], exact_match=False)
        self.set_text_shaping(True)
        self.set_margins(16, 16, 16)
        self.set_auto_page_break(True, margin=22)

    def footer(self):
        self.set_y(-16)
        self.set_font('Noto', '', 8)
        self.set_text_color(*MUTED)
        self.cell(0, 4, self.footer_text, align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.cell(0, 4, f'Page {self.page_no()} of {{nb}}', align='C')


def _text(pdf, size, text, *, bold=False, color=INK, height=None, align='L', width=0):
    pdf.set_font('Noto', 'B' if bold else '', size)
    pdf.set_text_color(*color)
    pdf.multi_cell(width, height or size * 0.5, text, align=align, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _block(pdf, x, y, width, title, lines):
    pdf.set_xy(x, y)
    pdf.set_font('Noto', 'B', 8)
    pdf.set_text_color(*MUTED)
    pdf.cell(width, 5, title.upper(), new_x=XPos.LEFT, new_y=YPos.NEXT)
    for index, line in enumerate(lines):
        pdf.set_x(x)
        pdf.set_font('Noto', 'B' if index == 0 else '', 10 if index == 0 else 9)
        pdf.set_text_color(*INK)
        pdf.multi_cell(width, 4.8, line, new_x=XPos.LEFT, new_y=YPos.NEXT)
    return pdf.get_y()


def build_invoice_pdf(order):
    """The invoice as PDF bytes."""
    store = _store()
    phone = (store.contact_phone_1 if store else '') or settings.SUPPORT_PHONE
    email = (store.contact_email_1 if store else '') or settings.SUPPORT_EMAIL
    address = ' '.join(((store.contact_address if store else '') or '').split())
    pdf = _InvoicePDF(f'PickOrbeet · {phone} · {email}')
    pdf.alias_nb_pages()
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin

    # Header: store on the left, invoice number on the right.
    top = pdf.get_y()
    pdf.set_font('Noto', 'B', 20)
    pdf.set_text_color(*ACCENT)
    pdf.cell(width / 2, 9, 'PickOrbeet', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    for line in (address, f'{phone} · {email}'):
        if line:
            _text(pdf, 8.5, line, color=MUTED, height=4.4, width=width / 2)
    left_bottom = pdf.get_y()

    pdf.set_xy(pdf.l_margin + width / 2, top)
    pdf.set_font('Noto', 'B', 20)
    pdf.set_text_color(*INK)
    pdf.cell(width / 2, 9, 'INVOICE', align='R', new_x=XPos.LEFT, new_y=YPos.NEXT)
    rows = [
        ('Invoice', order.order_number),
        ('Order date', format_when(order.created_at)),
        ('Shipped', format_when(order.shipped_at)),
        ('Delivered', format_when(order.delivered_at)),
        ('Payment', ' · '.join(part for part in (
            order.get_payment_status_display(), (order.payment_method or '').upper()) if part)),
    ]
    for label, value in rows:
        if not value:
            continue
        pdf.set_x(pdf.l_margin + width / 2)
        pdf.set_font('Noto', '', 9)
        pdf.set_text_color(*MUTED)
        pdf.cell(width / 4, 5, label, align='R')
        pdf.set_font('Noto', 'B', 9)
        pdf.set_text_color(*INK)
        pdf.cell(width / 4, 5, value, align='R', new_x=XPos.LEFT, new_y=YPos.NEXT)
        pdf.set_x(pdf.l_margin + width / 2)
    pdf.set_y(max(left_bottom, pdf.get_y()) + 4)
    pdf.set_draw_color(*LINE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + width, pdf.get_y())

    # Bill to and ship to.
    ship = _address_lines(
        order.shipping_name, order.shipping_phone, order.shipping_address_line1, order.shipping_address_line2,
        order.shipping_city, order.shipping_post_office, order.shipping_district, order.shipping_postal_code,
    )
    if order.billing_address_line1:
        bill = _address_lines(
            order.billing_name or order.customer_name, order.billing_phone or '', order.billing_address_line1,
            order.billing_address_line2, order.billing_city, order.billing_post_office,
            order.billing_district, order.billing_postal_code, order.customer_email or '',
        )
    else:
        bill = [part for part in (order.customer_name, order.customer_phone, order.customer_email) if part]
    y = pdf.get_y() + 4
    bottom = max(
        _block(pdf, pdf.l_margin, y, width / 2 - 4, 'Bill to', bill),
        _block(pdf, pdf.l_margin + width / 2, y, width / 2, 'Ship to', ship),
    )
    pdf.set_y(bottom + 6)

    # Items.
    pdf.set_font('Noto', '', 9)
    pdf.set_text_color(*INK)
    pdf.set_draw_color(*LINE)
    with pdf.table(
        col_widths=(58, 10, 16, 16),
        text_align=('LEFT', 'CENTER', 'RIGHT', 'RIGHT'),
        line_height=5,
        padding=(2, 2),
        borders_layout='HORIZONTAL_LINES',
        headings_style=_heading_style(),
    ) as table:
        table.row(['Item', 'Qty', 'Unit price', 'Total'])
        for item in order.items.all():
            details = _item_details(item)
            name = f'{item.product_name}\n{details}' if details else item.product_name
            table.row([name, str(item.quantity), format_taka(item.unit_price), format_taka(item.total_price)])

    # Totals.
    paid = order.total if order.payment_status == 'paid' else Decimal('0')
    due = max(Decimal(order.total) - Decimal(paid), Decimal('0'))
    discount_label = f'Discount ({order.coupon_code})' if order.coupon_code else 'Discount'
    totals = [('Subtotal', format_taka(order.subtotal), False)]
    if order.discount:
        totals.append((discount_label, f'-{format_taka(order.discount)}', False))
    totals += [
        ('Delivery', format_taka(order.delivery_charge), False),
        ('Total', format_taka(order.total), True),
        ('Paid', format_taka(paid), False),
        ('Due on delivery', format_taka(due), True),
    ]
    pdf.ln(4)
    for label, value, strong in totals:
        pdf.set_x(pdf.l_margin + width * 0.55)
        pdf.set_font('Noto', 'B' if strong else '', 10 if strong else 9)
        pdf.set_text_color(*(INK if strong else MUTED))
        pdf.cell(width * 0.25, 6, label)
        pdf.set_text_color(*INK)
        pdf.cell(width * 0.20, 6, value, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Courier and the warranty note.
    shipment = getattr(order, 'shipment', None)
    pdf.ln(6)
    if shipment is not None and (shipment.tracking_code or shipment.consignment_id):
        courier = ' · '.join(part for part in (
            shipment.get_courier_display(),
            f'Tracking {shipment.tracking_code}' if shipment.tracking_code else '',
            f'Consignment {shipment.consignment_id}' if shipment.consignment_id else '',
        ) if part)
        _text(pdf, 9, f'Courier: {courier}', height=5)
    _text(
        pdf, 9,
        'Please keep this invoice. You will need it for warranty claims, returns and exchanges.',
        color=MUTED, height=5,
    )
    return bytes(pdf.output())


def _heading_style():
    from fpdf.fonts import FontFace

    return FontFace(emphasis='BOLD', color=MUTED, fill_color=(246, 248, 252))
