"""DEBUG-only browser preview of the branded emails, including entrance motion."""
from django.conf import settings
from django.http import Http404, HttpResponse

from core.mailer import asset, build_tracker, frontend, render_branded

SAMPLE_ITEM = {
    'name': 'Oraimo Necklace Lite (OEB-311)',
    'meta': 'Black | Qty: 1',
    'price': '৳1,080',
    'compare': '৳1,500',
    'image': asset('product-fallback'),
    'url': frontend('products'),
}


def _motion(request):
    return request.GET.get('motion', '1') != '0'


def _html(template, context, motion):
    html, _text = render_branded(template, context, motion=motion)
    return html


def _welcome(motion):
    return _html('emails/welcome.html', {
        'preheader': 'Glad to have you with us. Shop your favorite products at the best prices.',
        'footer_mode': 'split',
    }, motion)


def _otp(motion):
    return _html('emails/otp.html', {
        'preheader': 'Your verification code is 482916. It expires in 10 minutes.',
        'otp_digits': list('482916'),
        'footer_mode': 'support',
        'support_line': 'Need help? Contact us and we will sort it out.',
    }, motion)


def _reset(motion):
    return _html('emails/password_reset.html', {
        'preheader': 'Reset your PickOrbeet password. This link expires in 1 hour.',
        'reset_url': frontend('reset-password'),
        'footer_mode': 'support',
        'support_line': 'Need help? Contact us at the address below.',
    }, motion)


def _changed(motion):
    return _html('emails/password_changed.html', {
        'preheader': 'Your PickOrbeet password was changed.',
        'forgot_url': frontend('forgot-password'),
        'footer_mode': 'support',
        'support_line': 'Need help? Contact us at the address below.',
    }, motion)


def _confirmed(motion):
    return _html('emails/order_confirmed.html', {
        'preheader': '#PO783256 has been placed.',
        'footer_mode': 'support',
        'support_line': 'If you have any questions, feel free to contact our support team.',
        'order_number': '#PO783256',
        'meta_label': 'Order Date',
        'meta_value': '20 Oct 2026, 10:24 AM',
        'items': [SAMPLE_ITEM],
        'subtotal': '৳1,080',
        'delivery': '৳60',
        'discount': '',
        'total': '৳1,140',
        'details_url': frontend('orders'),
    }, motion)


def _on_the_way(motion, active=2):
    intro = (
        'Your order is out for delivery and will arrive soon.'
        if active == 3 else
        'Great news! Your order has been shipped and is on its way to you.'
    )
    dates = ['20 Oct 2026', '21 Oct 2026', '22 Oct 2026', '23 Oct 2026', '']
    return _html('emails/order_on_the_way.html', {
        'preheader': intro,
        'footer_mode': 'support',
        'support_line': 'If you have any questions about your order, contact us anytime.',
        'intro': intro,
        'order_number': '#PO783256',
        'meta_label': 'Expected Delivery',
        'meta_value': '27 Oct 2026',
        'steps': build_tracker(active, dates),
        'items': [SAMPLE_ITEM],
        'track_url': f'{frontend("track-order")}?order=PO783256',
    }, motion)


def _delivered(motion):
    return _html('emails/order_delivered.html', {
        'preheader': '#PO783256 was delivered.',
        'footer_mode': 'thanks',
        'order_number': '#PO783256',
        'meta_label': 'Delivered on',
        'meta_value': '12 Oct 2026, 04:20 PM',
        'items': [SAMPLE_ITEM],
        'review_url': frontend('products'),
        'buy_url': frontend('products'),
        'explore_url': frontend('products'),
    }, motion)


def _sale(motion):
    return _html('emails/mega_sale.html', {
        'preheader': 'Mega sale. Up to 60% off electronics.',
        'footer_mode': 'social',
        'discount': '60',
    }, motion)


def _cart(motion):
    return _html('emails/abandoned_cart.html', {
        'preheader': 'Your cart is waiting for you.',
        'footer_mode': 'contact',
        'items': [SAMPLE_ITEM],
    }, motion)


BUILDERS = {
    'welcome': _welcome,
    'otp': _otp,
    'password-reset': _reset,
    'password-changed': _changed,
    'order-confirmed': _confirmed,
    'order-on-the-way': _on_the_way,
    'order-out-for-delivery': lambda motion: _on_the_way(motion, active=3),
    'order-delivered': _delivered,
    'mega-sale': _sale,
    'abandoned-cart': _cart,
}

TITLES = {
    'welcome': 'Welcome',
    'otp': 'Verification code',
    'password-reset': 'Reset password',
    'password-changed': 'Password changed',
    'order-confirmed': 'Order confirmed',
    'order-on-the-way': 'On the way',
    'order-out-for-delivery': 'Out for delivery',
    'order-delivered': 'Delivered',
    'mega-sale': 'Mega sale',
    'abandoned-cart': 'Still thinking',
}


def email_preview(request, slug):
    if not settings.DEBUG:
        raise Http404('Email preview is only available in development.')
    builder = BUILDERS.get(slug)
    if builder is None:
        raise Http404('Unknown email.')
    return HttpResponse(builder(_motion(request)))


def email_preview_index(request):
    if not settings.DEBUG:
        raise Http404('Email preview is only available in development.')
    links = ''.join(
        f'<li style="margin:0 0 10px;"><a href="/emails/preview/{slug}/" style="color:#172033;font-weight:700;">{title}</a> '
        f'<a href="/emails/preview/{slug}/?motion=0" style="color:#687386;margin-left:8px;">still</a></li>'
        for slug, title in TITLES.items()
    )
    html = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>PickOrbeet email preview</title></head>
<body style="margin:0;background:#E4ECFD;font-family:Inter,Segoe UI,sans-serif;color:#172033;">
  <main style="max-width:640px;margin:40px auto;background:#fff;border-radius:24px;padding:28px 32px;">
    <h1 style="margin:0 0 8px;font-size:28px;">Email preview</h1>
    <p style="margin:0 0 20px;color:#687386;">Each card opens with the entrance motion. “Still” is the message that is actually sent.</p>
    <ul style="padding-left:18px;">{links}</ul>
  </main>
</body></html>'''
    return HttpResponse(html)
