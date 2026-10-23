import { useState } from 'react';
import { Copy, ExternalLink, RefreshCw, Truck } from 'lucide-react';
import toast from 'react-hot-toast';

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

export default function SteadfastCard({ order, onBook, onRefresh, booking, refreshing }) {
  const [note, setNote] = useState('');
  const shipment = order.shipment;
  const booked = Boolean(shipment?.consignment_id || shipment?.tracking_code);
  const canBook = !booked && order.order_type === 'online' && BOOKABLE.includes(order.order_status);

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
          {shipment.status_message && (
            <p className="text-gray-700 bg-gray-50 rounded-xl px-3 py-2">{shipment.status_message}</p>
          )}
          <div className="flex justify-between gap-3">
            <span className="text-gray-500">Cash to collect</span>
            <span className="font-medium">{money(shipment.cod_amount) || '৳0'}</span>
          </div>
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
            {shipment.tracking_url && (
              <a
                href={shipment.tracking_url}
                target="_blank"
                rel="noreferrer"
                className="btn btn-secondary text-sm"
              >
                <ExternalLink className="w-4 h-4 mr-1.5" />
                Open tracking
              </a>
            )}
            <button type="button" onClick={onRefresh} disabled={refreshing} className="btn btn-secondary text-sm">
              <RefreshCw className={`w-4 h-4 mr-1.5 ${refreshing ? 'animate-spin' : ''}`} />
              {refreshing ? 'Checking…' : 'Refresh status'}
            </button>
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
        <div className="space-y-3">
          <p className="text-sm text-gray-600">
            Send this parcel to Steadfast. The order is marked shipped when the consignment is created.
          </p>
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={2}
            maxLength={500}
            placeholder="Note for the rider (optional)"
            className="w-full px-3 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
          />
          <button type="button" onClick={() => onBook(note.trim())} disabled={booking} className="btn btn-primary w-full">
            {booking ? 'Booking…' : 'Book with Steadfast'}
          </button>
        </div>
      ) : (
        <p className="text-sm text-gray-500">
          {order.order_type !== 'online'
            ? 'In-shop orders are not sent by courier.'
            : 'This order cannot be booked with Steadfast.'}
        </p>
      )}
    </div>
  );
}
