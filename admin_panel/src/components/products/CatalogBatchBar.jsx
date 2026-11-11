import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { useAdjustCatalogImportMutation } from '@/store/api/productsApi';
import { providerLabel } from '@/components/products/ProviderBadge';

const LEAVE = '';

export default function CatalogBatchBar({ batches, batchId, onBatchChange, loading }) {
  const batch = batches.find((row) => row.id === batchId) || batches[0] || null;
  const [percent, setPercent] = useState('');
  const [active, setActive] = useState(LEAVE);
  const [dealer, setDealer] = useState(LEAVE);
  const [warranty, setWarranty] = useState('');
  const [adjust, { isLoading }] = useAdjustCatalogImportMutation();

  useEffect(() => {
    setPercent('');
    setActive(LEAVE);
    setDealer(LEAVE);
    setWarranty('');
  }, [batch?.id]);

  if (loading && !batches.length) {
    return <p className="mb-6 text-sm text-gray-500">Loading imported batches…</p>;
  }
  if (!batch) {
    return <p className="mb-6 text-sm text-gray-500">No imported batch for this provider yet.</p>;
  }

  const apply = async () => {
    const body = {};
    if (percent.trim() !== '') {
      const value = Number(percent);
      if (!Number.isFinite(value)) {
        toast.error('Enter a price percent such as 10 or -5');
        return;
      }
      body.price_percent = value;
    }
    if (active !== LEAVE) body.is_active = active === 'true';
    if (dealer !== LEAVE) body.dealer_available = dealer === 'true';
    if (warranty.trim()) body.warranty_period = warranty.trim();
    if (!Object.keys(body).length) {
      toast.error('Choose a price change or a listing update');
      return;
    }

    const count = batch.product_count ?? 0;
    const pieces = [`Update ${count} product${count === 1 ? '' : 's'} in ${batch.label}?`];
    if (body.price_percent !== undefined) {
      const direction = body.price_percent < 0 ? 'lower' : 'raise';
      pieces.push(`This will ${direction} the current price by ${Math.abs(body.price_percent)}%.`);
    }
    if (!confirm(pieces.join(' '))) return;

    try {
      const result = await adjust({ id: batch.id, ...body }).unwrap();
      toast.success(`Updated ${result.updated} products in ${result.label}`);
      setPercent('');
      setActive(LEAVE);
      setDealer(LEAVE);
      setWarranty('');
    } catch (error) {
      const data = error?.data;
      const message = data?.detail || data?.price_percent || data?.warranty_period || 'Could not update this batch';
      toast.error(Array.isArray(message) ? message[0] : message);
    }
  };

  return (
    <div className="mb-6 rounded-xl border border-sky-100 bg-sky-50/60 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-gray-900">
            {providerLabel(batch.provider)} batch
          </p>
          <p className="text-xs text-gray-500">
            {batch.product_count ?? 0} product{(batch.product_count ?? 0) === 1 ? '' : 's'}. A percent changes the current price, and the compare price when there is one.
          </p>
        </div>
        {batches.length > 1 && (
          <select
            value={batch.id}
            onChange={(event) => onBatchChange(event.target.value)}
            className="input w-auto"
            aria-label="Import batch"
          >
            {batches.map((row) => (
              <option key={row.id} value={row.id}>
                {row.label} ({row.product_count})
              </option>
            ))}
          </select>
        )}
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs font-medium text-gray-600">
          Price percent
          <input
            type="number"
            step="0.01"
            value={percent}
            onChange={(event) => setPercent(event.target.value)}
            placeholder="10 or -5"
            className="input mt-1 w-32"
          />
        </label>
        <label className="text-xs font-medium text-gray-600">
          Listing
          <select
            value={active}
            onChange={(event) => setActive(event.target.value)}
            className="input mt-1 w-auto"
          >
            <option value="">Leave unchanged</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </label>
        <label className="text-xs font-medium text-gray-600">
          Dealer availability
          <select
            value={dealer}
            onChange={(event) => setDealer(event.target.value)}
            className="input mt-1 w-auto"
          >
            <option value="">Leave unchanged</option>
            <option value="true">On for the whole batch</option>
            <option value="false">Off for the whole batch</option>
          </select>
        </label>
        <label className="text-xs font-medium text-gray-600">
          Warranty
          <input
            type="text"
            maxLength={80}
            value={warranty}
            onChange={(event) => setWarranty(event.target.value)}
            placeholder="1 year"
            className="input mt-1 w-40"
          />
        </label>
        <button
          type="button"
          onClick={apply}
          disabled={isLoading}
          className="btn btn-primary"
        >
          {isLoading ? 'Updating…' : 'Apply to batch'}
        </button>
      </div>
    </div>
  );
}
