import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import {
  ArrowLeft, Mail, MapPin, Pencil, Phone, Plus, Shield, ShoppingBag, Trash2, X,
} from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import LoadError from '@/components/ui/LoadError';
import BdAddressFields from '@/components/BdAddressFields';
import {
  useCreateCustomerAddressMutation,
  useDeleteCustomerAddressMutation,
  useGetCustomerQuery,
  useUpdateCustomerAddressMutation,
  useUpdateCustomerMutation,
} from '@/store/api/customersApi';
import { getMediaUrl, routeId } from '@/lib/utils';
import { statusLabel } from '@/lib/labels';

function formatDate(value, withTime = false) {
  if (!value) return '—';
  return new Date(value).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    ...(withTime ? { hour: 'numeric', minute: '2-digit' } : {}),
  });
}

function formatMoney(value) {
  return `৳${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function initials(user) {
  const letters = `${user?.first_name || ''} ${user?.last_name || ''}`
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('');
  return letters || '?';
}

function messageOf(value) {
  if (!value) return '';
  if (Array.isArray(value)) return String(value[0] || '');
  if (typeof value === 'string') return value;
  return '';
}

function errorMap(error) {
  const data = error?.data;
  if (!data || typeof data !== 'object' || Array.isArray(data)) return {};
  return Object.fromEntries(
    Object.entries(data).map(([key, value]) => [key, messageOf(value)]),
  );
}

function profileForm(user) {
  return {
    first_name: user.first_name || '',
    last_name: user.last_name || '',
    email: user.email || '',
    phone: user.phone || '',
    address: user.address || '',
    city: user.city || '',
    postal_code: user.postal_code || '',
    is_active: Boolean(user.is_active),
    is_verified: Boolean(user.is_verified),
  };
}

function blankAddress(user) {
  const name = `${user?.first_name || ''} ${user?.last_name || ''}`.trim();
  return {
    label: '',
    address_type: 'shipping',
    full_name: name,
    phone: user?.phone || '',
    address_line1: '',
    address_line2: '',
    division: '',
    district: '',
    post_office: '',
    postal_code: '',
    city: '',
    is_default: false,
  };
}

function addressForm(address) {
  return {
    label: address.label || '',
    address_type: address.address_type || 'shipping',
    full_name: address.full_name || '',
    phone: address.phone || '',
    address_line1: address.address_line1 || '',
    address_line2: address.address_line2 || '',
    division: address.division || '',
    district: address.district || '',
    post_office: address.post_office || '',
    postal_code: address.postal_code || '',
    city: address.city || '',
    is_default: Boolean(address.is_default),
  };
}

function addressPayload(form) {
  return {
    label: form.label.trim(),
    address_type: form.address_type,
    full_name: form.full_name.trim(),
    phone: form.phone.trim(),
    address_line1: form.address_line1.trim(),
    address_line2: form.address_line2.trim(),
    division: form.division,
    district: form.district,
    post_office: form.post_office,
    postal_code: form.postal_code,
    city: form.city.trim(),
    country: 'Bangladesh',
    is_default: Boolean(form.is_default),
  };
}

function Field({ label, required, error, hint, children }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-gray-700">
        {label}
        {required ? <span className="text-red-500"> *</span> : null}
      </span>
      {children}
      {error ? <span className="mt-1 block text-xs text-red-600">{error}</span> : null}
      {hint && !error ? <span className="mt-1 block text-xs text-gray-500">{hint}</span> : null}
    </label>
  );
}

function orderBadge(status) {
  if (status === 'delivered' || status === 'paid') return 'badge-success';
  if (status === 'cancelled' || status === 'failed' || status === 'refunded') return 'badge-danger';
  if (status === 'pending') return 'badge-warning';
  return 'badge-info';
}

function AddressEditor({ initial, submitLabel, saving, error, onSubmit, onCancel }) {
  const [form, setForm] = useState(initial);
  const fields = errorMap(error);
  const general = messageOf(error?.data?.detail) || messageOf(error?.data?.non_field_errors);

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(addressPayload(form));
      }}
      className="grid gap-4 sm:grid-cols-2"
    >
      {general ? (
        <p className="sm:col-span-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{general}</p>
      ) : null}
      <Field label="Label" error={fields.label} hint="Home, office, or a short name">
        <input className="input" value={form.label} maxLength={40} onChange={(event) => setForm({ ...form, label: event.target.value })} />
      </Field>
      <Field label="Type" error={fields.address_type}>
        <select className="input" value={form.address_type} onChange={(event) => setForm({ ...form, address_type: event.target.value })}>
          <option value="shipping">Shipping</option>
          <option value="billing">Billing</option>
        </select>
      </Field>
      <Field label="Full name" required error={fields.full_name}>
        <input className="input" required value={form.full_name} maxLength={200} onChange={(event) => setForm({ ...form, full_name: event.target.value })} />
      </Field>
      <Field label="Phone" required error={fields.phone}>
        <input className="input" required value={form.phone} maxLength={20} onChange={(event) => setForm({ ...form, phone: event.target.value })} />
      </Field>
      <Field label="Address line 1" required error={fields.address_line1}>
        <input className="input" required value={form.address_line1} maxLength={255} onChange={(event) => setForm({ ...form, address_line1: event.target.value })} />
      </Field>
      <Field label="Address line 2" error={fields.address_line2}>
        <input className="input" value={form.address_line2} maxLength={255} onChange={(event) => setForm({ ...form, address_line2: event.target.value })} />
      </Field>
      <div className="grid gap-4 sm:col-span-2 sm:grid-cols-2">
        <BdAddressFields value={form} onChange={setForm} Field={Field} />
      </div>
      <label className="flex items-center gap-2 text-sm text-gray-700 sm:col-span-2">
        <input
          type="checkbox"
          checked={form.is_default}
          onChange={(event) => setForm({ ...form, is_default: event.target.checked })}
        />
        Default address
      </label>
      <div className="flex justify-end gap-2 sm:col-span-2">
        <button type="button" onClick={onCancel} className="btn btn-secondary">Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? 'Saving…' : submitLabel}
        </button>
      </div>
    </form>
  );
}

function addressSummary(address) {
  return [
    address.address_line1,
    address.address_line2,
    [address.post_office, address.postal_code].filter(Boolean).join(' '),
    [address.city, address.district, address.division].filter(Boolean).join(', '),
  ].filter(Boolean);
}

export default function UserDetailPage() {
  const router = useRouter();
  const id = routeId(router);
  const { data: user, isLoading, isError, error, refetch } = useGetCustomerQuery(id, { skip: !id });
  const [updateCustomer, { isLoading: saving }] = useUpdateCustomerMutation();
  const [createAddress, { isLoading: creatingAddress }] = useCreateCustomerAddressMutation();
  const [updateAddress, { isLoading: updatingAddress }] = useUpdateCustomerAddressMutation();
  const [deleteAddress, { isLoading: deletingAddress }] = useDeleteCustomerAddressMutation();

  const [form, setForm] = useState(null);
  const [formFor, setFormFor] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [addressError, setAddressError] = useState(null);
  const [seen, setSeen] = useState(false);

  // The exported page can finish this request before React subscribes. Reading
  // the store again after mount picks up a result that arrived during hydration.
  useEffect(() => {
    setSeen(true);
  }, []);

  useEffect(() => {
    if (!user?.id || formFor === user.id) return;
    setForm(profileForm(user));
    setFormFor(user.id);
    setFieldErrors({});
    setAdding(false);
    setEditingId(null);
    setAddressError(null);
  }, [user, formFor]);

  const saveUser = async (event) => {
    event.preventDefault();
    if (!user || !form) return;
    if (user.is_active && !form.is_active) {
      const confirmed = window.confirm('Deactivating this account signs them out of every device. Continue?');
      if (!confirmed) return;
    }
    try {
      const saved = await updateCustomer({ id: user.id, ...form }).unwrap();
      setForm(profileForm(saved));
      setFormFor(saved.id);
      setFieldErrors({});
      toast.success('User updated');
    } catch (saveError) {
      setFieldErrors(errorMap(saveError));
      toast.error(messageOf(saveError?.data?.detail) || 'Could not save this user');
    }
  };

  const saveAddress = async (payload, addressId) => {
    try {
      if (addressId) {
        await updateAddress({ userId: user.id, addressId, ...payload }).unwrap();
        toast.success('Address updated');
      } else {
        await createAddress({ userId: user.id, ...payload }).unwrap();
        toast.success('Address added');
      }
      setAdding(false);
      setEditingId(null);
      setAddressError(null);
    } catch (saveError) {
      setAddressError(saveError);
      toast.error('Could not save this address');
    }
  };

  const removeAddress = async (address) => {
    const name = address.label || address.address_line1 || 'this address';
    if (!window.confirm(`Remove ${name}?`)) return;
    try {
      await deleteAddress({ userId: user.id, addressId: address.id }).unwrap();
      if (editingId === address.id) setEditingId(null);
      toast.success('Address removed');
    } catch (saveError) {
      toast.error(messageOf(saveError?.data?.detail) || 'Could not remove this address');
    }
  };

  if (isError && !user) {
    return (
      <AdminLayout title="User">
        <LoadError
          title={error?.status === 404 ? 'This user could not be found' : 'Could not load this user'}
          onRetry={error?.status === 404 ? undefined : refetch}
        />
        <Link href="/users" className="btn btn-secondary mt-4">Back to users</Link>
      </AdminLayout>
    );
  }

  if (!seen || !id || isLoading || !user || formFor !== user.id || !form) {
    return (
      <AdminLayout title="User">
        <div className="card h-40 animate-pulse bg-gray-100" />
      </AdminLayout>
    );
  }

  const generalError = messageOf(fieldErrors.detail) || messageOf(fieldErrors.non_field_errors);
  const addresses = Array.isArray(user.addresses) ? user.addresses : [];
  const orders = Array.isArray(user.recent_orders) ? user.recent_orders : [];

  return (
    <AdminLayout title={user.full_name || 'User'}>
      <Link href="/users" className="mb-4 inline-flex items-center text-sm font-medium text-gray-500 hover:text-gray-800">
        <ArrowLeft className="mr-1.5 h-4 w-4" />
        Users
      </Link>

      <div className="card mb-6">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
          {user.avatar ? (
            <img src={getMediaUrl(user.avatar)} alt="" className="h-16 w-16 rounded-full object-cover" />
          ) : (
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary-100 text-xl font-semibold text-primary-700">
              {initials(user)}
            </div>
          )}
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold text-gray-900">{user.full_name || 'Unnamed user'}</h1>
              <span className={`badge ${user.is_active ? 'badge-success' : 'badge-danger'}`}>
                {user.is_active ? 'Active' : 'Inactive'}
              </span>
              <span className={`badge ${user.is_verified ? 'badge-info' : 'badge-warning'}`}>
                {user.is_verified ? 'Verified' : 'Unverified'}
              </span>
              {user.two_factor_enabled ? <span className="badge badge-gray">Two-factor on</span> : null}
            </div>
            <p className="mt-1 truncate text-sm text-gray-500">{user.email}</p>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:min-w-[240px]">
            <div className="rounded-xl bg-blue-50 px-4 py-3">
              <p className="text-xs text-blue-700">Orders</p>
              <p className="text-xl font-semibold text-blue-900">{user.order_count || 0}</p>
            </div>
            <div className="rounded-xl bg-green-50 px-4 py-3">
              <p className="text-xs text-green-700">Spent</p>
              <p className="text-xl font-semibold text-green-900">{formatMoney(user.total_spent)}</p>
            </div>
          </div>
        </div>
      </div>

      <form onSubmit={saveUser}>
        <div className="grid gap-6 lg:grid-cols-3">
          <section className="card lg:col-span-2">
            <h2 className="text-lg font-semibold text-gray-900">Profile</h2>
            <p className="mt-1 text-sm text-gray-500">
              Name, sign-in email, phone, and the address stored on the account.
            </p>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <Field label="First name" required error={fieldErrors.first_name}>
                <input
                  className="input"
                  required
                  maxLength={100}
                  value={form.first_name}
                  onChange={(event) => setForm({ ...form, first_name: event.target.value })}
                />
              </Field>
              <Field label="Last name" required error={fieldErrors.last_name}>
                <input
                  className="input"
                  required
                  maxLength={100}
                  value={form.last_name}
                  onChange={(event) => setForm({ ...form, last_name: event.target.value })}
                />
              </Field>
              <Field label="Email" required error={fieldErrors.email}>
                <input
                  type="email"
                  className="input"
                  required
                  value={form.email}
                  onChange={(event) => setForm({ ...form, email: event.target.value })}
                />
              </Field>
              <Field label="Phone" error={fieldErrors.phone} hint="Bangladeshi mobile, such as 01712345678. Leave blank to clear.">
                <input
                  className="input"
                  maxLength={20}
                  value={form.phone}
                  onChange={(event) => setForm({ ...form, phone: event.target.value })}
                />
              </Field>
              <Field label="Address" error={fieldErrors.address}>
                <textarea
                  rows={3}
                  className="input resize-y"
                  value={form.address}
                  onChange={(event) => setForm({ ...form, address: event.target.value })}
                />
              </Field>
              <div className="grid gap-4">
                <Field label="City" error={fieldErrors.city}>
                  <input
                    className="input"
                    maxLength={100}
                    value={form.city}
                    onChange={(event) => setForm({ ...form, city: event.target.value })}
                  />
                </Field>
                <Field label="Postal code" error={fieldErrors.postal_code}>
                  <input
                    className="input"
                    maxLength={20}
                    value={form.postal_code}
                    onChange={(event) => setForm({ ...form, postal_code: event.target.value })}
                  />
                </Field>
              </div>
            </div>
          </section>

          <section className="card h-fit space-y-5">
            <h2 className="text-lg font-semibold text-gray-900">Account</h2>
            <label className="flex items-start justify-between gap-4">
              <span>
                <span className="block text-sm font-medium text-gray-900">Active</span>
                <span className="mt-1 block text-xs text-gray-500">
                  Turning this off signs the user out of every device.
                </span>
              </span>
              <input
                type="checkbox"
                className="toggle shrink-0"
                checked={form.is_active}
                onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
              />
            </label>
            <label className="flex items-start justify-between gap-4">
              <span>
                <span className="block text-sm font-medium text-gray-900">Verified</span>
                <span className="mt-1 block text-xs text-gray-500">
                  Marks the email as confirmed.
                </span>
              </span>
              <input
                type="checkbox"
                className="toggle shrink-0"
                checked={form.is_verified}
                onChange={(event) => setForm({ ...form, is_verified: event.target.checked })}
              />
            </label>
            <dl className="space-y-3 border-t pt-4 text-sm">
              <div className="flex items-start justify-between gap-3">
                <dt className="text-gray-500">Joined</dt>
                <dd className="text-right text-gray-900">{formatDate(user.date_joined, true)}</dd>
              </div>
              <div className="flex items-start justify-between gap-3">
                <dt className="text-gray-500">Last sign-in</dt>
                <dd className="text-right text-gray-900">{formatDate(user.last_login, true)}</dd>
              </div>
              <div className="flex items-start justify-between gap-3">
                <dt className="flex items-center gap-1.5 text-gray-500"><Shield className="h-3.5 w-3.5" /> Two-factor</dt>
                <dd className="text-gray-900">{user.two_factor_enabled ? 'On' : 'Off'}</dd>
              </div>
              <div className="flex items-start justify-between gap-3">
                <dt className="flex items-center gap-1.5 text-gray-500"><Mail className="h-3.5 w-3.5" /> Recovery</dt>
                <dd className="max-w-[160px] truncate text-right text-gray-900">{user.recovery_email || 'Not set'}</dd>
              </div>
            </dl>
          </section>
        </div>

        {generalError ? (
          <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{generalError}</p>
        ) : null}
        <div className="mt-4 flex justify-end">
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Saving…' : 'Save changes'}
          </button>
        </div>
      </form>

      <section className="card mt-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Saved addresses</h2>
            <p className="mt-1 text-sm text-gray-500">Delivery and billing addresses on this account.</p>
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              setAdding((open) => !open);
              setEditingId(null);
              setAddressError(null);
            }}
          >
            {adding ? <X className="mr-2 h-4 w-4" /> : <Plus className="mr-2 h-4 w-4" />}
            {adding ? 'Close' : 'Add address'}
          </button>
        </div>

        {adding ? (
          <div className="mt-5 rounded-xl border border-[#E4E9F2] p-4">
            <AddressEditor
              initial={blankAddress(user)}
              submitLabel="Add address"
              saving={creatingAddress}
              error={addressError}
              onCancel={() => { setAdding(false); setAddressError(null); }}
              onSubmit={(payload) => saveAddress(payload)}
            />
          </div>
        ) : null}

        {addresses.length === 0 && !adding ? (
          <div className="mt-6 rounded-xl border border-dashed border-gray-200 px-4 py-10 text-center text-sm text-gray-500">
            <MapPin className="mx-auto mb-2 h-8 w-8 text-gray-300" />
            No saved addresses yet.
          </div>
        ) : (
          <div className="mt-5 space-y-3">
            {addresses.map((address) => (
              <div key={address.id} className="rounded-xl border border-[#E4E9F2] p-4">
                {editingId === address.id ? (
                  <AddressEditor
                    initial={addressForm(address)}
                    submitLabel="Save address"
                    saving={updatingAddress}
                    error={addressError}
                    onCancel={() => { setEditingId(null); setAddressError(null); }}
                    onSubmit={(payload) => saveAddress(payload, address.id)}
                  />
                ) : (
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium text-gray-900">{address.label || address.full_name}</p>
                        <span className="badge badge-gray">{statusLabel(address.address_type)}</span>
                        {address.is_default ? <span className="badge badge-info">Default</span> : null}
                        {address.is_inside_dhaka ? <span className="badge badge-success">Inside Dhaka</span> : null}
                      </div>
                      <p className="mt-1 flex items-center gap-1.5 text-sm text-gray-500">
                        <Phone className="h-3.5 w-3.5" />
                        {address.phone}
                      </p>
                      <p className="mt-2 text-sm text-gray-700">{addressSummary(address).join(', ')}</p>
                    </div>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        className="btn btn-secondary !px-3"
                        onClick={() => {
                          setEditingId(address.id);
                          setAdding(false);
                          setAddressError(null);
                        }}
                      >
                        <Pencil className="mr-1.5 h-4 w-4" />
                        Edit
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger !px-3"
                        disabled={deletingAddress}
                        onClick={() => removeAddress(address)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card mt-6">
        <div className="flex items-center gap-2">
          <ShoppingBag className="h-5 w-5 text-gray-400" />
          <h2 className="text-lg font-semibold text-gray-900">Recent orders</h2>
        </div>
        {orders.length === 0 ? (
          <p className="mt-4 text-sm text-gray-500">No orders yet.</p>
        ) : (
          <div className="mt-4 divide-y">
            {orders.map((order) => (
              <Link
                key={order.id}
                href={`/orders/${order.id}`}
                className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0 hover:bg-gray-50"
              >
                <div>
                  <p className="font-medium text-primary-600">#{order.order_number}</p>
                  <p className="text-sm text-gray-500">{formatDate(order.created_at, true)}</p>
                </div>
                <div className="text-right">
                  <p className="font-semibold text-gray-900">{formatMoney(order.total)}</p>
                  <div className="mt-1 flex justify-end gap-2">
                    <span className={`badge ${orderBadge(order.order_status)}`}>{statusLabel(order.order_status)}</span>
                    <span className={`badge ${orderBadge(order.payment_status)}`}>{statusLabel(order.payment_status)}</span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
        <p className="mt-4 text-xs text-gray-400">
          The order count includes every order. Spend excludes cancelled and refunded orders. This list shows the eight most recent.
        </p>
      </section>
    </AdminLayout>
  );
}

export async function getStaticPaths() {
  return { paths: [{ params: { id: '_' } }], fallback: false };
}

export async function getStaticProps() {
  return { props: {} };
}
