import { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { Search, Eye, Trash2, Plus } from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import LoadError from '@/components/ui/LoadError';
import Pager from '@/components/ui/Pager';
import { useGetOrdersQuery, useDeleteOrderMutation } from '@/store/api/ordersApi';
import { courierBadgeClass } from '@/components/orders/SteadfastCard';
import { statusLabel } from '@/lib/labels';

export default function OrdersPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({
    order_status: '',
    payment_status: '',
    order_type: '',
    platform: '',
    search: '',
  });

  useEffect(() => {
    if (!router.isReady) return;
    const status = typeof router.query.status === 'string' ? router.query.status : '';
    if (status) setFilters((current) => ({ ...current, order_status: status }));
  }, [router.isReady, router.query.status]);

  const queryParams = useMemo(() => {
    const params = { page };
    if (filters.order_status) params.order_status = filters.order_status;
    if (filters.payment_status) params.payment_status = filters.payment_status;
    if (filters.order_type) params.order_type = filters.order_type;
    if (filters.platform) params.platform = filters.platform;
    if (filters.search) params.search = filters.search;
    return params;
  }, [filters, page]);

  const { data: ordersData, isLoading: loading, isError, refetch } = useGetOrdersQuery(queryParams);
  const [deleteOrder] = useDeleteOrderMutation();
  const orders = Array.isArray(ordersData?.results || ordersData)
    ? (ordersData?.results || ordersData)
    : [];

  const updateFilters = (patch) => {
    setFilters((current) => ({ ...current, ...patch }));
    setPage(1);
  };

  const handleDelete = async (order) => {
    if (!['pending', 'cancelled'].includes(order.order_status)) {
      toast.error('Can only delete pending or cancelled orders');
      return;
    }
    if (window.confirm(`Are you sure you want to delete order ${order.order_number}?`)) {
      try {
        await deleteOrder(order.id).unwrap();
        toast.success('Order deleted successfully');
      } catch (error) {
        toast.error(error?.data?.error || 'Failed to delete order');
      }
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      pending: 'badge-warning',
      confirmed: 'badge-info',
      processing: 'badge-info',
      shipped: 'bg-purple-100 text-purple-800',
      out_for_delivery: 'bg-cyan-100 text-cyan-800',
      delivered: 'badge-success',
      cancelled: 'badge-danger',
      refunded: 'badge-gray',
    };
    return styles[status] || 'badge-gray';
  };

  const getPaymentBadge = (status) => {
    const styles = {
      pending: 'badge-warning',
      paid: 'badge-success',
      failed: 'badge-danger',
      refunded: 'badge-gray',
    };
    return styles[status] || 'badge-gray';
  };

  return (
    <AdminLayout title="Orders">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Orders</h1>
          <p className="text-sm text-gray-500 mt-1">
            Online storefront orders and orders created from the admin panel.
          </p>
        </div>
        <Link href="/orders/new" className="btn btn-primary">
          <Plus className="w-4 h-4 mr-2" />
          Add Order
        </Link>
      </div>

      {/* Filters */}
      <div className="card p-4 mb-6">
        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[200px]">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search orders..."
                value={filters.search}
                onChange={(e) => updateFilters({ search: e.target.value })}
                className="input pl-10"
              />
            </div>
          </div>

          <select
            value={filters.order_status}
            onChange={(e) => updateFilters({ order_status: e.target.value })}
            className="input w-auto"
          >
            <option value="">All Status</option>
            <option value="pending">Pending</option>
            <option value="confirmed">Confirmed</option>
            <option value="processing">Processing</option>
            <option value="shipped">Shipped</option>
            <option value="out_for_delivery">Out for delivery</option>
            <option value="delivered">Delivered</option>
            <option value="cancelled">Cancelled</option>
            <option value="refunded">Refunded</option>
          </select>

          <select
            value={filters.payment_status}
            onChange={(e) => updateFilters({ payment_status: e.target.value })}
            className="input w-auto"
          >
            <option value="">All Payments</option>
            <option value="pending">Pending</option>
            <option value="paid">Paid</option>
            <option value="failed">Failed</option>
            <option value="refunded">Refunded</option>
          </select>

          <select
            value={filters.order_type}
            onChange={(e) => updateFilters({ order_type: e.target.value })}
            className="input w-auto"
          >
            <option value="">All Types</option>
            <option value="online">Online</option>
            <option value="external">External</option>
          </select>

          <select
            value={filters.platform}
            onChange={(e) => updateFilters({ platform: e.target.value })}
            className="input w-auto"
          >
            <option value="">All Platforms</option>
            <option value="web">Web</option>
            <option value="app">App</option>
            <option value="admin">Admin</option>
            <option value="unknown">Unknown</option>
          </select>
        </div>
      </div>

      {/* Orders Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left py-4 px-4 table-header">Order</th>
                <th className="text-left py-4 px-4 table-header">Customer</th>
                <th className="text-left py-4 px-4 table-header">Type</th>
                <th className="text-left py-4 px-4 table-header">Platform</th>
                <th className="text-left py-4 px-4 table-header">Items</th>
                <th className="text-left py-4 px-4 table-header">Total</th>
                <th className="text-left py-4 px-4 table-header">Status</th>
                <th className="text-left py-4 px-4 table-header">Courier</th>
                <th className="text-left py-4 px-4 table-header">Payment</th>
                <th className="text-left py-4 px-4 table-header">Date</th>
                <th className="text-left py-4 px-4 table-header">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="11" className="text-center py-8 text-gray-500">
                    Loading...
                  </td>
                </tr>
              ) : isError ? (
                <tr>
                  <td colSpan="11" className="py-4">
                    <LoadError title="Could not load orders" onRetry={refetch} />
                  </td>
                </tr>
              ) : orders.length === 0 ? (
                <tr>
                  <td colSpan="11" className="text-center py-8 text-gray-500">
                    No orders found
                  </td>
                </tr>
              ) : (
                orders.map((order) => (
                  <tr
                    key={order.id}
                    className="border-b last:border-0 hover:bg-gray-50 cursor-pointer"
                    onClick={() => router.push(`/orders/${order.id}`)}
                  >
                    <td className="py-4 px-4">
                      <span className="font-medium text-gray-900">{order.order_number}</span>
                    </td>
                    <td className="py-4 px-4 text-gray-600">{order.customer_name}</td>
                    <td className="py-4 px-4">
                      <span className={`badge ${
                        order.order_type === 'online'
                          ? 'badge-info'
                          : order.order_type === 'external'
                            ? 'badge-warning'
                            : 'badge-success'
                      }`}>
                        {statusLabel(order.order_type)}
                      </span>
                    </td>
                    <td className="py-4 px-4">
                      <span className={`badge ${
                        order.platform === 'web'
                          ? 'badge-info'
                          : order.platform === 'app'
                            ? 'badge-success'
                            : order.platform === 'admin'
                              ? 'badge-warning'
                              : 'badge-gray'
                      }`}>
                        {statusLabel(order.platform || 'unknown')}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-gray-600">{order.item_count}</td>
                    <td className="py-4 px-4 font-semibold">৳{parseFloat(order.total).toLocaleString()}</td>
                    <td className="py-4 px-4">
                      <span className={`badge ${getStatusBadge(order.order_status)}`}>
                        {statusLabel(order.order_status)}
                      </span>
                    </td>
                    <td className="py-4 px-4">
                      {order.tracking_code ? (
                        <div>
                          <span className={`badge border ${courierBadgeClass(order.shipment_status_group)}`}>
                            {order.shipment_status_label || order.shipment_status}
                          </span>
                          <p className="text-xs text-gray-500 mt-1">{order.tracking_code}</p>
                        </div>
                      ) : (
                        <span className="text-xs text-gray-400">Not booked</span>
                      )}
                    </td>
                    <td className="py-4 px-4">
                      <span className={`badge ${getPaymentBadge(order.payment_status)}`}>
                        {statusLabel(order.payment_status)}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-gray-500 text-sm">
                      {new Date(order.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-4 px-4">
                      <div className="flex items-center gap-1">
                        <Link
                          href={`/orders/${order.id}`}
                          className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg inline-flex"
                          onClick={(event) => event.stopPropagation()}
                        >
                          <Eye className="w-4 h-4" />
                        </Link>
                        {['pending', 'cancelled'].includes(order.order_status) && (
                          <button
                            onClick={(event) => {
                              event.stopPropagation();
                              handleDelete(order);
                            }}
                            className="p-2 text-red-600 hover:bg-red-50 rounded-lg"
                            title="Delete order"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <Pager page={page} count={ordersData?.count} onPage={setPage} />
      </div>
    </AdminLayout>
  );
}
