import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Copy, ExternalLink, RefreshCw, Truck } from 'lucide-react';
import toast from 'react-hot-toast';
import { useGetBookingPreviewQuery } from '@/store/api/shippingApi';

const BOOKABLE = ['pending', 'confirmed', 'processing', 'shipped', 'out_for_delivery'];

const GROUP_STYLE = {
  in_review: 'bg-amber-50 text-amber-800 border-amber-200',
  pending: 'bg-blue-50 text-blue-800 border-blue-200',
  hold: 'bg-violet-50 text-violet-800 border-violet-200',
  delivered: 'bg-green-50 text-green-800 border-green-200',
  partial_delivered: 'bg-teal-50 text-teal-800 border-teal-200',
  cancelled: 'bg-red-50 text-red-800 border-red-200',
  unknown: 'bg-gray-50 text-gray-700 border-gray-200',
};

export function courierBadgeClass(group) {
  return GROUP_STYLE[group] || GROUP_STYLE.unknown;
}

function money(value) {
  const amount = parseFloat(value);
  if (Number.isNaN(amount)) return null;
  return `৳${amount.toLocaleString()}`;
}

function when(value) {
  if (!value) return null;
  return new Date(value).toLocaleString();
}

export function TrackingLinks({ shipment }) {
  const links = [
    [shipment.track_page_url, 'Customer tracking page'],
    [shipment.tracking_url, 'Open on Steadfast'],
    [shipment.portal_url, 'Steadfast portal'],
  ].filter(([href]) => href);
  return links.map(([href, label]) => (
    <a key={label} href={href} target="_blank" rel="noreferrer" className="btn btn-secondary text-sm">
      <ExternalLink className="w-4 h-4 mr-1.5" />
      {label}
    </a>
  ));
}

const MATCH_HINT = {
  matched: 'Thana found in the customer’s address.',
  chosen: 'Thana chosen by you.',
  sadar: 'No thana found in the address, so the district Sadar thana is used. Check it before booking.',
};

const FIELD = 'w-full px-3 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-500';

function BookingForm({ order, onBook, booking }) {
  const [note, setNote] = useState('');
  const [stationId, setStationId] = useState(null);
  const [address, setAddress] = useState('');
  const [edited, setEdited] = useState(false);
  const { data: preview, isFetching, isError, refetch } = useGetBookingPreviewQuery(
    { orderId: order.id, policeStationId: stationId },
    { refetchOnMountOrArgChange: true },
  );

  useEffect(() => {
    if (preview && !edited) setAddress(preview.recipient_address || '');
  }, [preview, edited]);

  const stations = preview?.police_stations || [];
  const selected = stationId ?? preview?.police_station?.id ?? '';
  const limit = preview?.address_limit || 250;
  let hint = MATCH_HINT[preview?.police_station_match];
  if (preview && !hint) {
    hint = stations.length
      ? 'No thana found. Pick one so Steadfast routes the parcel to the right area.'
      : `Steadfast's thana list has nothing for ${preview.district || 'this district'}. Make sure the address names the district.`;
  }

  const chooseStation = (value) => {
    setStationId(value ? Number(value) : null);
    setEdited(false);
  };

  const book = () => {
    if (!preview) {
      onBook({ note: note.trim() });
      return;
    }
    onBook({
      note: note.trim(),
      recipient_address: address.trim(),
      police_station_id: selected || null,
    });
  };

  return (
    <div className="space-y-3 text-sm">
      <p className="text-gray-600">
        Send this parcel to Steadfast. The order is marked shipped when the consignment is created.
      </p>
      {isError ? (
        <p className="text-amber-700 bg-amber-50 rounded-xl px-3 py-2">
          Couldn’t load the booking preview. Booking still sends the order’s address.{' '}
          <button type="button" onClick={refetch} className="underline font-medium">Try again</button>
        </p>
      ) : (
        <>
          <div>
            <label htmlFor="steadfast-thana" className="block text-gray-500 mb-1">
              Thana in {preview?.district || order.shipping_district || 'the district'}
            </label>
            <select
              id="steadfast-thana"
              value={selected}
              onChange={(event) => chooseStation(event.target.value)}
              disabled={!preview || stations.length === 0}
              className={FIELD}
            >
              <option value="">No thana</option>
              {stations.map((station) => (
                <option key={station.id} value={station.id}>{station.name}</option>
              ))}
            </select>
            {hint && (
              <p className={`mt-1 text-xs ${preview?.police_station_match === 'matched' || preview?.police_station_match === 'chosen' ? 'text-gray-500' : 'text-amber-700'}`}>
                {hint}
              </p>
            )}
          </div>
          <div>
            <div className="flex justify-between text-gray-500 mb-1">
              <label htmlFor="steadfast-address">Address sent to Steadfast</label>
              <span className="text-xs">{address.length}/{limit}</span>
            </div>
            <textarea
              id="steadfast-address"
              value={address}
              onChange={(event) => {
                setAddress(event.target.value);
                setEdited(true);
              }}
              rows={3}
              maxLength={limit}
              disabled={!preview}
              placeholder={isFetching ? 'Loading…' : ''}
              className={`${FIELD} resize-none`}
            />
            <p className="mt-1 text-xs text-gray-500">Steadfast reads the thana and district from this text.</p>
          </div>
          {preview?.phone_error && (
            <p className="text-red-700 bg-red-50 rounded-xl px-3 py-2">{preview.phone_error}</p>
          )}
          {preview && (
            <div className="flex justify-between gap-3">
              <span className="text-gray-500">Cash to collect</span>
              <span className="font-medium">{money(preview.cod_amount) || '৳0'}</span>
            </div>
          )}
        </>
      )}
      <textarea
        value={note}
        onChange={(event) => setNote(event.target.value)}
        rows={2}
        maxLength={500}
        placeholder="Note for the rider (optional)"
        className={`${FIELD} resize-none`}
      />
      <button
        type="button"
        onClick={book}
        disabled={booking || (!isError && (!preview || !address.trim() || Boolean(preview.phone_error)))}
        className="btn btn-primary w-full"
      >
        {booking ? 'Booking…' : 'Book with Steadfast'}
      </button>
    </div>
  );
}

export default function SteadfastCard({ order, onBook, onRefresh, booking, refreshing }) {
  const shipment = order.shipment;
  const booked = Boolean(shipment?.consignment_id || shipment?.tracking_code);
  const courierOrder = order.order_type === 'online' || order.order_type === 'external';
  const canBook = !booked && courierOrder && BOOKABLE.includes(order.order_status);

  const copyCode = async () => {
    if (!shipment?.tracking_code) return;
    await navigator.clipboard.writeText(shipment.tracking_code);
    toast.success('Tracking code copied');
  };

  return (
    <div className="card p-6">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Truck className="w-5 h-5 text-primary-600" />
            Steadfast
          </h2>
          <p className="text-xs text-gray-500 mt-1">Courier booking and live status</p>
        </div>
        {booked && (
          <span className={`badge border ${courierBadgeClass(shipment.status_group)}`}>
            {shipment.status_label || shipment.status}
          </span>
        )}
      </div>

      {booked ? (
        <div className="space-y-3 text-sm">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-gray-500">Tracking code</p>
              <p className="font-semibold text-gray-900">{shipment.tracking_code || 'Waiting for a code'}</p>
            </div>
            {shipment.tracking_code && (
              <button type="button" onClick={copyCode} className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg" title="Copy tracking code">
                <Copy className="w-4 h-4" />
              </button>
            )}
          </div>
          {shipment.consignment_id && (
            <div className="flex justify-between gap-3">
              <span className="text-gray-500">Consignment</span>
              <span className="font-medium text-gray-900">{shipment.consignment_id}</span>
            </div>
          )}
          {shipment.police_station_name && (
            <div className="flex justify-between gap-3">
              <span className="text-gray-500">Thana</span>
              <span className="font-medium text-gray-900">{shipment.police_station_name}</span>
            </div>
          )}
          {shipment.recipient_address && (
            <div>
              <p className="text-gray-500">Address sent</p>
              <p className="text-gray-900">{shipment.recipient_address}</p>
            </div>
          )}
          {shipment.status_message && (
            <p className="text-gray-700 bg-gray-50 rounded-xl px-3 py-2">{shipment.status_message}</p>
          )}
          <div className="flex justify-between gap-3">
            <span className="text-gray-500">Cash to collect</span>
            <span className="font-medium">{money(shipment.cod_amount) || '৳0'}</span>
          </div>
          {shipment.cod_mismatch && (
            <p className="text-amber-800 bg-amber-50 rounded-xl px-3 py-2">
              Steadfast will collect {money(shipment.courier_cod_amount) || '৳0'}, but this order needs{' '}
              {money(shipment.cod_amount) || '৳0'}. The amount was changed in the Steadfast portal; fix it there
              or update the order.
            </p>
          )}
          {shipment.delivery_charge != null && shipment.delivery_charge !== '' && (
            <div className="flex justify-between gap-3">
              <span className="text-gray-500">Courier charge</span>
              <span className="font-medium">{money(shipment.delivery_charge)}</span>
            </div>
          )}
          {shipment.booked_by_name && (
            <div className="flex justify-between gap-3">
              <span className="text-gray-500">Booked by</span>
              <span className="font-medium">{shipment.booked_by_name}</span>
            </div>
          )}
          {when(shipment.booked_at) && (
            <div className="flex justify-between gap-3">
              <span className="text-gray-500">Booked</span>
              <span>{when(shipment.booked_at)}</span>
            </div>
          )}
          {when(shipment.status_updated_at) && (
            <div className="flex justify-between gap-3">
              <span className="text-gray-500">Status updated</span>
              <span>{when(shipment.status_updated_at)}</span>
            </div>
          )}
          {shipment.note && (
            <p className="text-gray-600"><span className="text-gray-500">Note: </span>{shipment.note}</p>
          )}
          <div className="flex flex-wrap gap-2 pt-1">
            <TrackingLinks shipment={shipment} />
            <button type="button" onClick={onRefresh} disabled={refreshing} className="btn btn-secondary text-sm">
              <RefreshCw className={`w-4 h-4 mr-1.5 ${refreshing ? 'animate-spin' : ''}`} />
              {refreshing ? 'Checking…' : 'Refresh status'}
            </button>
            {shipment.id && (
              <Link href="/shipments/" className="btn btn-secondary text-sm">
                View in Shipments
              </Link>
            )}
          </div>
          {shipment.events?.length > 0 && (
            <div className="pt-3 border-t space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Courier updates</p>
              {shipment.events.map((event) => (
                <div key={event.id} className="flex gap-2">
                  <div className="w-1.5 h-1.5 mt-1.5 rounded-full bg-primary-500 shrink-0" />
                  <div>
                    <p className="font-medium text-gray-900 capitalize">
                      {(event.status || event.source || 'update').replace(/_/g, ' ')}
                    </p>
                    {event.message && <p className="text-gray-600">{event.message}</p>}
                    <p className="text-xs text-gray-400">{when(event.occurred_at || event.created_at)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : canBook ? (
        <BookingForm order={order} onBook={onBook} booking={booking} />
      ) : (
        <p className="text-sm text-gray-500">
          {!courierOrder
            ? 'Only online and external orders can be sent by courier.'
            : 'This order cannot be booked with Steadfast.'}
        </p>
      )}
    </div>
  );
}
