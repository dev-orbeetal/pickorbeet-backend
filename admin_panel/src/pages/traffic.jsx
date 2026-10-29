import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { useDispatch } from 'react-redux';
import {
  RefreshCw, Search, X, ArrowUpRight, ArrowDownRight,
} from 'lucide-react';
import {
  Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import AdminLayout from '@/components/layout/AdminLayout';
import { baseApi } from '@/store/api/baseApi';
import {
  useGetTrafficBreakdownQuery,
  useGetTrafficCustomerQuery,
  useGetTrafficCustomersQuery,
  useGetTrafficFunnelQuery,
  useGetTrafficLiveQuery,
  useGetTrafficOverviewQuery,
} from '@/store/api/trafficApi';
import {
  DEVICE_LABELS,
  PRESETS,
  countryName,
  dimensionLabel,
  formatChange,
  formatDuration,
  formatWhen,
  number,
  resolveRange,
  shortDate,
  timeAgo,
} from '@/lib/traffic';

const DEVICE_COLORS = {
  mobile: '#E86E00',
  desktop: '#202D70',
  tablet: '#3B82F6',
};

const DEFINITIONS = [
  ['Visitor', 'A distinct browser. Clearing site data starts a new visitor.'],
  ['Session', 'Ends after 30 minutes of inactivity.'],
  ['Page view', 'A page opened on the website, not an API call.'],
  ['Bounce', 'A session with a single page view.'],
  ['Active now', 'Distinct visitors in the last 5 minutes.'],
  ['Logged-in visitor', 'A visit tied to a customer account.'],
];

function queryRange(range) {
  if (!range) return { from: '', to: '' };
  return { from: range.from, to: range.to };
}

export default function TrafficPage() {
  const router = useRouter();
  const dispatch = useDispatch();
  const [mounted, setMounted] = useState(false);
  const [tab, setTab] = useState('live');
  const [search, setSearch] = useState('');
  const [debounced, setDebounced] = useState('');
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => setMounted(true), []);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const range = mounted && router.isReady ? resolveRange(router.query) : null;
  const params = queryRange(range);

  const overview = useGetTrafficOverviewQuery(params, {
    skip: !range,
    pollingInterval: 15000,
  });
  const pages = useGetTrafficBreakdownQuery({ ...params, dimension: 'page' }, { skip: !range });
  const countries = useGetTrafficBreakdownQuery({ ...params, dimension: 'country' }, { skip: !range });
  const regions = useGetTrafficBreakdownQuery({ ...params, dimension: 'region' }, { skip: !range });
  const cities = useGetTrafficBreakdownQuery({ ...params, dimension: 'city' }, { skip: !range });
  const devices = useGetTrafficBreakdownQuery({ ...params, dimension: 'device' }, { skip: !range });
  const browsers = useGetTrafficBreakdownQuery({ ...params, dimension: 'browser' }, { skip: !range });
  const systems = useGetTrafficBreakdownQuery({ ...params, dimension: 'os' }, { skip: !range });
  const sources = useGetTrafficBreakdownQuery({ ...params, dimension: 'source' }, { skip: !range });
  const campaigns = useGetTrafficBreakdownQuery({ ...params, dimension: 'utm_campaign' }, { skip: !range });
  const live = useGetTrafficLiveQuery(undefined, {
    skip: !range || tab !== 'live',
    pollingInterval: tab === 'live' ? 15000 : 0,
  });
  const customers = useGetTrafficCustomersQuery(
    { ...params, q: debounced },
    { skip: !range || tab !== 'customers' },
  );
  const funnel = useGetTrafficFunnelQuery(params, { skip: !range || tab !== 'path' });
  const timeline = useGetTrafficCustomerQuery(selectedId, { skip: !selectedId });

  const setPreset = (id) => {
    router.replace({ pathname: '/traffic', query: { range: id } }, undefined, { shallow: true });
  };

  const applyCustom = (event) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const from = String(data.get('from') || '');
    const to = String(data.get('to') || '');
    if (!/^\d{4}-\d{2}-\d{2}$/.test(from) || !/^\d{4}-\d{2}-\d{2}$/.test(to)) return;
    router.replace(
      { pathname: '/traffic', query: { range: 'custom', from, to } },
      undefined,
      { shallow: true },
    );
  };

  const refresh = () => dispatch(baseApi.util.invalidateTags(['Traffic']));
  const data = overview.data;
  const kpis = data?.kpis;
  const busy = overview.isFetching;

  return (
    <AdminLayout title="Traffic">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Traffic</h1>
          <p className="text-gray-600 mt-1">
            Who opened the shop, from where, and on which device.
            {range ? ` ${shortDate(range.from)} – ${shortDate(range.to)}, Asia/Dhaka.` : ''}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              onClick={() => setPreset(preset.id)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium ${
                range?.preset === preset.id
                  ? 'bg-primary-600 text-white'
                  : 'bg-white border border-[#E4E9F2] text-gray-700 hover:bg-gray-50'
              }`}
            >
              {preset.label}
            </button>
          ))}
          <button type="button" onClick={refresh} className="btn btn-secondary" disabled={busy}>
            <RefreshCw className={`w-4 h-4 mr-2 ${busy ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      <form onSubmit={applyCustom} className="flex flex-wrap items-end gap-3 mb-6">
        <label className="text-sm text-gray-600">
          From
          <input className="input mt-1" type="date" name="from" defaultValue={range?.from || ''} key={`from-${range?.from || ''}`} />
        </label>
        <label className="text-sm text-gray-600">
          To
          <input className="input mt-1" type="date" name="to" defaultValue={range?.to || ''} key={`to-${range?.to || ''}`} />
        </label>
        <button type="submit" className="btn btn-secondary">Apply</button>
      </form>

      <details className="mb-6 text-sm text-gray-600">
        <summary className="cursor-pointer font-medium text-gray-700">What these numbers mean</summary>
        <ul className="mt-3 grid md:grid-cols-2 gap-2">
          {DEFINITIONS.map(([term, text]) => (
            <li key={term}><span className="font-medium text-gray-800">{term}.</span> {text}</li>
          ))}
        </ul>
      </details>

      {!range || (overview.isLoading && !data) ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }, (_, index) => (
            <div key={index} className="h-28 bg-gray-200 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : null}

      {overview.isError && !data ? (
        <div className="card mb-6">
          <p className="font-medium text-gray-900">Traffic could not be loaded.</p>
          <button type="button" onClick={refresh} className="btn btn-primary mt-4">Try again</button>
        </div>
      ) : null}

      {kpis ? (
        <>
          {kpis.pageviews === 0 ? (
            <div className="card mb-6 bg-primary-50 border-primary-100">
              <p className="font-medium text-gray-900">No visits in this range yet</p>
              <p className="text-sm text-gray-600 mt-1">
                Tracking starts when shoppers open the website after this release. Earlier visits were not recorded.
                Country can stay Unknown when the hosting network does not send a region.
              </p>
            </div>
          ) : null}

          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
            <Kpi label="Visitors" value={number(kpis.visitors)} change={data.change.visitors} hint="Distinct browsers in this range." />
            <Kpi label="Page views" value={number(kpis.pageviews)} change={data.change.pageviews} hint="Pages opened on the website." />
            <Kpi label="Sessions" value={number(kpis.sessions)} change={data.change.sessions} hint="A session ends after 30 minutes idle." />
            <Kpi label="Active now" value={number(data.active_now)} pulse hint="Distinct visitors in the last 5 minutes." />
            <Kpi label="Bounce rate" value={`${kpis.bounce_rate}%`} change={data.change.bounce_rate} hint="Sessions with a single page view." />
            <Kpi label="Avg. duration" value={formatDuration(kpis.avg_duration_ms)} change={data.change.avg_duration_ms} hint="Time across the pages in a session." />
            <Kpi label="Logged-in visitors" value={number(kpis.logged_in_visitors)} change={data.change.logged_in_visitors} hint="Visits tied to a customer account." />
            <Kpi
              label="New visitors"
              value={number(kpis.new_visitors)}
              change={data.change.new_visitors}
              hint={`${number(kpis.returning_visitors)} returning in this range.`}
              detail={`${number(kpis.returning_visitors)} returning`}
            />
          </div>

          <div className="card mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Visitors and page views</h2>
              <p className="text-sm text-gray-500">{number(kpis.pages_per_session)} pages / session</p>
            </div>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.series}>
                  <CartesianGrid stroke="#E4E9F2" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={shortDate}
                    stroke="#94a3b8"
                    fontSize={12}
                    interval={data.series.length > 14 ? Math.ceil(data.series.length / 8) : 0}
                  />
                  <YAxis stroke="#94a3b8" fontSize={12} allowDecimals={false} width={36} />
                  <Tooltip
                    labelFormatter={shortDate}
                    contentStyle={{ borderRadius: 12, borderColor: '#E4E9F2' }}
                  />
                  <Area type="monotone" dataKey="visitors" name="Visitors" stroke="#E86E00" fill="#FF861F" fillOpacity={0.18} strokeWidth={2} />
                  <Area type="monotone" dataKey="pageviews" name="Page views" stroke="#202D70" fill="#202D70" fillOpacity={0.12} strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="grid lg:grid-cols-2 gap-6 mb-6">
            <RankCard title="Top pages" dimension="page" query={pages} />
            <div className="card">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Regions</h2>
              <div className="space-y-5">
                <RankList title="Countries" dimension="country" rows={countries.data?.results} loading={countries.isLoading} />
                <RankList title="Divisions" dimension="region" rows={regions.data?.results} loading={regions.isLoading} />
                <RankList title="Cities" dimension="city" rows={cities.data?.results} loading={cities.isLoading} />
              </div>
            </div>
          </div>

          <div className="grid lg:grid-cols-3 gap-6 mb-6">
            <DeviceCard query={devices} />
            <RankCard title="Browsers" dimension="browser" query={browsers} />
            <RankCard title="Operating systems" dimension="os" query={systems} />
          </div>

          <div className="grid lg:grid-cols-2 gap-6 mb-6">
            <RankCard title="Sources" dimension="source" query={sources} />
            <RankCard title="Campaigns" dimension="utm_campaign" query={campaigns} empty="No campaign tags in this range." />
          </div>

          <div className="card">
            <div className="flex gap-2 mb-5 border-b border-[#E4E9F2]">
              {[
                ['live', 'Live'],
                ['customers', 'Customers'],
                ['path', 'Shop path'],
              ].map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setTab(id)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
                    tab === id ? 'border-primary-600 text-primary-700' : 'border-transparent text-gray-500'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {tab === 'live' ? <LiveFeed query={live} onSelect={setSelectedId} /> : null}
            {tab === 'customers' ? (
              <Customers
                query={customers}
                search={search}
                onSearch={setSearch}
                onSelect={setSelectedId}
              />
            ) : null}
            {tab === 'path' ? <ShopPath query={funnel} /> : null}
          </div>
        </>
      ) : null}

      {selectedId ? (
        <CustomerDrawer
          timeline={timeline}
          onClose={() => setSelectedId(null)}
        />
      ) : null}
    </AdminLayout>
  );
}

function Kpi({ label, value, change, hint, pulse, detail }) {
  const text = formatChange(change);
  const positive = typeof change === 'number' && change > 0;
  const negative = typeof change === 'number' && change < 0;
  return (
    <div className="stat-card" title={hint}>
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
      {pulse ? (
        <p className="mt-3 text-xs text-gray-500 flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
          </span>
          Last 5 minutes
        </p>
      ) : (
        <p className="mt-3 text-sm flex items-center">
          {positive ? <ArrowUpRight className="w-4 h-4 text-green-500 mr-1" /> : null}
          {negative ? <ArrowDownRight className="w-4 h-4 text-red-500 mr-1" /> : null}
          <span className={positive ? 'text-green-600' : negative ? 'text-red-600' : 'text-gray-400'}>
            {text || '—'}
          </span>
          <span className="text-gray-500 ml-1">{detail || 'vs previous'}</span>
        </p>
      )}
    </div>
  );
}

function RankCard({ title, dimension, query, empty }) {
  return (
    <div className="card">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">{title}</h2>
      <RankList dimension={dimension} rows={query.data?.results} empty={empty} loading={query.isLoading} error={query.isError} />
    </div>
  );
}

function RankList({ title, dimension, rows, empty, loading, error }) {
  const list = rows || [];
  const top = list[0]?.pageviews || 1;
  return (
    <div>
      {title ? <h3 className="text-sm font-medium text-gray-700 mb-2">{title}</h3> : null}
      {loading ? <div className="h-24 bg-gray-100 rounded-lg animate-pulse" /> : null}
      {error ? <p className="text-sm text-red-600">Could not load this list.</p> : null}
      {!loading && !error && list.length === 0 ? (
        <p className="text-sm text-gray-500">{empty || 'No data in this range.'}</p>
      ) : null}
      <ul className="space-y-3">
        {list.map((row) => (
          <li key={`${dimension}-${row.label}`}>
            <div className="flex justify-between gap-3 text-sm mb-1">
              <span className="truncate text-gray-800">{dimensionLabel(dimension, row.label)}</span>
              <span className="shrink-0 text-gray-500">
                {number(row.pageviews)} views · {number(row.visitors)} visitors
              </span>
            </div>
            <div className="h-1.5 bg-gray-100 rounded-full">
              <div
                className="h-full bg-primary-500 rounded-full"
                style={{ width: `${Math.max(4, (row.pageviews / top) * 100)}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function DeviceCard({ query }) {
  const rows = (query.data?.results || []).filter((row) => row.label && row.label !== 'Unknown');
  const chart = rows.map((row) => ({
    name: DEVICE_LABELS[row.label] || row.label,
    key: row.label,
    value: row.visitors,
  }));
  return (
    <div className="card">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Devices</h2>
      {query.isLoading ? <div className="h-48 bg-gray-100 rounded-lg animate-pulse" /> : null}
      {!query.isLoading && chart.length === 0 ? <p className="text-sm text-gray-500">No data in this range.</p> : null}
      {chart.length > 0 ? (
        <div className="h-52">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={chart} dataKey="value" nameKey="name" innerRadius={48} outerRadius={72} paddingAngle={2}>
                {chart.map((entry) => (
                  <Cell key={entry.key} fill={DEVICE_COLORS[entry.key] || '#94a3b8'} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ borderRadius: 12, borderColor: '#E4E9F2' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      ) : null}
      <ul className="mt-2 space-y-1 text-sm text-gray-600">
        {chart.map((entry) => (
          <li key={entry.key} className="flex justify-between">
            <span className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: DEVICE_COLORS[entry.key] || '#94a3b8' }} />
              {entry.name}
            </span>
            <span>{number(entry.value)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function LiveFeed({ query, onSelect }) {
  const rows = query.data?.results || [];
  if (query.isLoading) return <div className="h-40 bg-gray-100 rounded-lg animate-pulse" />;
  if (rows.length === 0) return <p className="text-sm text-gray-500">No visits yet.</p>;
  return (
    <ul className="divide-y divide-[#E4E9F2]">
      {rows.map((row, index) => (
        <li key={`${row.occurred_at}-${row.path}-${index}`} className="py-3 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
          <span className="text-xs text-gray-500 w-20 shrink-0">{timeAgo(row.occurred_at)}</span>
          <span className="font-medium text-gray-900 truncate flex-1">{row.path}</span>
          <span className="text-sm text-gray-500">{place(row)}</span>
          <span className="text-sm text-gray-500">{DEVICE_LABELS[row.device] || row.device}</span>
          {row.user ? (
            <button type="button" onClick={() => onSelect(row.user.id)} className="text-sm text-primary-700 hover:underline text-left">
              {row.user.name}
            </button>
          ) : (
            <span className="text-sm text-gray-400">Guest</span>
          )}
        </li>
      ))}
    </ul>
  );
}

function Customers({ query, search, onSearch, onSelect }) {
  const rows = query.data?.results || [];
  return (
    <div>
      <div className="relative mb-4 max-w-sm">
        <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
        <input
          className="input pl-9"
          value={search}
          onChange={(event) => onSearch(event.target.value)}
          placeholder="Name or email"
        />
      </div>
      {query.isLoading ? <div className="h-40 bg-gray-100 rounded-lg animate-pulse" /> : null}
      {!query.isLoading && rows.length === 0 ? (
        <p className="text-sm text-gray-500">No signed-in customers in this range.</p>
      ) : null}
      {rows.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b">
                {['Customer', 'Last seen', 'Views', 'Last page', 'Place', 'Device'].map((heading) => (
                  <th key={heading} className="text-left py-3 px-2 table-header">{heading}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.user_id}
                  className="border-b last:border-0 hover:bg-gray-50 cursor-pointer"
                  onClick={() => onSelect(row.user_id)}
                >
                  <td className="py-3 px-2">
                    <p className="font-medium text-gray-900">{row.name}</p>
                    <p className="text-xs text-gray-500">{row.email}</p>
                  </td>
                  <td className="py-3 px-2 text-sm text-gray-600">{formatWhen(row.last_seen)}</td>
                  <td className="py-3 px-2 text-sm">{number(row.pageviews)}</td>
                  <td className="py-3 px-2 text-sm text-gray-600">{row.last_path}</td>
                  <td className="py-3 px-2 text-sm text-gray-600">{place(row)}</td>
                  <td className="py-3 px-2 text-sm text-gray-600">{DEVICE_LABELS[row.device] || row.device || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function ShopPath({ query }) {
  const steps = query.data?.steps || [];
  const peak = Math.max(...steps.map((step) => step.pageviews), 1);
  if (query.isLoading) return <div className="h-40 bg-gray-100 rounded-lg animate-pulse" />;
  return (
    <div>
      <p className="text-sm text-gray-500 mb-4">
        Product, cart, and checkout are page views. Orders are online orders placed in this range, excluding cancelled and in-shop sales.
      </p>
      <ol className="space-y-4">
        {steps.map((step, index) => {
          const previous = index === 0 ? null : steps[index - 1].pageviews;
          const continued = previous ? Math.round((step.pageviews / previous) * 100) : null;
          return (
            <li key={step.key}>
              <div className="flex justify-between text-sm mb-1">
                <span className="font-medium text-gray-900">{step.label}</span>
                <span className="text-gray-500">
                  {number(step.pageviews)}
                  {step.key !== 'orders' ? ` · ${number(step.visitors)} visitors` : ''}
                  {continued !== null ? ` · ${continued}% of previous` : ''}
                </span>
              </div>
              <div className="h-3 bg-gray-100 rounded-full">
                <div
                  className="h-full rounded-full bg-sidebar-bg"
                  style={{ width: `${Math.max(step.pageviews ? 4 : 0, (step.pageviews / peak) * 100)}%` }}
                />
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function CustomerDrawer({ timeline, onClose }) {
  useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const user = timeline.data?.user;
  const rows = timeline.data?.results || [];

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button type="button" className="absolute inset-0 bg-black/30" aria-label="Close" onClick={onClose} />
      <aside className="relative w-full max-w-md h-full bg-white shadow-xl overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-[#E4E9F2] px-5 py-4 flex items-start justify-between">
          <div>
            <p className="text-lg font-semibold text-gray-900">{user?.name || 'Customer'}</p>
            <p className="text-sm text-gray-500">{user?.email}</p>
          </div>
          <button type="button" onClick={onClose} className="p-2 text-gray-500 hover:text-gray-800" aria-label="Close">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-5">
          {timeline.isLoading ? <div className="h-40 bg-gray-100 rounded-lg animate-pulse" /> : null}
          {!timeline.isLoading && rows.length === 0 ? (
            <p className="text-sm text-gray-500">No page history for this customer.</p>
          ) : null}
          <ol className="space-y-4">
            {rows.map((row, index) => (
              <li key={`${row.occurred_at}-${index}`} className="border-l-2 border-primary-200 pl-4">
                <p className="text-xs text-gray-500">{formatWhen(row.occurred_at)}</p>
                <p className="font-medium text-gray-900">{row.path}</p>
                <p className="text-sm text-gray-500">
                  {[place(row), DEVICE_LABELS[row.device] || row.device, row.browser, formatDuration(row.duration_ms)]
                    .filter((part) => part && part !== '0s')
                    .join(' · ')}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </aside>
    </div>
  );
}

function place(row) {
  const country = countryName(row.country);
  if (row.city && country !== 'Unknown') return `${row.city}, ${country}`;
  if (row.city) return row.city;
  if (row.region && country !== 'Unknown') return `${dimensionLabel('region', row.region)}, ${country}`;
  return country;
}
