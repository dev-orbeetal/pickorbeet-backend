import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  ShoppingCart, Package, DollarSign, AlertTriangle,
  ArrowUpRight, ArrowDownRight, Activity
} from 'lucide-react';
import AdminLayout from '@/components/layout/AdminLayout';
import { useGetDashboardStatsQuery } from '@/store/api/dashboardApi';
import { useGetOrdersQuery } from '@/store/api/ordersApi';
import { useGetTrafficOverviewQuery } from '@/store/api/trafficApi';
import { dhakaToday, formatChange, number } from '@/lib/traffic';

function VisitorChange({ value }) {
  const text = formatChange(value);
  if (!text) return <span className="text-gray-400">—</span>;
  const negative = text.startsWith('-');
  const positive = text.startsWith('+');
  return (
    <span className={`inline-flex items-center ${positive ? 'text-green-600' : negative ? 'text-red-600' : 'text-gray-500'}`}>
      {positive ? <ArrowUpRight className="w-4 h-4 mr-1" /> : null}
      {negative ? <ArrowDownRight className="w-4 h-4 mr-1" /> : null}
      {text}
    </span>
  );
}

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useGetDashboardStatsQuery();
  const { data: ordersData, isLoading: ordersLoading } = useGetOrdersQuery({ page_size: 5 });
  const [today, setToday] = useState('');
  useEffect(() => setToday(dhakaToday()), []);
  const { data: traffic } = useGetTrafficOverviewQuery(
    { from: today, to: today },
    { skip: !today, pollingInterval: 60000 },
  );

  const recentOrders = ordersData?.results || ordersData || [];
  const loading = statsLoading || ordersLoading;

  const statCards = stats ? [
    {
      title: "Today's Orders",
      value: stats.today?.orders || 0,
      icon: ShoppingCart,
      color: 'bg-blue-500',
      change: '+12%',
      positive: true,
    },
    {
      title: "Today's Revenue",
      value: `৳${(stats.today?.revenue || 0).toLocaleString()}`,
      icon: DollarSign,
      color: 'bg-green-500',
      change: '+8%',
      positive: true,
    },
    {
      title: 'Pending Orders',
      value: stats.pending_orders || 0,
      icon: Package,
      color: 'bg-yellow-500',
      change: '-3%',
      positive: false,
    },
    {
      title: 'Low Stock Items',
      value: stats.low_stock_products || 0,
      icon: AlertTriangle,
      color: 'bg-red-500',
      change: '+2',
      positive: false,
    },
  ] : [];

  const getStatusBadge = (status) => {
    const styles = {
      pending: 'badge-warning',
      confirmed: 'badge-info',
      processing: 'badge-info',
      shipped: 'badge-info',
      delivered: 'badge-success',
      cancelled: 'badge-danger',
    };
    return styles[status] || 'badge-gray';
  };

  if (loading) {
    return (
      <AdminLayout title="Dashboard">
        <div className="animate-pulse space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-6">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-32 bg-gray-200 rounded-xl" />
            ))}
          </div>
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout title="Dashboard">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-6 mb-8">
        <div className="stat-card">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-gray-500 mb-1">Today&apos;s Visitors</p>
              <p className="text-2xl font-bold text-gray-900">
                {traffic ? number(traffic.kpis?.visitors) : '—'}
              </p>
            </div>
            <div className="p-3 bg-primary-600 rounded-xl">
              <Activity className="w-6 h-6 text-white" />
            </div>
          </div>
          <div className="mt-4 flex items-center text-sm">
            <VisitorChange value={traffic?.change?.visitors} />
            <span className="text-gray-500 ml-1">vs yesterday</span>
            <Link href="/traffic" className="ml-auto text-primary-600 hover:underline">View</Link>
          </div>
        </div>
        {statCards.map((stat, index) => (
          <div key={index} className="stat-card">
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
              {stat.positive ? (
                <ArrowUpRight className="w-4 h-4 text-green-500 mr-1" />
              ) : (
                <ArrowDownRight className="w-4 h-4 text-red-500 mr-1" />
              )}
              <span className={stat.positive ? 'text-green-600' : 'text-red-600'}>
                {stat.change}
              </span>
              <span className="text-gray-500 ml-1">vs yesterday</span>
            </div>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Recent Orders */}
        <div className="lg:col-span-2 card p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-gray-900">Recent Orders</h2>
            <a href="/orders" className="text-sm text-primary-600 hover:underline">
              View All
            </a>
          </div>

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
                {recentOrders.map((order) => (
                  <tr key={order.id} className="border-b last:border-0 hover:bg-gray-50">
                    <td className="py-3 px-2">
                      <span className="font-medium text-gray-900">{order.order_number}</span>
                    </td>
                    <td className="py-3 px-2 text-gray-600">{order.customer_name}</td>
                    <td className="py-3 px-2 font-medium">৳{parseFloat(order.total).toLocaleString()}</td>
                    <td className="py-3 px-2">
                      <span className={`badge ${getStatusBadge(order.order_status)}`}>
                        {order.order_status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">This Month</h2>

          <div className="space-y-6">
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-600">Total Orders</span>
                <span className="font-semibold">{stats?.this_month?.orders || 0}</span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full">
                <div className="h-full bg-primary-500 rounded-full" style={{ width: '70%' }} />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-600">Revenue</span>
                <span className="font-semibold">৳{(stats?.this_month?.revenue || 0).toLocaleString()}</span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full">
                <div className="h-full bg-green-500 rounded-full" style={{ width: '55%' }} />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-600">Products</span>
                <span className="font-semibold">{stats?.total_products || 0}</span>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-600">Categories</span>
                <span className="font-semibold">{stats?.total_categories || 0}</span>
              </div>
            </div>
          </div>

          <div className="mt-6 pt-6 border-t">
            <h3 className="text-sm font-medium text-gray-900 mb-3">Quick Actions</h3>
            <div className="space-y-2">
              <a href="/pos" className="block w-full btn btn-primary text-center">
                New In-Shop Order
              </a>
              <a href="/products/new" className="block w-full btn btn-secondary text-center">
                Add Product
              </a>
            </div>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
