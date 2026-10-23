"""
Test doubles for the Steadfast HTTP API.
"""
import requests

from apps.shipping.steadfast import SteadfastError


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError('not json')
        return self._payload


class FakeSession:
    """Records requests and replays queued responses (or raises queued exceptions)."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append({'method': method, 'url': url, **kwargs})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    """Stands in for SteadfastClient in service and view tests."""

    is_configured = True

    def __init__(self, status='in_review', error=None, consignment_id=1424107, tracking_code='SF123456789BD'):
        self.status = status
        self.error = error
        self.consignment_id = consignment_id
        self.tracking_code = tracking_code
        self.created = []
        self.status_checks = []

    def create_order(self, **kwargs):
        if self.error:
            raise self.error
        self.created.append(kwargs)
        return {
            'consignment_id': self.consignment_id,
            'invoice': kwargs['invoice'],
            'tracking_code': self.tracking_code,
            'recipient_name': kwargs['recipient_name'],
            'recipient_phone': kwargs['recipient_phone'],
            'recipient_address': kwargs['recipient_address'],
            'cod_amount': kwargs['cod_amount'],
            'status': 'in_review',
            '_message': 'Consignment has been created successfully.',
        }

    def status_by_cid(self, consignment_id):
        self.status_checks.append(consignment_id)
        if self.error:
            raise self.error
        return self.status

    def status_by_tracking_code(self, code):
        return self.status_by_cid(code)


TIMEOUT = requests.Timeout('slow')
CONNECTION_ERROR = requests.ConnectionError('down')
GENERIC = SteadfastError('boom')
