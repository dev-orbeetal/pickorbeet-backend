"""
Minimal client for the Steadfast Courier merchant API.

Docs: https://portal.packzy.com (Merchant panel > API). Every call sends the
``Api-Key`` and ``Secret-Key`` headers. Keys are read from settings and never
leave the server.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = (5, 15)  # (connect, read) seconds


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

    def _request(self, method, path, *, json=None):
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
