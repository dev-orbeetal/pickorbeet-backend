"""
Minimal client for the Steadfast Courier merchant API.

Docs: https://portal.packzy.com (Merchant panel > API). Every call sends the
``Api-Key`` and ``Secret-Key`` headers. Keys are read from settings and never
leave the server.
"""
import html
import logging
import re

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = (5, 15)  # (connect, read) seconds

# The public tracking page Steadfast gives us. Anything else is not fetched.
PUBLIC_TRACKING_URL = re.compile(r'^https://steadfast\.com\.bd/t(?:l)?/[A-Za-z0-9_-]{8,80}$')
_ASSIGNED_SECTION = re.compile(
    r'class="sf-card-title">\s*Assigned to\s*</h2>(?P<body>.*?)</section>',
    re.IGNORECASE | re.DOTALL,
)
_RIDER_NAME = re.compile(r'class="sf-person__name">([^<]+)</p>', re.IGNORECASE)
_RIDER_PHONE = re.compile(r'class="sf-person__meta">([^<]*)</p>', re.IGNORECASE)
_BD_MOBILE = re.compile(r'^01\d{9}$')


def parse_assigned_rider(page):
    """Name and phone from the public tracking page's Assigned to card.

    Returns ``('', '')`` when that card is missing. The recipient block is ignored.
    """
    section = _ASSIGNED_SECTION.search(page or '')
    if section is None:
        return '', ''
    body = section.group('body')
    name_match = _RIDER_NAME.search(body)
    phone_match = _RIDER_PHONE.search(body)
    name = html.unescape(' '.join(name_match.group(1).split()))[:100] if name_match else ''
    digits = re.sub(r'\D', '', html.unescape(phone_match.group(1)) if phone_match else '')
    if digits.startswith('880') and len(digits) == 13:
        digits = '0' + digits[3:]
    phone = digits if _BD_MOBILE.fullmatch(digits) else ''
    if not name:
        return '', ''
    return name, phone


class SteadfastError(Exception):
    """Base class. ``code`` is a stable machine-readable reason."""

    code = 'courier_error'
    retryable = False

    def __init__(self, message, *, status_code=None, payload=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload or {}


class SteadfastConfigError(SteadfastError):
    code = 'courier_not_configured'


class SteadfastAuthError(SteadfastError):
    code = 'courier_auth_failed'


class SteadfastValidationError(SteadfastError):
    code = 'courier_rejected'


class SteadfastDuplicateError(SteadfastValidationError):
    code = 'courier_duplicate_invoice'


class SteadfastNotFoundError(SteadfastError):
    code = 'courier_not_found'


class SteadfastNetworkError(SteadfastError):
    code = 'courier_unavailable'
    retryable = True


def _first_error(payload):
    """Flatten Steadfast's error shapes into one sentence."""
    if not isinstance(payload, dict):
        return ''
    errors = payload.get('errors')
    if isinstance(errors, dict):
        for field, messages in errors.items():
            if isinstance(messages, (list, tuple)) and messages:
                return str(messages[0])
            if messages:
                return f'{field}: {messages}'
    if isinstance(errors, (list, tuple)) and errors:
        return str(errors[0])
    return str(payload.get('message') or payload.get('error') or '')


def _looks_like_duplicate(payload, message):
    text = f'{message} {payload.get("errors", "")}'.lower()
    return 'invoice' in text and any(word in text for word in ('already', 'taken', 'exist', 'unique', 'duplicate'))


class SteadfastClient:
    def __init__(self, *, base_url=None, api_key=None, secret_key=None, timeout=DEFAULT_TIMEOUT, session=None):
        self.base_url = (base_url or settings.STEADFAST_BASE_URL).rstrip('/')
        self.api_key = api_key if api_key is not None else settings.STEADFAST_API_KEY
        self.secret_key = secret_key if secret_key is not None else settings.STEADFAST_SECRET_KEY
        self.timeout = timeout
        self.session = session or requests.Session()

    @property
    def is_configured(self):
        return bool(self.api_key and self.secret_key)

    # -- transport -----------------------------------------------------------------

    def _request(self, method, path, *, json=None, allow_list=False):
        if not self.is_configured:
            raise SteadfastConfigError('Steadfast API keys are not configured on the server.')

        url = f'{self.base_url}/{path.lstrip("/")}'
        headers = {
            'Api-Key': self.api_key,
            'Secret-Key': self.secret_key,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }
        try:
            response = self.session.request(
                method, url, json=json, headers=headers, timeout=self.timeout, allow_redirects=False,
            )
        except requests.Timeout as exc:
            raise SteadfastNetworkError('Steadfast did not respond in time.') from exc
        except requests.RequestException as exc:
            raise SteadfastNetworkError('Could not reach Steadfast.') from exc

        status_code = response.status_code
        if 300 <= status_code < 400:
            raise SteadfastError('Steadfast returned an unexpected redirect.', status_code=status_code)
        if status_code in (401, 403):
            raise SteadfastAuthError('Steadfast rejected the API keys.', status_code=status_code)
        if status_code == 429:
            raise SteadfastNetworkError('Steadfast rate limit reached. Try again shortly.', status_code=status_code)
        if status_code >= 500:
            raise SteadfastNetworkError('Steadfast is having trouble right now.', status_code=status_code)

        try:
            payload = response.json()
        except ValueError as exc:
            raise SteadfastError('Steadfast sent a response that is not JSON.', status_code=status_code) from exc
        if allow_list and isinstance(payload, list) and status_code < 400:
            return payload
        if not isinstance(payload, dict):
            raise SteadfastError('Steadfast sent an unexpected response.', status_code=status_code)

        # Steadfast also reports errors inside a 200 body as {"status": 400, ...}.
        body_status = payload.get('status')
        effective = body_status if isinstance(body_status, int) and body_status >= 400 else status_code
        if effective == 404:
            raise SteadfastNotFoundError(_first_error(payload) or 'Consignment not found.',
                                         status_code=effective, payload=payload)
        if effective >= 400:
            message = _first_error(payload) or 'Steadfast rejected the request.'
            error_cls = SteadfastDuplicateError if _looks_like_duplicate(payload, message) else SteadfastValidationError
            raise error_cls(message, status_code=effective, payload=payload)
        return payload

    # -- endpoints -----------------------------------------------------------------

    def create_order(self, *, invoice, recipient_name, recipient_phone, recipient_address, cod_amount,
                     note='', recipient_email=None, alternative_phone=None, item_description=None,
                     total_lot=None, delivery_type=None):
        """Create one consignment. Returns the ``consignment`` dict."""
        body = {
            'invoice': invoice,
            'recipient_name': recipient_name,
            'recipient_phone': recipient_phone,
            'recipient_address': recipient_address,
            'cod_amount': cod_amount,
            'note': note,
        }
        optional = {
            'recipient_email': recipient_email,
            'alternative_phone': alternative_phone,
            'item_description': item_description,
            'total_lot': total_lot,
            'delivery_type': delivery_type,
        }
        body.update({key: value for key, value in optional.items() if value not in (None, '')})

        payload = self._request('POST', '/create_order', json=body)
        consignment = payload.get('consignment')
        if not isinstance(consignment, dict) or not consignment.get('consignment_id'):
            raise SteadfastError('Steadfast did not return a consignment.', payload=payload)
        consignment['_message'] = payload.get('message', '')
        return consignment

    def _status(self, path):
        payload = self._request('GET', path)
        status = payload.get('delivery_status')
        if not status:
            raise SteadfastError('Steadfast did not return a delivery status.', payload=payload)
        return str(status)

    def status_by_cid(self, consignment_id):
        return self._status(f'/status_by_cid/{consignment_id}')

    def status_by_invoice(self, invoice):
        return self._status(f'/status_by_invoice/{invoice}')

    def status_by_tracking_code(self, tracking_code):
        return self._status(f'/status_by_trackingcode/{tracking_code}')

    def get_balance(self):
        """Return the merchant account balance as a float (taka)."""
        payload = self._request('GET', '/get_balance')
        raw = payload.get('current_balance', payload.get('balance'))
        if raw is None:
            raise SteadfastError('Steadfast did not return a balance.', payload=payload)
        try:
            return float(raw)
        except (TypeError, ValueError) as exc:
            raise SteadfastError('Steadfast returned an invalid balance.', payload=payload) from exc

    def police_stations(self):
        """Steadfast's thanas grouped by district: ``[{"Id", "Name", "PoliceStations": [...]}]``."""
        payload = self._request('GET', '/police_stations', allow_list=True)
        if isinstance(payload, dict):
            payload = payload.get('police_stations') or payload.get('data') or []
        if not isinstance(payload, list):
            raise SteadfastError('Steadfast did not return police stations.')
        return payload

    def fetch_public_tracking(self, url):
        """The public tracking page, or '' when the address is not Steadfast's or the page fails.

        This page is what shows the assigned rider. It needs no API key.
        """
        if not PUBLIC_TRACKING_URL.fullmatch(url or ''):
            return ''
        try:
            response = self.session.request(
                'GET',
                url,
                headers={'Accept': 'text/html', 'User-Agent': 'PickOrbeet/1.0'},
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.RequestException:
            logger.info('Steadfast tracking page unavailable')
            return ''
        if getattr(response, 'status_code', 0) != 200:
            return ''
        return (getattr(response, 'text', '') or '')[:300000]

    def trackings_by_invoice(self, invoice):
        """Return tracking timeline steps for an invoice (empty list if none).

        Steadfast's live response is ``{"tracking": [{"text", "created_at"}, ...]}``.
        Older examples used ``trackings``.
        """
        payload = self._request('GET', f'/trackings_by_invoice/{invoice}')
        steps = None
        for key in ('tracking', 'trackings', 'data'):
            value = payload.get(key)
            if isinstance(value, list):
                steps = value
                break
            if isinstance(value, dict):
                nested = value.get('tracking') or value.get('trackings') or value.get('data')
                if isinstance(nested, list):
                    steps = nested
                    break
        if steps is None and isinstance(payload, list):
            steps = payload
        if not isinstance(steps, list):
            raise SteadfastError('Steadfast did not return tracking steps.', payload=payload)
        return steps
