import Link from 'next/link';
import {
  ShoppingCart, Package, DollarSign, AlertTriangle, ArrowUpRight, ArrowDownRight
} from 'lucide-react';
import AdminLayout from '@/components/layout/AdminLayout';
import LoadError from '@/components/ui/LoadError';
import { useGetDashboardStatsQuery } from '@/store/api/dashboardApi';
import { useGetOrdersQuery } from '@/store/api/ordersApi';
import { statusLabel } from '@/lib/labels';

function changeFrom(current, previous) {
  const now = Number(current || 0);
  const before = Number(previous || 0);
  if (!before && !now) return null;
  if (!before) return { text: 'New', positive: true };
  const pct = Math.round(((now - before) / before) * 100);
  return { text: `${pct > 0 ? '+' : ''}${pct}%`, positive: pct >= 0 };
}

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading, isError: statsError, refetch: refetchStats } = useGetDashboardStatsQuery();
  const { data: ordersData, isLoading: ordersLoading, isError: ordersError, refetch: refetchOrders } = useGetOrdersQuery({ page_size: 5 });

  const recentOrders = ordersData?.results || (Array.isArray(ordersData) ? ordersData : []);
  const loading = statsLoading || ordersLoading;

  const orderChange = changeFrom(stats?.today?.orders, stats?.yesterday?.orders);
  const revenueChange = changeFrom(stats?.today?.revenue, stats?.yesterday?.revenue);

  const statCards = stats ? [
    {
      title: "Today's Orders",
      value: stats.today?.orders || 0,
      icon: ShoppingCart,
      color: 'bg-blue-500',
      href: '/orders',
      note: 'All orders placed today',
      change: orderChange,
    },
    {
      title: "Today's Revenue",
      value: `৳${(stats.today?.revenue || 0).toLocaleString()}`,
      icon: DollarSign,
      color: 'bg-green-500',
      href: '/reports',
      note: 'Order totals placed today',
      change: revenueChange,
    },
    {
      title: 'Pending Orders',
      value: stats.pending_orders || 0,
      icon: Package,
      color: 'bg-yellow-500',
      href: '/orders?status=pending',
      note: 'Waiting to be confirmed',
    },
    {
      title: 'Low Stock Items',
      value: stats.low_stock_products || 0,
      icon: AlertTriangle,
      color: 'bg-red-500',
      href: '/inventory?stock=low_stock',
      note: 'At or below the alert level',
    },
  ] : [];

  const getStatusBadge = (status) => {
    const styles = {
      pending: 'badge-warning',
      confirmed: 'badge-info',
      processing: 'badge-info',
      shipped: 'badge-info',
      out_for_delivery: 'bg-cyan-100 text-cyan-800',
      delivered: 'badge-success',
      cancelled: 'badge-danger',
      refunded: 'badge-gray',
    };
    return styles[status] || 'badge-gray';
  };

  if (loading) {
    return (
      <AdminLayout title="Dashboard">
        <div className="animate-pulse space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-32 bg-gray-200 rounded-xl" />
            ))}
          </div>
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout title="Dashboard">
      <p className="mb-4 text-sm text-gray-500">Today and this month. Open Reports for a date range.</p>
      {statsError && (
        <div className="mb-6">
          <LoadError title="Could not load dashboard totals" onRetry={refetchStats} />
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {statCards.map((stat) => (
          <Link key={stat.title} href={stat.href} className="stat-card block hover:shadow-md">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-gray-500 mb-1">{stat.title}</p>
                <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
              </div>
              <div className={`p-3 ${stat.color} rounded-xl`}>
                <stat.icon className="w-6 h-6 text-white" />
              </div>
            </div>
            <div className="mt-4 flex items-center text-sm">
              {stat.change && (
                <>
                  {stat.change.positive ? (
                    <ArrowUpRight className="w-4 h-4 text-green-500 mr-1" />
                  ) : (
                    <ArrowDownRight className="w-4 h-4 text-red-500 mr-1" />
                  )}
                  <span className={stat.change.positive ? 'text-green-600' : 'text-red-600'}>
                    {stat.change.text}
                  </span>
                  <span className="text-gray-500 ml-1">vs yesterday</span>
                </>
              )}
              {!stat.change && <span className="text-gray-500">{stat.note}</span>}
            </div>
          </Link>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 card p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-gray-900">Recent Orders</h2>
            <Link href="/orders" className="text-sm text-primary-600 hover:underline">
              View All
            </Link>
          </div>

          {ordersError ? (
            <LoadError title="Could not load recent orders" onRetry={refetchOrders} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-3 px-2 table-header">Order</th>
                    <th className="text-left py-3 px-2 table-header">Customer</th>
                    <th className="text-left py-3 px-2 table-header">Total</th>
                    <th className="text-left py-3 px-2 table-header">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {recentOrders.length === 0 ? (
                    <tr>
                      <td colSpan="4" className="py-8 text-center text-gray-500">No orders yet</td>
                    </tr>
                  ) : recentOrders.map((order) => (
                    <tr key={order.id} className="border-b last:border-0 hover:bg-gray-50">
                      <td className="py-3 px-2">
                        <Link href={`/orders/${order.id}`} className="font-medium text-gray-900 hover:text-primary-600">
                          {order.order_number}
                        </Link>
                      </td>
                      <td className="py-3 px-2 text-gray-600">{order.customer_name}</td>
                      <td className="py-3 px-2 font-medium">৳{parseFloat(order.total).toLocaleString()}</td>
                      <td className="py-3 px-2">
                        <span className={`badge ${getStatusBadge(order.order_status)}`}>
                          {statusLabel(order.order_status)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">This Month</h2>
          <p className="text-sm text-gray-500 mb-6">Orders placed since the first of the month, including unpaid.</p>

          <div className="space-y-4">
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">Total Orders</span>
              <span className="font-semibold">{stats?.this_month?.orders || 0}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">Revenue</span>
              <span className="font-semibold">৳{(stats?.this_month?.revenue || 0).toLocaleString()}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">Products</span>
              <span className="font-semibold">{stats?.total_products || 0}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">Categories</span>
              <span className="font-semibold">{stats?.total_categories || 0}</span>
            </div>
          </div>

          <div className="mt-6 pt-6 border-t">
            <h3 className="text-sm font-medium text-gray-900 mb-3">Quick Actions</h3>
            <div className="space-y-2">
              <Link href="/pos" className="block w-full btn btn-primary text-center">
                New In-Shop Order
              </Link>
              <Link href="/products/new" className="block w-full btn btn-secondary text-center">
                Add Product
              </Link>
            </div>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
