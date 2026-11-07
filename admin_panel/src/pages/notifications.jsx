import { useEffect, useMemo, useState } from 'react';
import { Bell, Send, Sparkles, Clock, History, Settings2, Search } from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import { getMediaUrl } from '@/lib/utils';
import { useGetProductsQuery } from '@/store/api/productsApi';
import {
  useCancelCampaignMutation,
  useCreateCampaignMutation,
  useEstimateCampaignMutation,
  useGetAutomationsQuery,
  useGetCampaignSettingsQuery,
  useGetCampaignTemplatesQuery,
  useGetCampaignsQuery,
  useLazySearchCampaignCustomersQuery,
  useScheduleCampaignMutation,
  useSendCampaignMutation,
  useTestCampaignMutation,
  useUpdateAutomationMutation,
  useUpdateCampaignSettingsMutation,
} from '@/store/api/campaignsApi';

const AUDIENCES = [
  ['all', 'All customers'],
  ['interested', 'Saved it or have it in the cart'],
  ['wishlist', 'Wishlist only'],
  ['cart', 'In the cart'],
  ['buyers', 'Bought from this category'],
  ['customers', 'Chosen customers'],
];

const TABS = [
  ['compose', 'Compose', Sparkles],
  ['history', 'History', History],
  ['automations', 'Automations', Settings2],
];

function fill(text, product) {
  if (!text) return '';
  const values = {
    product_name: product?.name || 'this product',
    price: product?.price ? `৳${Number(product.price).toLocaleString('en-BD')}` : '',
    old_price: product?.compare_price ? `৳${Number(product.compare_price).toLocaleString('en-BD')}` : '',
    discount: '',
    stock: '',
    category: product?.category_name || '',
    count: '3',
    others: '2',
  };
  return text.replace(/\{\{\s*(\w+)\s*\}\}/g, (_, key) => values[key] ?? '');
}

function productImage(product) {
  return getMediaUrl(product?.image || product?.primary_image);
}

export default function NotificationsPage() {
  const [tab, setTab] = useState('compose');
  return (
    <AdminLayout title="Notifications">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Product notifications</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Push a new arrival, a stock alert or a sale to phones and the in-app inbox.
          </p>
        </div>
        <div className="flex rounded-xl bg-white border border-[#E4E9F2] p-1">
          {TABS.map(([id, label, Icon]) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`px-3 py-1.5 text-sm font-medium rounded-lg inline-flex items-center gap-1.5 ${
                tab === id ? 'bg-primary-500 text-white' : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>
      </div>
      {tab === 'compose' && <ComposePanel />}
      {tab === 'history' && <HistoryPanel />}
      {tab === 'automations' && <AutomationsPanel />}
    </AdminLayout>
  );
}

function ComposePanel() {
  const { data: templates = [] } = useGetCampaignTemplatesQuery();
  const [createCampaign, { isLoading: creating }] = useCreateCampaignMutation();
  const [sendCampaign, { isLoading: sending }] = useSendCampaignMutation();
  const [scheduleCampaign, { isLoading: scheduling }] = useScheduleCampaignMutation();
  const [testCampaign, { isLoading: testing }] = useTestCampaignMutation();
  const [estimateCampaign] = useEstimateCampaignMutation();
  const [searchCustomers] = useLazySearchCampaignCustomersQuery();

  const [kind, setKind] = useState('new_arrival');
  const [title, setTitle] = useState('Something New Just Arrived! ✨');
  const [body, setBody] = useState("Meet your next favorite — {{product_name}} is now available. Don't miss out!");
  const [cta, setCta] = useState('Tap to explore');
  const [audience, setAudience] = useState('all');
  const [product, setProduct] = useState(null);
  const [query, setQuery] = useState('');
  const [when, setWhen] = useState('');
  const [customerQuery, setCustomerQuery] = useState('');
  const [customers, setCustomers] = useState([]);
  const [pickedCustomer, setPickedCustomer] = useState(null);
  const [chosenIds, setChosenIds] = useState([]);
  const [reach, setReach] = useState(null);

  const { data: productData, isFetching: loadingProducts } = useGetProductsQuery({
    search: query,
    page_size: 8,
  });
  const products = productData?.results || [];

  const previewTitle = fill(title, product);
  const previewBody = fill(body, product);
  const image = productImage(product);

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const result = await estimateCampaign({
          audience,
          product_id: product?.id,
          customer_ids: chosenIds,
        }).unwrap();
        if (!cancelled) setReach(result);
      } catch {
        if (!cancelled) setReach(null);
      }
    }, 280);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [audience, product, chosenIds, estimateCampaign]);

  const applyTemplate = (row) => {
    setKind(row.kind);
    setTitle(row.title);
    setBody(row.body);
    setCta(row.cta_label || 'Tap to explore');
  };

  const save = async () => {
    if (!title.trim() || !body.trim()) {
      toast.error('Write a title and a message.');
      return null;
    }
    try {
      return await createCampaign({
        kind,
        title,
        body,
        cta_label: cta,
        audience,
        product_id: product?.id || null,
        customer_ids: audience === 'customers' ? chosenIds : [],
      }).unwrap();
    } catch (error) {
      toast.error(error.data?.error || error.data?.detail || 'Could not save the notification.');
      return null;
    }
  };

  const onSend = async () => {
    const campaign = await save();
    if (!campaign) return;
    try {
      const sent = await sendCampaign(campaign.id).unwrap();
      toast.success(`Sent to ${sent.recipients} customer${sent.recipients === 1 ? '' : 's'}.`);
    } catch (error) {
      toast.error(error.data?.error || 'Could not send.');
    }
  };

  const onSchedule = async () => {
    if (!when) {
      toast.error('Pick a time to send.');
      return;
    }
    const campaign = await save();
    if (!campaign) return;
    try {
      await scheduleCampaign({ id: campaign.id, when: new Date(when).toISOString() }).unwrap();
      toast.success('Scheduled.');
    } catch (error) {
      toast.error(error.data?.error || 'Could not schedule.');
    }
  };

  const onTest = async () => {
    if (!pickedCustomer) {
      toast.error('Choose a customer to send a test to.');
      return;
    }
    const campaign = await save();
    if (!campaign) return;
    try {
      await testCampaign({ id: campaign.id, customer_id: pickedCustomer.id }).unwrap();
      toast.success(`Test sent to ${pickedCustomer.full_name || pickedCustomer.email}.`);
    } catch (error) {
      toast.error(error.data?.error || 'Could not send the test.');
    }
  };

  const lookupCustomers = async (value) => {
    setCustomerQuery(value);
    if (value.trim().length < 2) {
      setCustomers([]);
      return;
    }
    try {
      const data = await searchCustomers({ search: value, page_size: 8 }).unwrap();
      setCustomers(data.results || data || []);
    } catch {
      setCustomers([]);
    }
  };

  const kinds = useMemo(() => [...new Set(templates.map((row) => row.kind))], [templates]);

  return (
    <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,360px)]">
      <div className="min-w-0 space-y-5">
        <section className="card p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-3">Start from a template</p>
          <div className="flex flex-wrap gap-2 mb-4">
            {kinds.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setKind(item)}
                className={`px-3 py-1 text-xs font-semibold rounded-full capitalize ${
                  kind === item ? 'bg-primary-500 text-white' : 'bg-gray-100 text-gray-600'
                }`}
              >
                {item.replaceAll('_', ' ')}
              </button>
            ))}
          </div>
          <div className="grid md:grid-cols-2 gap-3">
            {templates.filter((row) => row.kind === kind).map((row) => (
              <button
                key={row.id}
                type="button"
                onClick={() => applyTemplate(row)}
                className="text-left rounded-2xl border border-[#E4E9F2] p-4 hover:border-primary-300 hover:shadow-sm transition"
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-semibold text-gray-900">{row.name}</p>
                  {row.is_recommended && (
                    <span className="text-[10px] font-semibold uppercase tracking-wide text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
                      Recommended
                    </span>
                  )}
                </div>
                <p className="text-sm font-medium mt-2">{row.title}</p>
                <p className="text-xs text-gray-500 mt-1 line-clamp-2">{row.body}</p>
              </button>
            ))}
          </div>
        </section>

        <section className="card p-5 space-y-4">
          <ProductPicker
            product={product}
            query={query}
            products={products}
            loading={loadingProducts}
            onQuery={(value) => {
              setProduct(null);
              setQuery(value);
            }}
            onPick={(item) => {
              setProduct(item);
              setQuery('');
            }}
            onClear={() => {
              setProduct(null);
              setQuery('');
            }}
          />
          <label className="block">
            <span className="text-xs font-semibold text-gray-500">Title</span>
            <input className="input mt-1" maxLength={80} value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>
          <label className="block">
            <span className="text-xs font-semibold text-gray-500">Message</span>
            <textarea
              className="input mt-1 min-h-[88px]"
              maxLength={240}
              value={body}
              onChange={(event) => setBody(event.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-xs font-semibold text-gray-500">Button label</span>
            <input className="input mt-1" maxLength={40} value={cta} onChange={(event) => setCta(event.target.value)} />
          </label>

          <label className="block">
            <span className="text-xs font-semibold text-gray-500">Who should get this</span>
            <select className="input mt-1" value={audience} onChange={(event) => setAudience(event.target.value)}>
              {AUDIENCES.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>

          {audience === 'customers' && (
            <label className="block">
              <span className="text-xs font-semibold text-gray-500">Customers</span>
              <input
                className="input mt-1"
                placeholder="Search name, phone or email"
                value={customerQuery}
                onChange={(event) => lookupCustomers(event.target.value)}
              />
              {customers.length > 0 && (
                <ul className="mt-2 border border-[#E4E9F2] rounded-xl overflow-hidden">
                  {customers.map((person) => (
                    <li key={person.id}>
                      <button
                        type="button"
                        className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50"
                        onClick={() => {
                          setChosenIds((current) => current.includes(person.id) ? current : [...current, person.id]);
                          setCustomers([]);
                          setCustomerQuery('');
                        }}
                      >
                        {person.full_name || person.email}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <p className="text-xs text-gray-500 mt-1">{chosenIds.length} selected</p>
            </label>
          )}

          <p className="text-sm text-gray-600">
            {reach
              ? `${reach.recipients} customer${reach.recipients === 1 ? '' : 's'} will get this · ${reach.reachable} with a phone`
              : 'Pick an audience to see how many people this reaches.'}
          </p>
        </section>
      </div>

      <div className="min-w-0 space-y-5 xl:sticky xl:top-4">
        <PhonePreview title={previewTitle} body={previewBody} cta={cta} image={image} />
        <InAppPreview title={previewTitle} body={previewBody} image={image} kind={kind} />

        <section className="card p-5 space-y-3">
          <button type="button" onClick={onSend} disabled={creating || sending} className="btn btn-primary w-full">
            <Send className="w-4 h-4 mr-2" />
            {sending ? 'Sending…' : 'Send now'}
          </button>
          <div className="space-y-2">
            <input
              type="datetime-local"
              className="input w-full min-w-0 max-w-full"
              value={when}
              onChange={(event) => setWhen(event.target.value)}
            />
            <button type="button" onClick={onSchedule} disabled={scheduling} className="btn btn-secondary w-full">
              <Clock className="w-4 h-4 mr-1" />
              {scheduling ? 'Scheduling…' : 'Schedule'}
            </button>
          </div>
          <div className="border-t border-[#E4E9F2] pt-3 space-y-2">
            <p className="text-xs font-semibold text-gray-500">Send a test to one phone</p>
            <input
              className="input"
              placeholder="Search a customer"
              value={pickedCustomer ? (pickedCustomer.full_name || pickedCustomer.email) : customerQuery}
              onChange={(event) => {
                setPickedCustomer(null);
                lookupCustomers(event.target.value);
              }}
            />
            {!pickedCustomer && customers.length > 0 && (
              <ul className="border border-[#E4E9F2] rounded-xl overflow-hidden">
                {customers.map((person) => (
                  <li key={person.id}>
                    <button
                      type="button"
                      className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50"
                      onClick={() => {
                        setPickedCustomer(person);
                        setCustomers([]);
                      }}
                    >
                      {person.full_name || person.email}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <button type="button" onClick={onTest} disabled={testing} className="btn btn-secondary w-full">
              <Bell className="w-4 h-4 mr-2" />
              {testing ? 'Sending test…' : 'Send test'}
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}

function ProductPicker({ product, query, products, loading, onQuery, onPick, onClear }) {
  return (
    <div>
      <span className="text-xs font-semibold text-gray-500">Choose a product</span>
      {product ? (
        <div className="mt-1 flex items-center gap-3 rounded-xl border border-[#E4E9F2] p-2">
          <img
            src={productImage(product) || '/placeholder.png'}
            alt=""
            className="h-12 w-12 shrink-0 rounded-lg bg-gray-100 object-cover"
          />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-gray-900">{product.name}</p>
            <p className="truncate text-xs text-gray-500">{product.sku || 'This product is used in the preview'}</p>
          </div>
          <button type="button" onClick={onClear} className="shrink-0 text-xs font-semibold text-primary-600">
            Change
          </button>
        </div>
      ) : (
        <div className="mt-1">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
            <input
              className="input w-full min-w-0 pl-9"
              placeholder="Search by name or SKU"
              value={query}
              onChange={(event) => onQuery(event.target.value)}
            />
          </div>
          <ul className="mt-2 max-h-64 overflow-y-auto rounded-xl border border-[#E4E9F2] bg-white">
            {products.map((item) => (
              <li key={item.id} className="border-b border-[#E4E9F2] last:border-b-0">
                <button
                  type="button"
                  onClick={() => onPick(item)}
                  className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-gray-50"
                >
                  <img
                    src={productImage(item) || '/placeholder.png'}
                    alt=""
                    className="h-10 w-10 shrink-0 rounded-lg bg-gray-100 object-cover"
                  />
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium">{item.name}</span>
                    {item.sku && <span className="block truncate text-xs text-gray-500">{item.sku}</span>}
                  </span>
                </button>
              </li>
            ))}
            {!loading && products.length === 0 && (
              <li className="px-3 py-2 text-sm text-gray-500">
                {query.trim() ? 'No products match.' : 'No products yet.'}
              </li>
            )}
            {loading && products.length === 0 && (
              <li className="px-3 py-2 text-sm text-gray-500">Loading products…</li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

function PhonePreview({ title, body, cta, image }) {
  return (
    <div className="card p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-3">On the phone</p>
      <div className="rounded-[28px] bg-[#0B1020] p-3 shadow-inner">
        <div className="rounded-2xl bg-white p-3 flex gap-3 items-start">
          <div className="w-14 h-14 rounded-xl overflow-hidden bg-[#F3F5FB] shrink-0">
            {image ? <img src={image} alt="" className="w-full h-full object-cover" /> : <div className="w-full h-full bg-gray-100" />}
          </div>
          <div className="min-w-0">
            <p className="text-[13px] font-semibold text-[#051340] leading-snug">{title || 'Title'}</p>
            <p className="text-[12px] text-[#6A7390] mt-0.5 leading-snug line-clamp-2">{body || 'Message'}</p>
            <p className="text-[11px] font-semibold text-primary-500 mt-1">{cta || 'Tap to explore'} →</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function InAppPreview({ title, body, image, kind }) {
  const label = kind === 'support' ? 'Help chat' : kind?.includes('price') || kind === 'flash_sale' ? 'Offer' : 'New arrival';
  return (
    <div className="card p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-3">In the app</p>
      <div className="rounded-2xl border border-[#E4E9F2] bg-white p-3 flex gap-3 shadow-sm">
        <div className="w-10 h-10 rounded-[13px] overflow-hidden bg-[#EDF3FE] shrink-0">
          {image ? <img src={image} alt="" className="w-full h-full object-cover" /> : <Sparkles className="w-5 h-5 m-2.5 text-primary-500" />}
        </div>
        <div className="min-w-0">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-bold tracking-[0.08em] uppercase text-primary-500">{label}</p>
            <p className="text-[10px] text-gray-400">now</p>
          </div>
          <p className="text-sm font-semibold text-[#051340] truncate">{title || 'Title'}</p>
          <p className="text-xs text-gray-500 line-clamp-2">{body || 'Message'}</p>
        </div>
      </div>
    </div>
  );
}

function HistoryPanel() {
  const { data, isLoading } = useGetCampaignsQuery({ page_size: 20 });
  const [cancelCampaign] = useCancelCampaignMutation();
  const rows = data?.results || [];

  return (
    <div className="card overflow-hidden p-0">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
          <tr>
            <th className="px-4 py-3">Notification</th>
            <th className="px-4 py-3">Audience</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Reached</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody>
          {isLoading && (
            <tr><td className="px-4 py-6 text-gray-500" colSpan={5}>Loading…</td></tr>
          )}
          {rows.map((row) => (
            <tr key={row.id} className="border-t border-[#E4E9F2]">
              <td className="px-4 py-3">
                <p className="font-medium">{row.title}</p>
                <p className="text-xs text-gray-500 capitalize">{row.kind.replaceAll('_', ' ')} · {row.source}</p>
              </td>
              <td className="px-4 py-3 capitalize text-gray-600">{row.audience}</td>
              <td className="px-4 py-3 capitalize">{row.status}</td>
              <td className="px-4 py-3 text-gray-600">
                {row.recipients} inbox · {row.pushed} phones
                {row.opened ? ` · ${row.opened} opened` : ''}
              </td>
              <td className="px-4 py-3 text-right">
                {row.status === 'scheduled' && (
                  <button
                    type="button"
                    className="text-sm text-red-600"
                    onClick={async () => {
                      try {
                        await cancelCampaign(row.id).unwrap();
                        toast.success('Cancelled.');
                      } catch (error) {
                        toast.error(error.data?.error || 'Could not cancel.');
                      }
                    }}
                  >
                    Cancel
                  </button>
                )}
              </td>
            </tr>
          ))}
          {!isLoading && rows.length === 0 && (
            <tr><td className="px-4 py-6 text-gray-500" colSpan={5}>Nothing sent yet.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function AutomationsPanel() {
  const { data: rules = [] } = useGetAutomationsQuery();
  const { data: settings } = useGetCampaignSettingsQuery();
  const [updateAutomation] = useUpdateAutomationMutation();
  const [updateSettings] = useUpdateCampaignSettingsMutation();
  const [draft, setDraft] = useState(null);

  useEffect(() => {
    if (settings) setDraft(settings);
  }, [settings]);

  const saveSettings = async (next) => {
    setDraft(next);
    try {
      await updateSettings({
        quiet_start: next.quiet_start,
        quiet_end: next.quiet_end,
        daily_cap: Number(next.daily_cap),
        arrival_settle_minutes: Number(next.arrival_settle_minutes),
      }).unwrap();
      toast.success('Saved.');
    } catch {
      toast.error('Could not save settings.');
    }
  };

  return (
    <div className="grid lg:grid-cols-2 gap-6">
      <div className="space-y-4">
        {rules.map((rule) => (
          <section key={rule.trigger} className="card p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-semibold capitalize">{rule.trigger.replaceAll('_', ' ')}</p>
                <p className="text-xs text-gray-500 mt-0.5">Audience: {rule.audience}</p>
              </div>
              <label className="inline-flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={rule.enabled}
                  onChange={async (event) => {
                    try {
                      await updateAutomation({ trigger: rule.trigger, enabled: event.target.checked }).unwrap();
                    } catch {
                      toast.error('Could not update this automation.');
                    }
                  }}
                />
                On
              </label>
            </div>
            <p className="text-sm mt-3">{rule.title}</p>
            <p className="text-xs text-gray-500 mt-1">{rule.body}</p>
            {rule.threshold > 0 && (
              <p className="text-xs text-gray-500 mt-2">Threshold: {rule.threshold}</p>
            )}
          </section>
        ))}
      </div>
      {draft && (
        <section className="card p-5 space-y-3 h-fit">
          <p className="font-semibold">Quiet hours and limits</p>
          <label className="block text-sm">
            Quiet from
            <input className="input mt-1" type="time" value={String(draft.quiet_start).slice(0, 5)} onChange={(event) => saveSettings({ ...draft, quiet_start: event.target.value })} />
          </label>
          <label className="block text-sm">
            Quiet until
            <input className="input mt-1" type="time" value={String(draft.quiet_end).slice(0, 5)} onChange={(event) => saveSettings({ ...draft, quiet_end: event.target.value })} />
          </label>
          <label className="block text-sm">
            Daily cap per customer
            <input className="input mt-1" type="number" min="1" max="20" value={draft.daily_cap} onChange={(event) => saveSettings({ ...draft, daily_cap: event.target.value })} />
          </label>
          <label className="block text-sm">
            Wait after a product goes live (minutes)
            <input className="input mt-1" type="number" min="0" max="180" value={draft.arrival_settle_minutes} onChange={(event) => saveSettings({ ...draft, arrival_settle_minutes: event.target.value })} />
          </label>
          {draft.placeholders && (
            <p className="text-xs text-gray-500 pt-2">
              Placeholders: {Object.keys(draft.placeholders).map((name) => `{{${name}}}`).join(', ')}
            </p>
          )}
        </section>
      )}
    </div>
  );
}
