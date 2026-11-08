import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useDispatch, useSelector } from 'react-redux';
import {
  Activity, ArrowDownRight, ArrowUpRight, Calendar, ChevronDown, Clock, Download,
  Eye, Layers, Monitor, Percent, Radio, RefreshCw, Route, Search, Smartphone,
  Tablet, UserCheck, UserPlus, Users, X,
} from 'lucide-react';
import { jsPDF } from 'jspdf';
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
  SOURCE_LABELS,
  countryName,
  dimensionLabel,
  formatChange,
  formatDuration,
  formatWhen,
  mediumDate,
  number,
  previousCaption,
  resolveRange,
  shortDate,
  timeAgo,
} from '@/lib/traffic';

const DEVICE_COLORS = {
  desktop: '#2F5BFF',
  mobile: '#FF851B',
  tablet: '#8B9CF7',
};

const DEVICE_ICONS = {
  desktop: Monitor,
  mobile: Smartphone,
  tablet: Tablet,
};

const DEFINITIONS = [
  ['Visitor', 'A distinct browser. Clearing site data starts a new visitor.'],
  ['Session', 'Ends after 30 minutes of inactivity.'],
  ['Page view', 'A page opened on the website, not an API call.'],
  ['Bounce', 'A session with a single page view.'],
  ['Active now', 'Distinct visitors in the last 5 minutes.'],
  ['Logged-in visitor', 'A visit tied to a customer account.'],
];

const RANGE_LABELS = {
  today: 'Today',
  '7d': '7 Days',
  '30d': '30 Days',
  '90d': '90 Days',
};

const BD_OUTLINE = [
  [88.05, 26.63], [90.2, 26.5], [91.9, 26.2], [92.4, 25.1], [92.1, 23.8],
  [92.3, 22.2], [91.8, 21.2], [90.8, 22.2], [90.5, 21.6], [89.1, 21.7],
  [88.2, 22.5], [88.0, 24.2], [88.5, 25.2], [88.0, 26.1],
];

function queryRange(range) {
  if (!range) return { from: '', to: '' };
  return { from: range.from, to: range.to };
}

function scrollToId(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function seriesValues(series, key) {
  return (series || []).map((row) => Number(row[key]) || 0);
}

function toneOf(change, invert) {
  if (typeof change !== 'number' || change === 0) return 'flat';
  const rising = change > 0;
  return (invert ? !rising : rising) ? 'up' : 'down';
}

function flagEmoji(code) {
  if (!code || code === 'Unknown' || code.length !== 2) return '';
  const chars = [...code.toUpperCase()];
  if (chars.some((char) => char < 'A' || char > 'Z')) return '';
  return String.fromCodePoint(...chars.map((char) => 127397 + char.charCodeAt(0)));
}

function share(part, whole) {
  if (!whole) return '0%';
  return `${((part / whole) * 100).toFixed(1)}%`;
}

function hourTick(value) {
  const [date, time] = String(value || '').split('T');
  if (!time) return shortDate(value);
  return `${shortDate(date)} ${time.slice(0, 5)}`;
}

function csvCell(value) {
  const text = String(value ?? '');
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function downloadCsv(filename, rows) {
  const body = rows.map((row) => row.map(csvCell).join(',')).join('\n');
  const blob = new Blob([body], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function downloadPdf(range, data, pages, countries) {
  const doc = new jsPDF();
  const kpis = data.kpis;
  let y = 18;
  doc.setFontSize(16);
  doc.text('PickOrbeet traffic', 14, y);
  y += 8;
  doc.setFontSize(10);
  doc.setTextColor(80);
  doc.text(`${mediumDate(range.from)} – ${mediumDate(range.to)}, Asia/Dhaka`, 14, y);
  y += 10;
  doc.setTextColor(20);
  const lines = [
    ['Visitors', number(kpis.visitors)],
    ['Page views', number(kpis.pageviews)],
    ['Sessions', number(kpis.sessions)],
    ['Bounce rate', `${kpis.bounce_rate}%`],
    ['Avg. duration', formatDuration(kpis.avg_duration_ms)],
    ['Logged-in visitors', number(kpis.logged_in_visitors)],
    ['New visitors', number(kpis.new_visitors)],
    ['Active now', number(data.active_now)],
  ];
  lines.forEach(([label, value]) => {
    doc.text(label, 14, y);
    doc.text(String(value), 80, y);
    y += 6;
  });
  y += 4;
  doc.setFontSize(12);
  doc.text('Top pages', 14, y);
  y += 7;
  doc.setFontSize(10);
  (pages || []).slice(0, 8).forEach((row) => {
    doc.text(`${String(row.label).slice(0, 64)}  ·  ${number(row.pageviews)} views`, 14, y);
    y += 6;
  });
  y += 2;
  doc.setFontSize(12);
  doc.text('Countries', 14, y);
  y += 7;
  doc.setFontSize(10);
  (countries || []).slice(0, 8).forEach((row) => {
    doc.text(`${dimensionLabel('country', row.label)}  ·  ${number(row.visitors)} visitors`, 14, y);
    y += 6;
  });
  doc.save(`traffic-${range.from}-${range.to}.pdf`);
}

export default function TrafficPage() {
  const router = useRouter();
  const dispatch = useDispatch();
  const role = useSelector((state) => state.auth.user?.role);
  const canIdentify = role === 'seller' || role === 'super_admin';
  const [mounted, setMounted] = useState(false);
  const [tab, setTab] = useState('live');
  const [search, setSearch] = useState('');
  const [debounced, setDebounced] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [dateOpen, setDateOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [grain, setGrain] = useState('daily');
  const [focus, setFocus] = useState('pageviews');
  const [regionTab, setRegionTab] = useState('country');
  const [showAllPages, setShowAllPages] = useState(false);
  const [deviceFilter, setDeviceFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const dateRef = useRef(null);
  const exportRef = useRef(null);

  useEffect(() => setMounted(true), []);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    const close = (event) => {
      if (dateRef.current && !dateRef.current.contains(event.target)) setDateOpen(false);
      if (exportRef.current && !exportRef.current.contains(event.target)) setExportOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const range = mounted && router.isReady ? resolveRange(router.query) : null;
  const params = queryRange(range);
  const hourlyAvailable = Boolean(range && (new Date(`${range.to}T00:00:00Z`) - new Date(`${range.from}T00:00:00Z`)) / 86400000 <= 6);

  const overview = useGetTrafficOverviewQuery(params, { skip: !range, pollingInterval: 15000 });
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
    { ...params, q: canIdentify ? debounced : '' },
    { skip: !range || tab !== 'customers' },
  );
  const funnel = useGetTrafficFunnelQuery(params, { skip: !range || tab !== 'path' });
  const timeline = useGetTrafficCustomerQuery(selectedId, { skip: !selectedId || !canIdentify });

  useEffect(() => {
    if (!hourlyAvailable && grain === 'hourly') setGrain('daily');
  }, [hourlyAvailable, grain]);

  const setPreset = (id) => {
    router.replace({ pathname: '/traffic', query: { range: id } }, undefined, { shallow: true });
  };

  const applyCustom = (event) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const from = String(data.get('from') || '');
    const to = String(data.get('to') || '');
    if (!/^\d{4}-\d{2}-\d{2}$/.test(from) || !/^\d{4}-\d{2}-\d{2}$/.test(to)) return;
    setDateOpen(false);
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
  const compare = previousCaption(range?.preset);
  const chartPoints = grain === 'hourly' && data?.hourly ? data.hourly : (data?.series || []);
  const chartKey = grain === 'hourly' ? 'hour' : 'date';

  const openSection = (id, section) => {
    setFocus(id);
    if (section === 'live' || section === 'customers' || section === 'path') {
      setTab(section);
      scrollToId('activity');
      return;
    }
    scrollToId(section);
  };

  const exportRows = () => {
    if (!kpis || !range) return;
    const rows = [
      ['from', range.from],
      ['to', range.to],
      ['visitors', kpis.visitors],
      ['pageviews', kpis.pageviews],
      ['sessions', kpis.sessions],
      ['bounce_rate', kpis.bounce_rate],
      ['avg_duration_ms', kpis.avg_duration_ms],
      ['logged_in_visitors', kpis.logged_in_visitors],
      ['new_visitors', kpis.new_visitors],
      ['active_now', data.active_now],
      [],
      ['date', 'visitors', 'pageviews', 'sessions'],
      ...(data.series || []).map((row) => [row.date, row.visitors, row.pageviews, row.sessions]),
      [],
      ['page', 'views', 'visitors'],
      ...(pages.data?.results || []).map((row) => [row.label, row.pageviews, row.visitors]),
    ];
    downloadCsv(`traffic-${range.from}-${range.to}.csv`, rows);
    setExportOpen(false);
  };

  const cards = kpis ? [
    {
      id: 'visitors', label: 'Visitors', value: number(kpis.visitors), change: data.change.visitors,
      spark: seriesValues(data.series, 'visitors'), icon: Users, bubble: 'bg-blue-50 text-blue-600',
      detail: `${number(kpis.visitors)} distinct browsers. The previous period had ${number(data.previous.visitors)}.`,
      section: 'trend',
    },
    {
      id: 'pageviews', label: 'Page views', value: number(kpis.pageviews), change: data.change.pageviews,
      spark: seriesValues(data.series, 'pageviews'), icon: Eye, bubble: 'bg-violet-50 text-violet-600',
      detail: `${number(kpis.pageviews)} pages opened. The previous period had ${number(data.previous.pageviews)}.`,
      section: 'trend',
    },
    {
      id: 'sessions', label: 'Sessions', value: number(kpis.sessions), change: data.change.sessions,
      spark: seriesValues(data.series, 'sessions'), icon: Layers, bubble: 'bg-emerald-50 text-emerald-600',
      detail: `${number(kpis.sessions)} sessions. A session ends after 30 minutes idle. The previous period had ${number(data.previous.sessions)}.`,
      section: 'trend',
    },
    {
      id: 'duration', label: 'Avg. duration', value: formatDuration(kpis.avg_duration_ms), change: data.change.avg_duration_ms,
      spark: [data.previous.avg_duration_ms, kpis.avg_duration_ms], icon: Clock, bubble: 'bg-orange-50 text-orange-600',
      detail: `Average time on the shop is ${formatDuration(kpis.avg_duration_ms)}. The previous period was ${formatDuration(data.previous.avg_duration_ms)}.`,
      section: 'path',
    },
    {
      id: 'bounce', label: 'Bounce rate', value: `${kpis.bounce_rate}%`, change: data.change.bounce_rate, invert: true,
      spark: [data.previous.bounce_rate, kpis.bounce_rate], icon: Percent, bubble: 'bg-red-50 text-red-500',
      detail: `${kpis.bounce_rate}% of sessions opened a single page. The previous period was ${data.previous.bounce_rate}%.`,
      section: 'path',
    },
    {
      id: 'logged_in', label: 'Logged-in visitors', value: number(kpis.logged_in_visitors), change: data.change.logged_in_visitors,
      spark: [data.previous.logged_in_visitors, kpis.logged_in_visitors], icon: UserCheck, bubble: 'bg-sky-50 text-sky-600',
      detail: `${number(kpis.logged_in_visitors)} visits are tied to a customer account.`,
      section: 'customers',
    },
    {
      id: 'new', label: 'New visitors', value: number(kpis.new_visitors), change: data.change.new_visitors,
      spark: [data.previous.new_visitors, kpis.new_visitors], icon: UserPlus, bubble: 'bg-emerald-50 text-emerald-600',
      detail: `${number(kpis.new_visitors)} new and ${number(kpis.returning_visitors)} returning in this range.`,
      section: 'trend',
    },
    {
      id: 'active', label: 'Active now', value: number(data.active_now), live: true,
      icon: Activity, bubble: 'bg-emerald-50 text-emerald-600',
      detail: `${number(data.active_now)} distinct visitors in the last 5 minutes.`,
      section: 'live',
    },
  ] : [];
  const selectedCard = cards.find((card) => card.id === focus);

  return (
    <AdminLayout title="Traffic">
      <div className="mb-5 flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <p className="text-sm text-[#697386]">
            <Link href="/dashboard" className="hover:text-[#172033]">Home</Link>
            <span className="mx-1.5">/</span>
            <span className="text-[#172033]">Traffic</span>
          </p>
          <h2 className="mt-1 text-2xl font-semibold tracking-tight text-[#172033]">Traffic Analytics</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-[#697386]">
            See who opened your shop, from where, on which device, and which pages they visited.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative" ref={dateRef}>
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded-xl border border-[#E3E8F2] bg-white px-3 py-2 text-sm font-medium text-[#172033] shadow-sm"
              onClick={() => setDateOpen((open) => !open)}
              aria-expanded={dateOpen}
            >
              <Calendar className="h-4 w-4 text-[#697386]" />
              {range ? `${mediumDate(range.from)} – ${mediumDate(range.to)}` : 'Date range'}
              <ChevronDown className="h-4 w-4 text-[#697386]" />
            </button>
            {dateOpen ? (
              <form onSubmit={applyCustom} className="absolute right-0 z-20 mt-2 w-72 rounded-2xl border border-[#E3E8F2] bg-white p-4 shadow-lg">
                <label className="block text-xs font-medium text-[#697386]">
                  From
                  <input className="input mt-1" type="date" name="from" defaultValue={range?.from || ''} key={`from-${range?.from || ''}`} />
                </label>
                <label className="mt-3 block text-xs font-medium text-[#697386]">
                  To
                  <input className="input mt-1" type="date" name="to" defaultValue={range?.to || ''} key={`to-${range?.to || ''}`} />
                </label>
                <button type="submit" className="btn btn-primary mt-4 w-full">Apply</button>
              </form>
            ) : null}
          </div>
          {PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              onClick={() => setPreset(preset.id)}
              className={`rounded-xl px-3 py-2 text-sm font-medium ${
                range?.preset === preset.id
                  ? 'bg-[#202F70] text-white'
                  : 'border border-[#E3E8F2] bg-white text-[#172033] hover:bg-[#F8FAFC]'
              }`}
            >
              {RANGE_LABELS[preset.id]}
            </button>
          ))}
          <button type="button" onClick={refresh} className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[#E3E8F2] bg-white text-[#172033]" aria-label="Refresh" disabled={busy}>
            <RefreshCw className={`h-4 w-4 ${busy ? 'animate-spin' : ''}`} />
          </button>
          <div className="relative" ref={exportRef}>
            <button
              type="button"
              className="inline-flex h-10 items-center gap-2 rounded-xl border border-[#E3E8F2] bg-white px-3 text-sm font-medium text-[#172033] disabled:opacity-50"
              onClick={() => setExportOpen((open) => !open)}
              disabled={!kpis}
              aria-expanded={exportOpen}
            >
              <Download className="h-4 w-4" />
              Export
            </button>
            {exportOpen && kpis && range ? (
              <div className="absolute right-0 z-20 mt-2 w-40 overflow-hidden rounded-xl border border-[#E3E8F2] bg-white shadow-lg">
                <button type="button" className="block w-full px-3 py-2 text-left text-sm hover:bg-[#F8FAFC]" onClick={exportRows}>CSV</button>
                <button
                  type="button"
                  className="block w-full px-3 py-2 text-left text-sm hover:bg-[#F8FAFC]"
                  onClick={() => {
                    downloadPdf(range, data, pages.data?.results, countries.data?.results);
                    setExportOpen(false);
                  }}
                >
                  PDF
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <details className="mb-5 text-sm text-[#697386]">
        <summary className="cursor-pointer font-medium text-[#172033]">What these numbers mean</summary>
        <ul className="mt-3 grid gap-2 md:grid-cols-2">
          {DEFINITIONS.map(([term, text]) => (
            <li key={term}><span className="font-medium text-[#172033]">{term}.</span> {text}</li>
          ))}
        </ul>
      </details>

      {!range || (overview.isLoading && !data) ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 8 }, (_, index) => (
            <div key={index} className="h-36 animate-pulse rounded-2xl bg-white" />
          ))}
        </div>
      ) : null}

      {overview.isError && !data ? (
        <div className="rounded-2xl border border-[#E3E8F2] bg-white p-6">
          <p className="font-medium text-[#172033]">Traffic could not be loaded.</p>
          <button type="button" onClick={refresh} className="btn btn-primary mt-4">Try again</button>
        </div>
      ) : null}

      {kpis ? (
        <div className="space-y-4">
          {kpis.pageviews === 0 ? (
            <div className="rounded-2xl border border-orange-100 bg-orange-50 px-5 py-4">
              <p className="font-medium text-[#172033]">No visits in this range yet</p>
              <p className="mt-1 text-sm text-[#697386]">
                Visits appear after a shopper opens the website. A country stays Unknown when the network does not send a place.
              </p>
            </div>
          ) : null}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {cards.map((card) => (
              <KpiCard
                key={card.id}
                card={card}
                compare={compare}
                active={focus === card.id}
                onClick={() => openSection(card.id, card.section)}
              />
            ))}
          </div>

          {selectedCard ? (
            <p className="px-1 text-sm leading-6 text-[#697386]">{selectedCard.detail}</p>
          ) : null}

          <div id="trend" className="grid scroll-mt-6 grid-cols-1 gap-4 xl:grid-cols-3">
            <section className="rounded-2xl border border-[#E3E8F2] bg-white p-5 shadow-sm xl:col-span-2">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-base font-semibold text-[#172033]">Visitors & page views</h3>
                  <div className="mt-2 flex flex-wrap items-center gap-4 text-sm text-[#697386]">
                    <LegendDot color="#2F5BFF" label={`Page views (${number(kpis.pageviews)})`} />
                    <LegendDot color="#FF851B" label={`Visitors (${number(kpis.visitors)})`} />
                    {focus === 'sessions' ? <LegendDot color="#16A34A" label={`Sessions (${number(kpis.sessions)})`} /> : null}
                  </div>
                </div>
                <div className="inline-flex rounded-xl bg-[#F3F5F8] p-1">
                  <GrainButton active={grain === 'daily'} onClick={() => setGrain('daily')}>Daily</GrainButton>
                  <GrainButton
                    active={grain === 'hourly'}
                    disabled={!hourlyAvailable || !data.hourly}
                    title={hourlyAvailable ? 'Hours in this range' : 'Hourly is available for 7 days or fewer'}
                    onClick={() => setGrain('hourly')}
                  >
                    Hourly
                  </GrainButton>
                </div>
              </div>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartPoints} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid stroke="#E3E8F2" vertical={false} />
                    <XAxis
                      dataKey={chartKey}
                      tickFormatter={grain === 'hourly' ? hourTick : shortDate}
                      stroke="#97A0B0"
                      fontSize={12}
                      tickLine={false}
                      axisLine={false}
                      interval={chartPoints.length > 14 ? Math.ceil(chartPoints.length / 7) : 0}
                      minTickGap={24}
                    />
                    <YAxis stroke="#97A0B0" fontSize={12} allowDecimals={false} width={32} tickLine={false} axisLine={false} />
                    <Tooltip content={<ChartTip hourly={grain === 'hourly'} />} />
                    <Area type="monotone" dataKey="pageviews" name="Page views" stroke="#2F5BFF" fill="#2F5BFF" fillOpacity={focus === 'visitors' ? 0.05 : 0.12} strokeWidth={focus === 'pageviews' ? 2.75 : 2} />
                    <Area type="monotone" dataKey="visitors" name="Visitors" stroke="#FF851B" fill="#FF851B" fillOpacity={focus === 'pageviews' ? 0.05 : 0.16} strokeWidth={focus === 'visitors' ? 2.75 : 2} />
                    {focus === 'sessions' ? (
                      <Area type="monotone" dataKey="sessions" name="Sessions" stroke="#16A34A" fill="#16A34A" fillOpacity={0.08} strokeWidth={2.5} />
                    ) : null}
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </section>
            <DeviceCard query={devices} />
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <PagesTable
              rows={pages.data?.results || []}
              loading={pages.isLoading}
              error={pages.isError}
              expanded={showAllPages}
              onToggle={() => setShowAllPages((value) => !value)}
            />
            <RegionsCard
              tab={regionTab}
              onTab={setRegionTab}
              countries={countries}
              regions={regions}
              cities={cities}
            />
          </div>

          <details className="rounded-2xl border border-[#E3E8F2] bg-white p-5 shadow-sm">
            <summary className="cursor-pointer text-base font-semibold text-[#172033]">Browsers, systems, sources, and campaigns</summary>
            <div className="mt-5 grid gap-6 lg:grid-cols-2">
              <MiniTable title="Browsers" dimension="browser" query={browsers} />
              <MiniTable title="Operating systems" dimension="os" query={systems} />
              <MiniTable title="Sources" dimension="source" query={sources} />
              <MiniTable title="Campaigns" dimension="utm_campaign" query={campaigns} empty="No campaign tags in this range." />
            </div>
          </details>

          <section id="activity" className="scroll-mt-6 rounded-2xl border border-[#E3E8F2] bg-white p-5 shadow-sm">
            <div className="mb-4 flex flex-wrap gap-2 border-b border-[#E3E8F2]">
              {[
                ['live', 'Live activity', Radio],
                ['customers', 'Customers', Users],
                ['path', 'Shop path', Route],
              ].map(([id, label, Icon]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setTab(id)}
                  className={`inline-flex items-center gap-2 border-b-2 px-3 py-3 text-sm font-medium ${
                    tab === id ? 'border-[#FF851B] text-[#172033]' : 'border-transparent text-[#697386]'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </button>
              ))}
            </div>

            {tab === 'live' ? (
              <LiveFeed
                query={live}
                onSelect={canIdentify ? setSelectedId : null}
                canIdentify={canIdentify}
                device={deviceFilter}
                source={sourceFilter}
                onDevice={setDeviceFilter}
                onSource={setSourceFilter}
              />
            ) : null}
            {tab === 'customers' ? (
              <Customers
                query={customers}
                search={search}
                onSearch={canIdentify ? setSearch : null}
                onSelect={canIdentify ? setSelectedId : null}
                canIdentify={canIdentify}
              />
            ) : null}
            {tab === 'path' ? <ShopPath query={funnel} /> : null}
          </section>
        </div>
      ) : null}

      {selectedId && canIdentify ? (
        <CustomerDrawer timeline={timeline} onClose={() => setSelectedId(null)} />
      ) : null}
    </AdminLayout>
  );
}

function GrainButton({ active, disabled, onClick, title, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`rounded-lg px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-40 ${
        active ? 'bg-[#202F70] text-white' : 'text-[#697386]'
      }`}
    >
      {children}
    </button>
  );
}

function LegendDot({ color, label }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="h-2 w-2 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}

function ChartTip({ active, payload, label, hourly }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-[#E3E8F2] bg-white px-3 py-2 text-xs shadow-lg">
      <p className="font-medium text-[#172033]">{hourly ? hourTick(label) : shortDate(label)}</p>
      {payload.map((item) => (
        <p key={item.dataKey} className="mt-1" style={{ color: item.color }}>
          {item.name}: {number(item.value)}
        </p>
      ))}
    </div>
  );
}

function KpiCard({ card, compare, active, onClick }) {
  const Icon = card.icon;
  const tone = toneOf(card.change, card.invert);
  const sparkColor = tone === 'up' ? '#16A34A' : tone === 'down' ? '#EF4444' : '#94A3B8';
  const changeClass = tone === 'up' ? 'text-emerald-600' : tone === 'down' ? 'text-red-500' : 'text-[#697386]';
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-2xl border bg-white p-5 text-left shadow-sm transition ${
        active ? 'border-[#FF851B] ring-2 ring-orange-100' : 'border-[#E3E8F2] hover:border-[#D5DCEA]'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <span className="inline-flex items-center gap-2.5 text-sm font-medium text-[#697386]">
          <span className={`flex h-9 w-9 items-center justify-center rounded-full ${card.bubble}`}>
            <Icon className="h-4 w-4" />
          </span>
          {card.label}
        </span>
        {card.spark ? <Sparkline values={card.spark} color={card.live ? '#16A34A' : sparkColor} /> : null}
      </div>
      <p className="mt-4 text-[1.75rem] font-semibold leading-none tracking-tight text-[#172033]">{card.value}</p>
      {card.live ? (
        <p className="mt-3 inline-flex items-center gap-2 text-xs font-medium text-emerald-600">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
          </span>
          Live · last 5 minutes
        </p>
      ) : (
        <p className={`mt-3 flex items-center text-sm ${changeClass}`}>
          {tone === 'up' ? <ArrowUpRight className="mr-0.5 h-4 w-4" /> : null}
          {tone === 'down' ? <ArrowDownRight className="mr-0.5 h-4 w-4" /> : null}
          <span className="font-medium">{formatChange(card.change) || '—'}</span>
          <span className="ml-1.5 font-normal text-[#697386]">{compare}</span>
        </p>
      )}
    </button>
  );
}

function Sparkline({ values, color }) {
  const nums = values && values.length ? values.map((value) => Number(value) || 0) : [0, 0];
  const width = 84;
  const height = 36;
  const max = Math.max(...nums, 1);
  const min = Math.min(...nums, 0);
  const span = max - min || 1;
  const step = nums.length === 1 ? 0 : width / (nums.length - 1);
  const points = nums.map((value, index) => {
    const x = index * step;
    const y = height - ((value - min) / span) * (height - 6) - 3;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true" className="shrink-0">
      <polyline fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" points={points} />
    </svg>
  );
}

function DeviceCard({ query }) {
  const rows = (query.data?.results || []).filter((row) => row.label && row.label !== 'Unknown');
  const chart = rows.map((row) => ({
    name: DEVICE_LABELS[row.label] || row.label,
    key: row.label,
    value: row.visitors,
  }));
  const total = chart.reduce((sum, row) => sum + row.value, 0);
  return (
    <section className="rounded-2xl border border-[#E3E8F2] bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-[#172033]">Devices</h3>
      {query.isLoading ? <div className="mt-4 h-52 animate-pulse rounded-xl bg-[#F5F7FC]" /> : null}
      {!query.isLoading && chart.length === 0 ? <p className="mt-6 text-sm text-[#697386]">No data in this range.</p> : null}
      {chart.length > 0 ? (
        <div className="mt-2 grid items-center gap-2 sm:grid-cols-[160px_1fr]">
          <div className="relative h-44">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={chart} dataKey="value" nameKey="name" innerRadius={52} outerRadius={70} paddingAngle={3} stroke="none">
                  {chart.map((entry) => (
                    <Cell key={entry.key} fill={DEVICE_COLORS[entry.key] || '#94A3B8'} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ borderRadius: 12, borderColor: '#E3E8F2', fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-2xl font-semibold text-[#172033]">{number(total)}</span>
              <span className="text-xs text-[#697386]">Visitors</span>
            </div>
          </div>
          <ul className="space-y-3">
            {chart.map((entry) => {
              const Icon = DEVICE_ICONS[entry.key] || Monitor;
              return (
                <li key={entry.key} className="flex items-center justify-between gap-3 text-sm">
                  <span className="inline-flex items-center gap-2 text-[#172033]">
                    <Icon className="h-4 w-4" style={{ color: DEVICE_COLORS[entry.key] || '#94A3B8' }} />
                    {entry.name}
                  </span>
                  <span className="tabular-nums text-[#697386]">
                    {number(entry.value)}
                    <span className="ml-2">{share(entry.value, total)}</span>
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function PagesTable({ rows, loading, error, expanded, onToggle }) {
  const visible = expanded ? rows : rows.slice(0, 5);
  const top = rows[0]?.pageviews || 1;
  return (
    <section className="rounded-2xl border border-[#E3E8F2] bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-base font-semibold text-[#172033]">Top pages</h3>
        {rows.length > 5 ? (
          <button type="button" onClick={onToggle} className="text-sm font-medium text-[#2F5BFF]">
            {expanded ? 'Show less' : 'View all'}
          </button>
        ) : null}
      </div>
      {loading ? <div className="h-40 animate-pulse rounded-xl bg-[#F5F7FC]" /> : null}
      {error ? <p className="text-sm text-red-600">Could not load pages.</p> : null}
      {!loading && !error && rows.length === 0 ? <p className="text-sm text-[#697386]">No pages in this range.</p> : null}
      {visible.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[#E3E8F2] text-left text-xs font-semibold uppercase tracking-wide text-[#697386]">
                <th className="py-3 pr-3">#</th>
                <th className="py-3 pr-3">Page</th>
                <th className="py-3 pr-3">Views</th>
                <th className="py-3">Visitors</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((row, index) => (
                <tr key={row.label} className="border-b border-[#F3F5F8] last:border-0">
                  <td className="py-3.5 pr-3 text-sm text-[#697386]">{index + 1}</td>
                  <td className="max-w-[220px] py-3.5 pr-3">
                    <span className="block truncate text-sm font-medium text-[#172033]" title={row.label}>{row.label}</span>
                  </td>
                  <td className="py-3.5 pr-3">
                    <div className="flex items-center gap-3">
                      <span className="w-8 text-sm tabular-nums text-[#172033]">{number(row.pageviews)}</span>
                      <span className="h-1.5 w-24 overflow-hidden rounded-full bg-[#F3F5F8]">
                        <span className="block h-full rounded-full bg-[#FF851B]" style={{ width: `${Math.max(8, (row.pageviews / top) * 100)}%` }} />
                      </span>
                    </div>
                  </td>
                  <td className="py-3.5 text-sm tabular-nums text-[#697386]">{number(row.visitors)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

function RegionsCard({ tab, onTab, countries, regions, cities }) {
  const queries = { country: countries, region: regions, city: cities };
  const query = queries[tab];
  const rows = query.data?.results || [];
  const totalViews = rows.reduce((sum, row) => sum + row.pageviews, 0);
  const top = rows[0];
  const showMap = tab === 'country' && rows.some((row) => row.label === 'BD');
  return (
    <section className="rounded-2xl border border-[#E3E8F2] bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-base font-semibold text-[#172033]">Regions</h3>
        <div className="inline-flex rounded-xl bg-[#F3F5F8] p-1">
          {[
            ['country', 'Countries'],
            ['region', 'Divisions'],
            ['city', 'Cities'],
          ].map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => onTab(id)}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${tab === id ? 'bg-white text-[#172033] shadow-sm' : 'text-[#697386]'}`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      {query.isLoading ? <div className="h-40 animate-pulse rounded-xl bg-[#F5F7FC]" /> : null}
      {query.isError ? <p className="text-sm text-red-600">Could not load this list.</p> : null}
      {!query.isLoading && !query.isError && rows.length === 0 ? (
        <p className="text-sm text-[#697386]">No places in this range.</p>
      ) : null}
      {rows.length > 0 ? (
        <div className={showMap ? 'grid gap-4 lg:grid-cols-[1fr_150px]' : ''}>
          <ul className="divide-y divide-[#F3F5F8]">
            {rows.slice(0, 6).map((row) => {
              const flag = tab === 'country' ? flagEmoji(row.label) : '';
              return (
                <li key={row.label} className="flex items-center gap-3 py-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[#F5F7FC] text-base">
                    {flag || <span className="h-2.5 w-2.5 rounded-full bg-[#FF851B]" />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-[#172033]">{dimensionLabel(tab, row.label)}</p>
                    <p className="text-xs text-[#697386]">{number(row.pageviews)} views · {number(row.visitors)} visitors</p>
                  </div>
                  <span className="text-sm font-medium tabular-nums text-[#697386]">{share(row.pageviews, totalViews)}</span>
                </li>
              );
            })}
          </ul>
          {showMap ? <BangladeshMap label={top?.label === 'BD' ? top : rows.find((row) => row.label === 'BD')} /> : null}
        </div>
      ) : null}
    </section>
  );
}

function BangladeshMap({ label }) {
  const projected = BD_OUTLINE.map(([lon, lat]) => [(lon - 87.7) * 46, (26.8 - lat) * 52]);
  const path = projected.map((point, index) => `${index === 0 ? 'M' : 'L'}${point[0].toFixed(1)} ${point[1].toFixed(1)}`).join(' ') + ' Z';
  const pin = [(90.41 - 87.7) * 46, (26.8 - 23.81) * 52];
  return (
    <div className="relative">
      <svg viewBox="0 0 230 300" className="h-44 w-full" role="img" aria-label="Bangladesh">
        <path d={path} fill="#E7EEF9" stroke="#2F5BFF" strokeWidth="3" />
        <circle cx={pin[0]} cy={pin[1]} r="6" fill="#FF851B" />
        <circle cx={pin[0]} cy={pin[1]} r="11" fill="#FF851B" opacity="0.25" />
      </svg>
      {label ? (
        <p className="mt-1 text-center text-xs text-[#697386]">
          Bangladesh · {number(label.pageviews)} views · {number(label.visitors)} visitors
        </p>
      ) : null}
    </div>
  );
}

function MiniTable({ title, dimension, query, empty }) {
  const rows = query.data?.results || [];
  return (
    <div>
      <h3 className="mb-3 text-sm font-semibold text-[#172033]">{title}</h3>
      {query.isLoading ? <div className="h-24 animate-pulse rounded-xl bg-[#F5F7FC]" /> : null}
      {query.isError ? <p className="text-sm text-red-600">Could not load this list.</p> : null}
      {!query.isLoading && !query.isError && rows.length === 0 ? (
        <p className="text-sm text-[#697386]">{empty || 'No data in this range.'}</p>
      ) : null}
      <table className="w-full">
        <tbody>
          {rows.slice(0, 6).map((row) => (
            <tr key={row.label} className="border-b border-[#F3F5F8] last:border-0">
              <td className="py-2.5 pr-3 text-sm text-[#172033]">{dimensionLabel(dimension, row.label)}</td>
              <td className="py-2.5 text-right text-sm tabular-nums text-[#697386]">{number(row.pageviews)} views</td>
              <td className="py-2.5 pl-4 text-right text-sm tabular-nums text-[#697386]">{number(row.visitors)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LiveFeed({ query, onSelect, canIdentify, device, source, onDevice, onSource }) {
  const [placeQuery, setPlaceQuery] = useState('');
  const all = query.data?.results || [];
  const rows = all.filter((row) => {
    if (device && row.device !== device) return false;
    if (source && row.source !== source) return false;
    if (placeQuery && !place(row).toLowerCase().includes(placeQuery.trim().toLowerCase())) return false;
    return true;
  });
  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-2">
        <select className="input w-auto" value={device} onChange={(event) => onDevice(event.target.value)} aria-label="Device">
          <option value="">All devices</option>
          {Object.entries(DEVICE_LABELS).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
        </select>
        <select className="input w-auto" value={source} onChange={(event) => onSource(event.target.value)} aria-label="Source">
          <option value="">All sources</option>
          {Object.entries(SOURCE_LABELS).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
        </select>
        <input
          className="input w-auto min-w-[180px]"
          value={placeQuery}
          onChange={(event) => setPlaceQuery(event.target.value)}
          placeholder="City or country"
          aria-label="Location"
        />
      </div>
      {query.isLoading ? <div className="h-40 animate-pulse rounded-xl bg-[#F5F7FC]" /> : null}
      {!query.isLoading && all.length === 0 ? <p className="text-sm text-[#697386]">No visits yet.</p> : null}
      {!query.isLoading && all.length > 0 && rows.length === 0 ? <p className="text-sm text-[#697386]">No visits for this filter.</p> : null}
      {rows.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px]">
            <thead>
              <tr className="border-b border-[#E3E8F2] text-left text-xs font-semibold uppercase tracking-wide text-[#697386]">
                {['Time', 'Page / URL', 'Location', 'Device', 'User'].map((heading) => (
                  <th key={heading} className="py-3 pr-4">{heading}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={`${row.occurred_at}-${row.path}-${index}`} className="border-b border-[#F3F5F8] last:border-0">
                  <td className="py-4 pr-4 text-sm text-[#697386]">
                    <span className="inline-flex items-center gap-2">
                      <span className={`h-2 w-2 rounded-full ${recent(row.occurred_at) ? 'bg-emerald-500' : 'bg-[#D5DCEA]'}`} />
                      {timeAgo(row.occurred_at)}
                    </span>
                  </td>
                  <td className="max-w-[280px] py-4 pr-4">
                    <span className="block truncate text-sm font-medium text-[#172033]" title={row.path}>{row.path}</span>
                  </td>
                  <td className="py-4 pr-4 text-sm text-[#697386]">{place(row)}</td>
                  <td className="py-4 pr-4 text-sm text-[#697386]">{DEVICE_LABELS[row.device] || row.device}</td>
                  <td className="py-4 text-sm">
                    <Person user={row.user} canIdentify={canIdentify} onSelect={onSelect} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function recent(iso) {
  const then = new Date(iso).getTime();
  return !Number.isNaN(then) && Date.now() - then < 5 * 60 * 1000;
}

function Person({ user, canIdentify, onSelect }) {
  if (!user) return <span className="rounded-full bg-[#F3F5F8] px-2 py-1 text-xs text-[#697386]">Guest</span>;
  if (!canIdentify || !user.id || !onSelect) {
    return <span className="text-[#697386]">Signed in</span>;
  }
  return (
    <button type="button" onClick={() => onSelect(user.id)} className="font-medium text-[#E86E00] hover:underline">
      {user.name}
    </button>
  );
}

function Customers({ query, search, onSearch, onSelect, canIdentify }) {
  const rows = query.data?.results || [];
  return (
    <div>
      {onSearch ? (
        <div className="relative mb-4 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#97A0B0]" />
          <input className="input pl-9" value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Name or email" />
        </div>
      ) : (
        <p className="mb-4 text-sm text-[#697386]">Customer names are hidden for this role.</p>
      )}
      {query.isLoading ? <div className="h-40 animate-pulse rounded-xl bg-[#F5F7FC]" /> : null}
      {!query.isLoading && rows.length === 0 ? <p className="text-sm text-[#697386]">No signed-in customers in this range.</p> : null}
      {rows.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px]">
            <thead>
              <tr className="border-b border-[#E3E8F2] text-left text-xs font-semibold uppercase tracking-wide text-[#697386]">
                {['Customer', 'Last seen', 'Views', 'Last page', 'Place', 'Device'].map((heading) => (
                  <th key={heading} className="py-3 pr-4">{heading}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr
                  key={row.user_id || `${row.last_seen}-${index}`}
                  className={`border-b border-[#F3F5F8] last:border-0 ${onSelect && row.user_id ? 'cursor-pointer hover:bg-[#F8FAFC]' : ''}`}
                  onClick={() => onSelect && row.user_id && onSelect(row.user_id)}
                >
                  <td className="py-4 pr-4">
                    <p className="text-sm font-medium text-[#172033]">{canIdentify ? row.name : 'Signed in'}</p>
                    {canIdentify && row.email ? <p className="text-xs text-[#697386]">{row.email}</p> : null}
                  </td>
                  <td className="py-4 pr-4 text-sm text-[#697386]">{formatWhen(row.last_seen)}</td>
                  <td className="py-4 pr-4 text-sm tabular-nums">{number(row.pageviews)}</td>
                  <td className="max-w-[200px] py-4 pr-4">
                    <span className="block truncate text-sm text-[#697386]" title={row.last_path}>{row.last_path}</span>
                  </td>
                  <td className="py-4 pr-4 text-sm text-[#697386]">{place(row)}</td>
                  <td className="py-4 text-sm text-[#697386]">{DEVICE_LABELS[row.device] || row.device || '—'}</td>
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
  if (query.isLoading) return <div className="h-40 animate-pulse rounded-xl bg-[#F5F7FC]" />;
  return (
    <div>
      <p className="mb-5 max-w-3xl text-sm leading-6 text-[#697386]">
        Product, cart, and checkout are page views. Orders are online orders placed in this range, excluding cancelled and external sales.
      </p>
      <ol className="space-y-5">
        {steps.map((step, index) => {
          const previous = index === 0 ? null : steps[index - 1].pageviews;
          const continued = previous ? Math.round((step.pageviews / previous) * 100) : null;
          return (
            <li key={step.key}>
              <div className="mb-2 flex items-baseline justify-between gap-3 text-sm">
                <span className="font-medium text-[#172033]">{index + 1}. {step.label}</span>
                <span className="text-[#697386]">
                  {number(step.pageviews)}
                  {step.key !== 'orders' ? ` · ${number(step.visitors)} visitors` : ''}
                  {continued !== null ? ` · ${continued}% of previous` : ''}
                </span>
              </div>
              <div className="h-3 rounded-full bg-[#F3F5F8]">
                <div
                  className="h-full rounded-full bg-[#202F70]"
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
  const rows = [...(timeline.data?.results || [])].reverse();

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button type="button" className="absolute inset-0 bg-black/30" aria-label="Close" onClick={onClose} />
      <aside className="relative h-full w-full max-w-md overflow-y-auto bg-white shadow-xl">
        <div className="sticky top-0 flex items-start justify-between border-b border-[#E3E8F2] bg-white px-5 py-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-[#697386]">Customer journey</p>
            <p className="text-lg font-semibold text-[#172033]">{user?.name || 'Customer'}</p>
            <p className="text-sm text-[#697386]">{user?.email}</p>
          </div>
          <button type="button" onClick={onClose} className="p-2 text-[#697386]" aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="p-5">
          {timeline.isLoading ? <div className="h-40 animate-pulse rounded-xl bg-[#F5F7FC]" /> : null}
          {!timeline.isLoading && rows.length === 0 ? <p className="text-sm text-[#697386]">No page history for this customer.</p> : null}
          <ol className="space-y-4">
            {rows.map((row, index) => (
              <li key={`${row.occurred_at}-${index}`} className="border-l-2 border-orange-200 pl-4">
                <p className="text-xs text-[#697386]">{formatWhen(row.occurred_at)}</p>
                <p className="font-medium text-[#172033]" title={row.path}>{row.path}</p>
                <p className="text-sm text-[#697386]">
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
