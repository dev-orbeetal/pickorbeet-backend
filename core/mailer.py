"""Branded mail rendering.

Sent messages are static table HTML. A browser preview can pass ``motion=True``
to add entrance animation; that stylesheet is never attached to ``send_mail``.
"""
import logging
import re
from decimal import Decimal
from urllib.parse import quote

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

TRACKER_LABELS = (
    'Order Placed',
    'Processing',
    'Shipped',
    'Out for Delivery',
    'Delivered',
)
FONT = "'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
MONEY_FONT = "'Kohinoor Bangla', 'Noto Sans Bengali', 'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


def frontend(*parts):
    base = settings.FRONTEND_URL.rstrip('/')
    tail = '/'.join(part.strip('/') for part in parts if part)
    return f'{base}/{tail}' if tail else base


def public_base():
    configured = getattr(settings, 'PUBLIC_BASE_URL', '') or ''
    return (configured or settings.FRONTEND_URL).rstrip('/')


def asset(name):
    return f'{frontend()}/images/email/{name}.png'


def absolute_media(url):
    if not url:
        return ''
    if url.startswith('http://') or url.startswith('https://'):
        return url
    return f'{public_base()}/{url.lstrip("/")}'


def format_taka(amount):
    """৳1,080 for whole taka, ৳1,080.50 when there are paise."""
    if amount is None or amount == '':
        return ''
    value = Decimal(amount)
    if value == value.to_integral_value():
        return f'৳{int(value):,}'
    return f'৳{value:,.2f}'


def format_when(dt, with_time=False):
    if not dt:
        return ''
    local = timezone.localtime(dt) if timezone.is_aware(dt) else dt
    month = local.strftime('%b')
    if not with_time:
        return f'{local.day} {month} {local.year}'
    hour = local.strftime('%I')
    return f'{local.day} {month} {local.year}, {hour}:{local.strftime("%M")} {local.strftime("%p")}'


def display_order_number(order):
    number = str(order.order_number)
    return number if number.startswith('#') else f'#{number}'


def build_tracker(active_index, dates):
    """Five-step shipment tracker. ``dates`` aligns with ``TRACKER_LABELS``."""
    blue = '#2864E8'
    mute = '#E1E7F2'
    last = len(TRACKER_LABELS) - 1
    steps = []
    for index, label in enumerate(TRACKER_LABELS):
        reached = index <= active_index
        steps.append({
            'label': label,
            'date': dates[index] if reached else '',
            'dot': blue if reached else '#D5DCE8',
            'left': 'transparent' if index == 0 else (blue if reached else mute),
            'right': 'transparent' if index == last else (blue if index < active_index else mute),
        })
    return steps


def brand_context():
    home = frontend()
    social = [
        ('Facebook', settings.EMAIL_FACEBOOK_URL, 'social-facebook'),
        ('X', settings.EMAIL_X_URL, 'social-x'),
        ('YouTube', settings.EMAIL_YOUTUBE_URL, 'social-youtube'),
        ('LinkedIn', settings.EMAIL_LINKEDIN_URL, 'social-linkedin'),
    ]
    return {
        'frontend_url': home,
        'logo_url': f'{home}/images/logo.png',
        'font': FONT,
        'money_font': MONEY_FONT,
        'support_email': settings.SUPPORT_EMAIL,
        'support_phone': settings.SUPPORT_PHONE,
        'app_store_url': settings.APP_STORE_URL,
        'play_store_url': settings.PLAY_STORE_URL,
        'shop_url': frontend('products'),
        'account_url': frontend('account'),
        'cart_url': frontend('cart'),
        'offers_url': f'{frontend("products")}?on_sale=1',
        'nav': [
            {'label': 'Electronics', 'href': frontend('category', 'electronics')},
            {'label': 'Accessories', 'href': frontend('products')},
            {'label': 'Offers', 'href': f'{frontend("products")}?on_sale=1'},
            {'label': 'My Account', 'href': frontend('account')},
        ],
        'social': [
            {'name': name, 'href': href, 'icon': asset(icon)}
            for name, href, icon in social if href
        ],
        'assets': {
            'bag': asset('bag'),
            'parcel': asset('parcel'),
            'truck': asset('truck'),
            'open_box': asset('open-box'),
            'lock': asset('lock'),
            'envelope': asset('envelope'),
            'sale': asset('sale'),
            'cart': asset('cart'),
            'phone': asset('phone'),
            'check': asset('check'),
            'icon_range': asset('icon-range'),
            'icon_pay': asset('icon-pay'),
            'icon_ship': asset('icon-ship'),
            'icon_genuine': asset('icon-genuine'),
            'icon_cod': asset('icon-cod'),
            'icon_returns': asset('icon-returns'),
            'icon_secure': asset('icon-secure'),
            'icon_cart': asset('icon-cart'),
            'icon_grid': asset('icon-grid'),
            'glyph_cart': asset('glyph-cart'),
            'glyph_grid': asset('glyph-grid'),
            'product_fallback': asset('product-fallback'),
        },
        'motion': False,
        'footer_mode': 'support',
        'support_line': '',
        'preheader': '',
    }


def plain_text(html):
    lines = []
    for line in strip_tags(html).splitlines():
        clean = re.sub(r'\s+', ' ', line).strip()
        if clean:
            lines.append(clean)
    return '\n'.join(lines)


def render_branded(template, context, *, motion=False):
    payload = {**brand_context(), **context, 'motion': motion}
    html = render_to_string(template, payload)
    return html, plain_text(html)


def send_branded(subject, template, context, recipient):
    if not recipient:
        return False
    html, text = render_branded(template, context, motion=False)
    send_mail(
        subject=subject,
        message=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient],
        html_message=html,
        fail_silently=False,
    )
    return True


def product_url(product):
    if product is not None and getattr(product, 'slug', None):
        return frontend('product', product.slug)
    return frontend('products')


def product_image(product):
    image = ''
    if product is not None:
        try:
            image = product.primary_image or ''
        except Exception:
            logger.warning('Could not read a product image for email', exc_info=True)
            image = ''
    return absolute_media(image) or asset('product-fallback')


def track_url(order):
    return f'{frontend("track-order")}?order={quote(str(order.order_number))}'
