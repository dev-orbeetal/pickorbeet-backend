import { useMemo, useState } from 'react';
import Link from 'next/link';
import {
  Download, Eye, RefreshCw, Search, Truck, Wallet, X,
} from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import LoadError from '@/components/ui/LoadError';
import Pager from '@/components/ui/Pager';
import { TrackingLinks, courierBadgeClass } from '@/components/orders/SteadfastCard';
import { useGetOrdersQuery } from '@/store/api/ordersApi';
import {
  useBulkRefreshShipmentsMutation,
  useGetShipmentSummaryQuery,
  useGetShipmentsQuery,
  useGetSteadfastBalanceQuery,
  useImportShipmentMutation,
  useLazyGetShipmentQuery,
  usePreviewShipmentImportMutation,
  useRefreshShipmentMutation,
} from '@/store/api/shippingApi';

const STATUS_GROUPS = [
  { key: 'in_review', label: 'In review' },
  { key: 'pending', label: 'Pending' },
  { key: 'hold', label: 'Hold' },
  { key: 'delivered', label: 'Delivered' },
  { key: 'partial_delivered', label: 'Partial' },
  { key: 'cancelled', label: 'Cancelled' },
];

const OPEN_GROUPS = new Set(['in_review', 'pending', 'hold', 'unknown']);

const LIVE_POLLING = { pollingInterval: 30000, skipPollingIfUnfocused: true };

function money(value) {
  const amount = parseFloat(value);
  if (Number.isNaN(amount)) return '—';
  return `৳${amount.toLocaleString()}`;
}

function when(value) {
  if (!value) return '—';
  return new Date(value).toLocaleString();
}

function SyncHealth({ sync }) {
  const minutes = Math.round((sync.interval_seconds || 120) / 60);
  const lastRun = sync.last_run_at
    ? `Last check ${when(sync.last_run_at)}: ${sync.last_run_checked} checked, ${sync.last_run_changed} changed`
      + (sync.last_run_failed ? `, ${sync.last_run_failed} failed` : '')
    : 'No automatic check has run yet';
  return (
    <div
      className={`mb-6 rounded-xl px-4 py-3 text-sm ${
        sync.warning ? 'bg-amber-50 text-amber-900 border border-amber-200' : 'bg-gray-50 text-gray-600'
      }`}
    >
      {sync.warning && <p className="font-medium">{sync.warning}</p>}
      <p>
        Open parcels are checked with Steadfast every {minutes} minute{minutes === 1 ? '' : 's'}. {lastRun}.
        {' '}Last webhook: {sync.last_webhook_at ? when(sync.last_webhook_at) : 'none yet'}.
      </p>
    </div>
  );
}

export default function ShipmentsPage() {
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({
    status_group: '',
    search: '',
    booked_from: '',
    booked_to: '',
  });
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [liveSteps, setLiveSteps] = useState(null);
  const [loadingLive, setLoadingLive] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [importForm, setImportForm] = useState({
    consignment_id: '',
    tracking_code: '',
    orderSearch: '',
    order_id: '',
  });
  const [importPreview, setImportPreview] = useState(null);

  const queryParams = useMemo(() => {
    const params = { page };
    if (filters.status_group) params.status_group = filters.status_group;
    if (filters.search) params.search = filters.search;
    if (filters.booked_from) params.booked_from = filters.booked_from;
    if (filters.booked_to) params.booked_to = filters.booked_to;
    return params;
  }, [filters, page]);

  const summaryParams = useMemo(() => {
    const params = {};
    if (filters.booked_from) params.booked_from = filters.booked_from;
    if (filters.booked_to) params.booked_to = filters.booked_to;
    return params;
  }, [filters.booked_from, filters.booked_to]);

  const { data: balance, isFetching: balanceLoading, refetch: refetchBalance } = useGetSteadfastBalanceQuery();
  const { data: summary, isError: summaryError, refetch: refetchSummary } = useGetShipmentSummaryQuery(
    summaryParams,
    LIVE_POLLING,
  );
  const {
    data: shipmentsData,
    isLoading,
    isError,
    refetch,
  } = useGetShipmentsQuery(queryParams, LIVE_POLLING);
  const [refreshShipment] = useRefreshShipmentMutation();
  const [refreshingIds, setRefreshingIds] = useState(() => new Set());
  const [bulkRefresh, { isLoading: bulkRefreshing }] = useBulkRefreshShipmentsMutation();
  const [previewImport, { isLoading: previewing }] = usePreviewShipmentImportMutation();
  const [importShipment, { isLoading: importing }] = useImportShipmentMutation();
  const [fetchDetail] = useLazyGetShipmentQuery();

  const orderPickerParams = useMemo(() => {
    const params = { without_shipment: 1, page_size: 20, page: 1 };
    if (importForm.orderSearch.trim()) params.search = importForm.orderSearch.trim();
    return params;
  }, [importForm.orderSearch]);

  const { data: linkableOrdersData } = useGetOrdersQuery(orderPickerParams, { skip: !importOpen });
  const linkableOrders = Array.isArray(linkableOrdersData?.results)
    ? linkableOrdersData.results
    : (Array.isArray(linkableOrdersData) ? linkableOrdersData : []);

  const shipments = Array.isArray(shipmentsData?.results) ? shipmentsData.results : [];
  const byGroup = summary?.by_status_group || {};

  const updateFilters = (patch) => {
    setFilters((current) => ({ ...current, ...patch }));
    setPage(1);
  };

  const openDetail = async (row) => {
    setSelected(row);
    setDetail(row);
    setLiveSteps(null);
    try {
      const full = await fetchDetail({ id: row.id }).unwrap();
      setDetail(full);
      setSelected(full);
    } catch (error) {
      toast.error(error?.data?.error || 'Could not load shipment detail');
    }
  };

  const loadLiveTracking = async () => {
    if (!selected?.id) return;
    setLoadingLive(true);
    try {
      const full = await fetchDetail({ id: selected.id, live: true }).unwrap();
      setDetail(full);
      setLiveSteps(full.live_trackings ?? []);
      if (full.live_trackings == null) {
        toast.error('Live tracking is unavailable right now');
      }
    } catch (error) {
      toast.error(error?.data?.error || 'Could not load live tracking');
    } finally {
      setLoadingLive(false);
    }
  };

  const handleRefresh = async (id) => {
    if (refreshingIds.has(id)) return;
    setRefreshingIds((current) => new Set(current).add(id));
    try {
      const updated = await refreshShipment(id).unwrap();
      toast.success('Status refreshed');
      setSelected((current) => (current?.id === id ? updated : current));
      setDetail((current) => (current?.id === id ? updated : current));
    } catch (error) {
      toast.error(error?.data?.error || 'Refresh failed');
    } finally {
      setRefreshingIds((current) => {
        const next = new Set(current);
        next.delete(id);
        return next;
      });
    }
  };

  const handleBulkRefresh = async () => {
    const openIds = shipments
      .filter((row) => OPEN_GROUPS.has(row.status_group) || !row.is_final)
      .map((row) => row.id);
    if (!openIds.length) {
      toast.error('No open shipments on this page');
      return;
    }
    try {
      const result = await bulkRefresh({ ids: openIds, limit: openIds.length, pause: 0.2 }).unwrap();
      toast.success(`Checked ${result.checked}: ${result.changed} changed, ${result.failed} failed`);
    } catch (error) {
      toast.error(error?.data?.error || 'Bulk refresh failed');
    }
  };

  const openImport = () => {
    setImportOpen(true);
    setImportPreview(null);
    setImportForm({ consignment_id: '', tracking_code: '', orderSearch: '', order_id: '' });
  };

  const handlePreviewImport = async () => {
    try {
      const preview = await previewImport({
        consignment_id: importForm.consignment_id.trim(),
        tracking_code: importForm.tracking_code.trim(),
      }).unwrap();
      setImportPreview(preview);
      toast.success('Parcel found on Steadfast');
    } catch (error) {
      setImportPreview(null);
      toast.error(error?.data?.error || 'Could not look up that parcel');
    }
  };

  const handleImport = async () => {
    if (!importForm.order_id) {
      toast.error('Select an order to link');
      return;
    }
    try {
      const shipment = await importShipment({
        order_id: importForm.order_id,
        consignment_id: importForm.consignment_id.trim(),
        tracking_code: importForm.tracking_code.trim(),
      }).unwrap();
      toast.success('Shipment imported');
      setImportOpen(false);
      refetch();
      refetchSummary();
      openDetail(shipment);
    } catch (error) {
      toast.error(error?.data?.error || 'Import failed');
    }
  };

  return (
    <AdminLayout title="Shipments">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 flex items-center gap-2">
            <Truck className="w-6 h-6 text-primary-600" />
            Shipments
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Book new parcels from an order. Import portal-only Steadfast consignments here.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={openImport} className="btn btn-primary">
            <Download className="w-4 h-4 mr-2" />
            Import from Steadfast
          </button>
          <button
            type="button"
            onClick={handleBulkRefresh}
            disabled={bulkRefreshing || !shipments.length}
            className="btn btn-secondary"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${bulkRefreshing ? 'animate-spin' : ''}`} />
            {bulkRefreshing ? 'Refreshing…' : 'Refresh open on page'}
          </button>
        </div>
      </div>

      {summary?.sync && <SyncHealth sync={summary.sync} />}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 mb-6">
        <div className="card p-4 sm:col-span-2 xl:col-span-1">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Steadfast balance</p>
              <p className="text-2xl font-semibold text-gray-900 mt-1">
                {balanceLoading
                  ? '…'
                  : balance?.configured
                    ? money(balance.current_balance)
                    : 'Not configured'}
              </p>
              {balance?.error && <p className="text-xs text-red-600 mt-1">{balance.error}</p>}
            </div>
            <button
              type="button"
              onClick={() => refetchBalance()}
              className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg"
              title="Refresh balance"
            >
              <Wallet className="w-5 h-5" />
            </button>
          </div>
          {summary && (
            <p className="text-xs text-gray-500 mt-3">
              Open COD {money(summary.open_cod_total)} · {summary.open_count} open parcels
            </p>
          )}
        </div>

        {STATUS_GROUPS.map((group) => {
          const active = filters.status_group === group.key;
          return (
            <button
              key={group.key}
              type="button"
              onClick={() => updateFilters({ status_group: active ? '' : group.key })}
              className={`card p-4 text-left transition ${active ? 'ring-2 ring-primary-500' : 'hover:bg-gray-50'}`}
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">{group.label}</p>
              <p className="text-2xl font-semibold text-gray-900 mt-1">{byGroup[group.key] ?? 0}</p>
            </button>
          );
        })}
      </div>

      <div className="card mb-6">
        <div className="p-4 grid gap-3 md:grid-cols-4">
          <div className="relative md:col-span-2">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="search"
              value={filters.search}
              onChange={(e) => updateFilters({ search: e.target.value })}
              placeholder="Order, tracking, phone, consignment…"
              className="w-full pl-9 pr-3 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <input
            type="date"
            value={filters.booked_from}
            onChange={(e) => updateFilters({ booked_from: e.target.value })}
            className="w-full px-3 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <input
            type="date"
            value={filters.booked_to}
            onChange={(e) => updateFilters({ booked_to: e.target.value })}
            className="w-full px-3 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        {isError || summaryError ? (
          <LoadError onRetry={() => { refetch(); refetchSummary(); }} />
        ) : isLoading ? (
          <div className="p-8 text-center text-gray-500">Loading shipments…</div>
        ) : !shipments.length ? (
          <div className="p-8 text-center text-gray-500">No shipments match these filters.</div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-y bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
                    <th className="px-4 py-3 font-semibold">Order</th>
                    <th className="px-4 py-3 font-semibold">Customer</th>
                    <th className="px-4 py-3 font-semibold">Tracking</th>
                    <th className="px-4 py-3 font-semibold">Status</th>
                    <th className="px-4 py-3 font-semibold">COD</th>
                    <th className="px-4 py-3 font-semibold">Courier ৳</th>
                    <th className="px-4 py-3 font-semibold">Booked</th>
                    <th className="px-4 py-3 font-semibold">Checked</th>
                    <th className="px-4 py-3 font-semibold" />
                  </tr>
                </thead>
                <tbody>
                  {shipments.map((row) => (
                    <tr key={row.id} className="border-b last:border-0 hover:bg-gray-50/80">
                      <td className="px-4 py-3">
                        <Link href={`/orders/${row.order?.id}`} className="font-medium text-primary-700 hover:underline">
                          {row.order?.order_number || row.invoice}
                        </Link>
                      </td>
                      <td className="px-4 py-3">
                        <p className="font-medium text-gray-900">{row.order?.customer_name || row.recipient_name || '—'}</p>
                        <p className="text-xs text-gray-500">{row.recipient_phone || row.order?.customer_phone}</p>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">{row.tracking_code || '—'}</td>
                      <td className="px-4 py-3">
                        <span className={`badge border ${courierBadgeClass(row.status_group)}`}>
                          {row.status_label || row.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {money(row.courier_cod_amount != null && row.courier_cod_amount !== '' ? row.courier_cod_amount : row.cod_amount)}
                        {row.cod_mismatch && (
                          <span className="block text-xs text-amber-700" title="Booked amount differs from what Steadfast will collect">
                            Booked {money(row.cod_amount)}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">{row.delivery_charge != null ? money(row.delivery_charge) : '—'}</td>
                      <td className="px-4 py-3 text-xs text-gray-600">{when(row.booked_at)}</td>
                      <td className="px-4 py-3 text-xs text-gray-600">{when(row.last_checked_at)}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            type="button"
                            onClick={() => openDetail(row)}
                            className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg"
                            title="Details"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleRefresh(row.id)}
                            disabled={refreshingIds.has(row.id)}
                            className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg disabled:opacity-60"
                            title="Refresh status"
                          >
                            <RefreshCw className={`w-4 h-4 ${refreshingIds.has(row.id) ? 'animate-spin' : ''}`} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager
              page={page}
              count={shipmentsData?.count || 0}
              pageSize={20}
              onPage={setPage}
            />
          </>
        )}
      </div>

      {selected && detail && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={() => setSelected(null)}>
          <aside
            className="h-full w-full max-w-md bg-white shadow-xl overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sticky top-0 bg-white border-b px-5 py-4 flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-gray-500">Shipment</p>
                <h2 className="text-lg font-semibold text-gray-900">{detail.tracking_code || detail.invoice}</h2>
                <span className={`badge border mt-2 ${courierBadgeClass(detail.status_group)}`}>
                  {detail.status_label || detail.status}
                </span>
              </div>
              <button type="button" onClick={() => setSelected(null)} className="p-2 hover:bg-gray-100 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 space-y-4 text-sm">
              <div className="space-y-2">
                <div className="flex justify-between gap-3">
                  <span className="text-gray-500">Order</span>
                  <Link href={`/orders/${detail.order?.id}`} className="font-medium text-primary-700 hover:underline">
                    {detail.order?.order_number}
                  </Link>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-gray-500">Consignment</span>
                  <span className="font-medium">{detail.consignment_id || '—'}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-gray-500">Cash to collect</span>
                  <span className="font-medium">
                    {money(detail.courier_cod_amount != null && detail.courier_cod_amount !== '' ? detail.courier_cod_amount : detail.cod_amount)}
                  </span>
                </div>
                {detail.cod_mismatch && (
                  <p className="text-amber-800 bg-amber-50 rounded-xl px-3 py-2">
                    The rider collects {money(detail.courier_cod_amount)}. This order was booked to collect{' '}
                    {money(detail.cod_amount)}. Steadfast changed the amount after booking.
                  </p>
                )}
                <div className="flex justify-between gap-3">
                  <span className="text-gray-500">Courier charge</span>
                  <span className="font-medium">{detail.delivery_charge != null ? money(detail.delivery_charge) : '—'}</span>
                </div>
                {detail.note && (
                  <p className="text-gray-600 bg-gray-50 rounded-xl px-3 py-2">
                    <span className="text-gray-500">Note: </span>{detail.note}
                  </p>
                )}
              </div>

              <div className="flex flex-wrap gap-2">
                <TrackingLinks shipment={detail} />
                <button
                  type="button"
                  onClick={() => handleRefresh(detail.id)}
                  disabled={refreshingIds.has(detail.id)}
                  className="btn btn-secondary text-sm"
                >
                  <RefreshCw className={`w-4 h-4 mr-1.5 ${refreshingIds.has(detail.id) ? 'animate-spin' : ''}`} />
                  Refresh
                </button>
                <button
                  type="button"
                  onClick={loadLiveTracking}
                  disabled={loadingLive}
                  className="btn btn-secondary text-sm"
                >
                  {loadingLive ? 'Loading…' : 'Load live tracking'}
                </button>
              </div>

              {detail.events?.length > 0 && (
                <div className="pt-3 border-t space-y-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Local timeline</p>
                  {detail.events.map((event) => (
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

              {liveSteps != null && (
                <div className="pt-3 border-t space-y-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Live Steadfast steps</p>
                  {!liveSteps.length ? (
                    <p className="text-gray-500">No live steps returned.</p>
                  ) : (
                    liveSteps.map((step, index) => {
                      const sentence = step.text || step.tracking_message || step.message || step.details || '';
                      const label = sentence || step.delivery_status || (typeof step.status === 'string' ? step.status : '') || `Step ${index + 1}`;
                      return (
                      <div key={index} className="flex gap-2">
                        <div className="w-1.5 h-1.5 mt-1.5 rounded-full bg-teal-500 shrink-0" />
                        <div>
                          <p className="font-medium text-gray-900">{label}</p>
                          <p className="text-xs text-gray-400">
                            {when(step.updated_at || step.created_at || step.time)}
                          </p>
                        </div>
                      </div>
                      );
                    })
                  )}
                </div>
              )}
            </div>
          </aside>
        </div>
      )}

      {importOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={() => setImportOpen(false)}>
          <div
            className="w-full max-w-lg bg-white rounded-2xl shadow-xl max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3 border-b px-5 py-4">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Import from Steadfast</h2>
                <p className="text-sm text-gray-500 mt-1">
                  Paste a consignment ID from the Steadfast portal and link it to a PickOrbeet order that has no shipment yet.
                </p>
              </div>
              <button type="button" onClick={() => setImportOpen(false)} className="p-2 hover:bg-gray-100 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 space-y-4 text-sm">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">
                  Consignment ID
                </label>
                <input
                  type="text"
                  value={importForm.consignment_id}
                  onChange={(e) => setImportForm((c) => ({ ...c, consignment_id: e.target.value }))}
                  placeholder="e.g. 315320720"
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">
                  Tracking code (optional)
                </label>
                <input
                  type="text"
                  value={importForm.tracking_code}
                  onChange={(e) => setImportForm((c) => ({ ...c, tracking_code: e.target.value }))}
                  placeholder="If you have it"
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>

              <button
                type="button"
                onClick={handlePreviewImport}
                disabled={previewing || (!importForm.consignment_id.trim() && !importForm.tracking_code.trim())}
                className="btn btn-secondary w-full"
              >
                {previewing ? 'Looking up…' : 'Preview on Steadfast'}
              </button>

              {importPreview && (
                <div className="rounded-xl border border-gray-200 bg-gray-50 px-3 py-3 space-y-1">
                  <p className="font-medium text-gray-900">
                    Status:{' '}
                    <span className={`badge border ${courierBadgeClass(importPreview.status_group)}`}>
                      {importPreview.status}
                    </span>
                  </p>
                  {importPreview.consignment_id && (
                    <p className="text-gray-600">Consignment {importPreview.consignment_id}</p>
                  )}
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">
                  Link to order
                </label>
                <input
                  type="search"
                  value={importForm.orderSearch}
                  onChange={(e) => setImportForm((c) => ({ ...c, orderSearch: e.target.value, order_id: '' }))}
                  placeholder="Search order number or phone…"
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 mb-2"
                />
                <div className="max-h-48 overflow-y-auto border border-gray-200 rounded-xl divide-y">
                  {!linkableOrders.length ? (
                    <p className="px-3 py-3 text-gray-500">No unshipped orders match.</p>
                  ) : (
                    linkableOrders.map((order) => (
                      <button
                        key={order.id}
                        type="button"
                        onClick={() => setImportForm((c) => ({ ...c, order_id: order.id }))}
                        className={`w-full text-left px-3 py-2.5 hover:bg-gray-50 ${
                          importForm.order_id === order.id ? 'bg-primary-50' : ''
                        }`}
                      >
                        <p className="font-medium text-gray-900">{order.order_number}</p>
                        <p className="text-xs text-gray-500">
                          {order.customer_name} · {order.order_status} · {money(order.total)}
                        </p>
                      </button>
                    ))
                  )}
                </div>
              </div>

              <button
                type="button"
                onClick={handleImport}
                disabled={importing || !importForm.order_id}
                className="btn btn-primary w-full"
              >
                {importing ? 'Importing…' : 'Import and link'}
              </button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}
