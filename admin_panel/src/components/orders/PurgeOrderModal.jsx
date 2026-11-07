import { useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { usePurgeOrderMutation } from '@/store/api/ordersApi';

const MIN_REASON = 5;

export default function PurgeOrderModal({ order, open, onClose, onDeleted }) {
  const [typed, setTyped] = useState('');
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [purgeOrder, { isLoading }] = usePurgeOrderMutation();

  if (!open || !order) return null;

  const parcelActive = Boolean(order.shipment?.consignment_id) && !order.shipment?.is_final;
  const matches = typed.trim().toUpperCase() === String(order.order_number).toUpperCase();
  const ready = matches && reason.trim().length >= MIN_REASON && !parcelActive && !isLoading;

  const close = () => {
    if (isLoading) return;
    setTyped('');
    setReason('');
    setError('');
    onClose();
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!ready) return;
    setError('');
    try {
      const result = await purgeOrder({ id: order.id, order_number: typed.trim(), reason: reason.trim() }).unwrap();
      toast.success(result.detail || 'Order deleted');
      onDeleted();
    } catch (err) {
      setError(err?.data?.error || 'Could not delete this order');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={close} />
      <form onSubmit={submit} className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden">
        <div className="px-6 py-5 bg-red-50 border-b flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
              <AlertTriangle className="w-5 h-5 text-red-600" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Delete order permanently</h3>
              <p className="text-sm text-gray-500">{order.order_number}</p>
            </div>
          </div>
          <button type="button" onClick={close} className="p-1 hover:bg-gray-200 rounded-lg transition-colors">
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        <div className="px-6 py-5 space-y-4 text-sm">
          <p className="text-gray-700">
            The order, its items, payments and history are removed, and it drops out of every report.
            Stock it took goes back to the warehouse. A copy is kept in the deletion log. This cannot be undone.
          </p>
          {parcelActive && (
            <p className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-800">
              Steadfast still has this parcel. Cancel it in the Steadfast portal and refresh its status first.
            </p>
          )}
          <div>
            <label htmlFor="purge-number" className="block font-medium text-gray-700 mb-1.5">
              Type <span className="font-mono">{order.order_number}</span> to confirm
            </label>
            <input
              id="purge-number"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              autoComplete="off"
              className="input w-full font-mono"
            />
          </div>
          <div>
            <label htmlFor="purge-reason" className="block font-medium text-gray-700 mb-1.5">Reason</label>
            <textarea
              id="purge-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              maxLength={500}
              placeholder="For example: demo order placed while testing the shop"
              className="w-full px-3 py-2.5 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent resize-none placeholder-gray-400"
            />
          </div>
          {error && <p className="text-red-700">{error}</p>}
        </div>

        <div className="px-6 py-4 bg-gray-50 border-t flex justify-end gap-3">
          <button
            type="button"
            onClick={close}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-xl hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!ready}
            className="px-5 py-2 text-sm font-medium rounded-xl bg-red-600 text-white hover:bg-red-700 disabled:bg-red-300"
          >
            {isLoading ? 'Deleting…' : 'Delete permanently'}
          </button>
        </div>
      </form>
    </div>
  );
}
