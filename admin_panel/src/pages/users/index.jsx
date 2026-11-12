import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import {
  Calendar, ChevronRight, RefreshCw, Search, ShoppingBag, UserCheck, Users,
} from 'lucide-react';
import AdminLayout from '@/components/layout/AdminLayout';
import LoadError from '@/components/ui/LoadError';
import Pager from '@/components/ui/Pager';
import { useGetCustomerSummaryQuery, useGetCustomersQuery } from '@/store/api/customersApi';
import { getMediaUrl } from '@/lib/utils';

function formatDate(value) {
  if (!value) return '—';
  return new Date(value).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
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

function Stat({ label, value, loading, icon: Icon, tone }) {
  return (
    <div className="stat-card">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">
            {loading ? '…' : (value ?? '—')}
          </p>
        </div>
        <div className={`rounded-xl p-3 ${tone}`}>
          <Icon className="h-6 w-6" />
        </div>
      </div>
    </div>
  );
}

export default function UsersPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [verified, setVerified] = useState('');
  const [orders, setOrders] = useState('');
  const [ordering, setOrdering] = useState('-date_joined');
  const queryRef = useRef('');

  useEffect(() => {
    const timer = setTimeout(() => {
      const next = search.trim();
      if (queryRef.current === next) return;
      queryRef.current = next;
      setQuery(next);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const params = useMemo(() => {
    const next = { page, ordering };
    if (query) next.search = query;
    if (status) next.is_active = status;
    if (verified) next.is_verified = verified;
    if (orders) next.has_orders = orders;
    return next;
  }, [page, ordering, query, status, verified, orders]);

  const { data, isLoading, isFetching, isError, refetch } = useGetCustomersQuery(params);
  const summary = useGetCustomerSummaryQuery();
  const users = Array.isArray(data?.results) ? data.results : [];

  const changeFilter = (setter) => (event) => {
    setter(event.target.value);
    setPage(1);
  };

  const openUser = (id) => router.push(`/users/${id}`);

  return (
    <AdminLayout title="Users">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Users</h1>
          <p className="mt-1 text-sm text-gray-500">
            Every customer account, including people who have not ordered yet.
          </p>
        </div>
        <button type="button" onClick={() => { refetch(); summary.refetch(); }} className="btn btn-secondary">
          <RefreshCw className={`mr-2 h-4 w-4 ${isFetching || summary.isFetching ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Total users" value={summary.data?.total} loading={summary.isLoading} icon={Users} tone="bg-blue-100 text-blue-600" />
        <Stat label="Active" value={summary.data?.active} loading={summary.isLoading} icon={UserCheck} tone="bg-green-100 text-green-600" />
        <Stat label="New this month" value={summary.data?.new_this_month} loading={summary.isLoading} icon={Calendar} tone="bg-purple-100 text-purple-600" />
        <Stat label="With orders" value={summary.data?.with_orders} loading={summary.isLoading} icon={ShoppingBag} tone="bg-amber-100 text-amber-600" />
      </div>

      <div className="card mb-6">
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1.4fr)_repeat(4,minmax(0,0.7fr))]">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search name, email, or phone"
              className="input pl-10"
            />
          </div>
          <select className="input" value={status} onChange={changeFilter(setStatus)} aria-label="Status">
            <option value="">All statuses</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
          <select className="input" value={verified} onChange={changeFilter(setVerified)} aria-label="Verification">
            <option value="">Verified or not</option>
            <option value="true">Verified</option>
            <option value="false">Unverified</option>
          </select>
          <select className="input" value={orders} onChange={changeFilter(setOrders)} aria-label="Orders">
            <option value="">Any order history</option>
            <option value="true">Has orders</option>
            <option value="false">No orders</option>
          </select>
          <select
            className="input"
            value={ordering}
            onChange={changeFilter(setOrdering)}
            aria-label="Sort"
          >
            <option value="-date_joined">Newest first</option>
            <option value="date_joined">Oldest first</option>
            <option value="-total_spent">Highest spend</option>
            <option value="-order_count">Most orders</option>
            <option value="-last_login">Recent sign-in</option>
          </select>
        </div>
      </div>

      <div className="card overflow-hidden !p-0">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px]">
            <thead className="border-b bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left table-header">User</th>
                <th className="px-4 py-3 text-left table-header">Contact</th>
                <th className="px-4 py-3 text-left table-header">Orders</th>
                <th className="px-4 py-3 text-left table-header">Spent</th>
                <th className="px-4 py-3 text-left table-header">Joined</th>
                <th className="px-4 py-3 text-left table-header">Status</th>
                <th className="px-4 py-3 text-left table-header">Verified</th>
                <th className="px-4 py-3 text-right table-header"> </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {isLoading ? (
                [...Array(6)].map((_, index) => (
                  <tr key={index}>
                    <td colSpan="8" className="px-4 py-4">
                      <div className="h-10 animate-pulse rounded bg-gray-100" />
                    </td>
                  </tr>
                ))
              ) : isError ? (
                <tr>
                  <td colSpan="8" className="px-4 py-4">
                    <LoadError title="Could not load users" onRetry={refetch} />
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan="8" className="px-4 py-16 text-center text-gray-500">
                    <Users className="mx-auto mb-3 h-10 w-10 text-gray-300" />
                    <p className="font-medium text-gray-700">No users match these filters</p>
                    <p className="mt-1 text-sm">Try another name, email, or phone number.</p>
                  </td>
                </tr>
              ) : (
                users.map((user) => (
                  <tr
                    key={user.id}
                    className="cursor-pointer hover:bg-gray-50"
                    onClick={() => openUser(user.id)}
                  >
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-3">
                        {user.avatar ? (
                          <img
                            src={getMediaUrl(user.avatar)}
                            alt=""
                            className="h-10 w-10 rounded-full object-cover"
                          />
                        ) : (
                          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-100 text-sm font-semibold text-primary-700">
                            {initials(user)}
                          </div>
                        )}
                        <div className="min-w-0">
                          <Link
                            href={`/users/${user.id}`}
                            className="block truncate font-medium text-gray-900 hover:text-primary-600"
                            onClick={(event) => event.stopPropagation()}
                          >
                            {user.full_name || 'Unnamed user'}
                          </Link>
                          <p className="truncate text-sm text-gray-500">{user.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-sm text-gray-600">
                      <p>{user.phone || 'No phone'}</p>
                      <p className="text-gray-400">{user.city || 'No city'}</p>
                    </td>
                    <td className="px-4 py-4 text-sm text-gray-900">{user.order_count || 0}</td>
                    <td className="px-4 py-4 text-sm font-medium text-gray-900">{formatMoney(user.total_spent)}</td>
                    <td className="px-4 py-4 text-sm text-gray-500">{formatDate(user.date_joined)}</td>
                    <td className="px-4 py-4">
                      <span className={`badge ${user.is_active ? 'badge-success' : 'badge-danger'}`}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      <span className={`badge ${user.is_verified ? 'badge-info' : 'badge-warning'}`}>
                        {user.is_verified ? 'Verified' : 'Unverified'}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-right text-gray-400">
                      <ChevronRight className="ml-auto h-4 w-4" />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <Pager page={page} count={data?.count} onPage={setPage} />
      </div>
    </AdminLayout>
  );
}
