import { useState, useMemo } from 'react';
import Link from 'next/link';
import { Search, Filter, Eye, Trash2, ChevronLeft, ChevronRight } from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import { useGetOrdersQuery, useDeleteOrderMutation } from '@/store/api/ordersApi';
import { courierBadgeClass } from '@/components/orders/SteadfastCard';

export default function OrdersPage() {
  const [filters, setFilters] = useState({
    order_status: '',
    payment_status: '',
    order_type: '',
    search: '',
  });

  const queryParams = useMemo(() => {
    const params = {};
    if (filters.order_status) params.order_status = filters.order_status;
    if (filters.payment_status) params.payment_status = filters.payment_status;
    if (filters.order_type) params.order_type = filters.order_type;
    if (filters.search) params.search = filters.search;
    return params;
  }, [filters]);

  const { data: ordersData, isLoading: loading } = useGetOrdersQuery(queryParams);
  const [deleteOrder] = useDeleteOrderMutation();
  const orders = ordersData?.results || ordersData || [];

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
                onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                className="input pl-10"
              />
            </div>
          </div>

          <select
            value={filters.order_status}
            onChange={(e) => setFilters({ ...filters, order_status: e.target.value })}
            className="input w-auto"
          >
            <option value="">All Status</option>
            <option value="pending">Pending</option>
            <option value="confirmed">Confirmed</option>
            <option value="processing">Processing</option>
            <option value="shipped">Shipped</option>
            <option value="delivered">Delivered</option>
            <option value="cancelled">Cancelled</option>
          </select>

          <select
            value={filters.payment_status}
            onChange={(e) => setFilters({ ...filters, payment_status: e.target.value })}
            className="input w-auto"
          >
            <option value="">All Payments</option>
            <option value="pending">Pending</option>
            <option value="paid">Paid</option>
            <option value="failed">Failed</option>
          </select>

          <select
            value={filters.order_type}
            onChange={(e) => setFilters({ ...filters, order_type: e.target.value })}
            className="input w-auto"
          >
            <option value="">All Types</option>
            <option value="online">Online</option>
            <option value="in_shop">In-Shop</option>
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
                  <td colSpan="10" className="text-center py-8 text-gray-500">
                    Loading...
                  </td>
                </tr>
              ) : orders.length === 0 ? (
                <tr>
                  <td colSpan="10" className="text-center py-8 text-gray-500">
                    No orders found
                  </td>
                </tr>
              ) : (
                orders.map((order) => (
                  <tr key={order.id} className="border-b last:border-0 hover:bg-gray-50">
                    <td className="py-4 px-4">
                      <span className="font-medium text-gray-900">{order.order_number}</span>
                    </td>
                    <td className="py-4 px-4 text-gray-600">{order.customer_name}</td>
                    <td className="py-4 px-4">
                      <span className={`badge ${order.order_type === 'online' ? 'badge-info' : 'badge-success'}`}>
                        {order.order_type}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-gray-600">{order.item_count}</td>
                    <td className="py-4 px-4 font-semibold">৳{parseFloat(order.total).toLocaleString()}</td>
                    <td className="py-4 px-4">
                      <span className={`badge ${getStatusBadge(order.order_status)}`}>
                        {order.order_status.replace('_', ' ')}
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
                        {order.payment_status}
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
                        >
                          <Eye className="w-4 h-4" />
                        </Link>
                        {['pending', 'cancelled'].includes(order.order_status) && (
                          <button
                            onClick={() => handleDelete(order)}
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
      </div>
    </AdminLayout>
  );
}
