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

    def __init__(
        self,
        status='in_review',
        error=None,
        consignment_id=1424107,
        tracking_code='SF123456789BD',
        balance=1250.5,
        trackings=None,
    ):
        self.status = status
        self.error = error
        self.consignment_id = consignment_id
        self.tracking_code = tracking_code
        self.balance = balance
        self.trackings = trackings if trackings is not None else [
            {'status': 'pending', 'message': 'Picked up', 'updated_at': '2025-10-24 10:00:00'},
        ]
        self.created = []
        self.status_checks = []
        self.balance_checks = 0
        self.tracking_lookups = []

    def create_order(self, **kwargs):
        if self.error:
            raise self.error
        self.created.append(kwargs)
        return {
            'consignment_id': self.consignment_id,
            'invoice': kwargs['invoice'],
            'tracking_code': self.tracking_code,
            'tracking_link': 'https://steadfast.com.bd/t/a1b2c3d4',
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

    def get_balance(self):
        self.balance_checks += 1
        if self.error:
            raise self.error
        return self.balance

    def trackings_by_invoice(self, invoice):
        self.tracking_lookups.append(invoice)
        if self.error:
            raise self.error
        return list(self.trackings)

    def police_stations(self):
        if self.error:
            raise self.error
        return list(POLICE_STATIONS)


def _district(district_id, name, *stations):
    return {
        'Id': district_id,
        'Name': name,
        'PoliceStations': [
            {'Id': station_id, 'Name': station, 'DistrictId': district_id, 'HubId': 3}
            for station_id, station in stations
        ],
    }


# The shape Steadfast's GET /police_stations returns, with its older spellings.
POLICE_STATIONS = [
    _district(1, 'Dhaka', (17, 'Dhanmondi'), (18, 'Mirpur Model'), (19, 'Mirpur'), (20, 'Gulshan')),
    _district(2, 'Noakhali', (201, 'Noakhali Sadar'), (202, 'Begumganj'), (203, 'Companiganj')),
    _district(3, 'Chittagong', (301, 'Kotwali'), (302, 'Panchlaish')),
    _district(4, 'Comilla', (401, 'Comilla Sadar Dakshin'), (402, 'Kotwali Comilla')),
]


TIMEOUT = requests.Timeout('slow')
CONNECTION_ERROR = requests.ConnectionError('down')
GENERIC = SteadfastError('boom')
