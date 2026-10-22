import { useState } from 'react';
import {
  Package, TrendingUp, TrendingDown, AlertTriangle,
  DollarSign, BarChart3, ArrowUpRight, ArrowDownRight,
  RefreshCw, Download, Search, Filter, Eye,
  PackageX, PackageCheck, Clock, Layers,
  ChevronDown, ChevronRight, Plus, Minus, X, Edit3
} from 'lucide-react';
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  AreaChart, Area, ComposedChart
} from 'recharts';
import AdminLayout from '@/components/layout/AdminLayout';
import { useGetInventoryAnalyticsQuery } from '@/store/api/reportsApi';
import {
  useGetInventoryItemsQuery,
  useUpdateProductStockMutation,
  useUpdateVariantStockMutation,
} from '@/store/api/productsApi';
import { toast } from 'react-hot-toast';

const COLORS = ['#10B981', '#F59E0B', '#EF4444', '#3B82F6', '#8B5CF6', '#EC4899', '#06B6D4', '#84CC16'];

const REASON_OPTIONS = [
  { value: 'purchase', label: 'Purchase / Restock' },
  { value: 'return', label: 'Customer Return' },
  { value: 'damaged', label: 'Damaged' },
  { value: 'lost', label: 'Lost / Missing' },
  { value: 'adjustment', label: 'Manual Adjustment' },
];

export default function InventoryManagementPage() {
  const { data, isLoading: loading, isFetching: refreshing, refetch } = useGetInventoryAnalyticsQuery();
  const [activeTab, setActiveTab] = useState('overview');
  const [searchTerm, setSearchTerm] = useState('');

  // Stock management state
  const [stockSearch, setStockSearch] = useState('');
  const [stockFilter, setStockFilter] = useState('');
  const [expandedProducts, setExpandedProducts] = useState({});
  const [stockModal, setStockModal] = useState(null); // { type: 'product'|'variant', id, name, currentStock }
  const [stockForm, setStockForm] = useState({ operation: 'add', quantity: '', reason: 'purchase', note: '' });

  // Category detail modal state
  const [categoryDetail, setCategoryDetail] = useState(null); // { id, name, ...stats }
  const [catExpandedProducts, setCatExpandedProducts] = useState({});

  const { data: inventoryData, isLoading: inventoryLoading, isFetching: inventoryRefreshing } = useGetInventoryItemsQuery(
    { search: stockSearch, stock_status: stockFilter },
    { skip: activeTab !== 'manage' }
  );
  const { data: categoryItemsData, isLoading: categoryItemsLoading } = useGetInventoryItemsQuery(
    { category: categoryDetail?.id },
    { skip: !categoryDetail }
  );
  const [updateProductStock, { isLoading: updatingProduct }] = useUpdateProductStockMutation();
  const [updateVariantStock, { isLoading: updatingVariant }] = useUpdateVariantStockMutation();

  const inventoryItems = inventoryData?.items || [];

  const toggleExpand = (productId) => {
    setExpandedProducts(prev => ({ ...prev, [productId]: !prev[productId] }));
  };

  const openStockModal = (type, id, productId, name, currentStock) => {
    setStockModal({ type, id, productId, name, currentStock });
    setStockForm({ operation: 'add', quantity: '', reason: 'purchase', note: '' });
  };

  const handleStockUpdate = async (e) => {
    e.preventDefault();
    if (!stockModal || !stockForm.quantity) return;

    const qty = parseInt(stockForm.quantity);
    if (isNaN(qty) || qty <= 0) {
      toast.error('Enter a valid quantity');
      return;
    }

    try {
      if (stockModal.type === 'variant') {
        await updateVariantStock({
          variantId: stockModal.id,
          quantity: qty,
          operation: stockForm.operation,
          reason: stockForm.reason,
          note: stockForm.note,
        }).unwrap();
      } else {
        await updateProductStock({
          productId: stockModal.id,
          quantity: qty,
          operation: stockForm.operation,
          reason: stockForm.reason,
          note: stockForm.note,
        }).unwrap();
      }
      toast.success('Stock updated successfully');
      setStockModal(null);
      refetch();
    } catch (error) {
      toast.error(error?.data?.error || 'Failed to update stock');
    }
  };

  const getStockBadge = (stock, threshold) => {
    if (stock === 0) return { label: 'Out of Stock', cls: 'bg-red-100 text-red-700' };
    if (stock <= threshold) return { label: 'Low Stock', cls: 'bg-yellow-100 text-yellow-700' };
    return { label: 'In Stock', cls: 'bg-green-100 text-green-700' };
  };

  const openCategoryDetail = (category) => {
    setCategoryDetail(category);
    setCatExpandedProducts({});
  };

  const toggleCatExpand = (productId) => {
    setCatExpandedProducts(prev => ({ ...prev, [productId]: !prev[productId] }));
  };

  const fetchInventoryData = () => {
    refetch();
  };

  const formatCurrency = (value) => {
    return `৳${(value || 0).toLocaleString()}`;
  };

  const formatNumber = (value) => {
    return (value || 0).toLocaleString();
  };

  const getStockStatusColor = (status) => {
    switch (status) {
      case 'in_stock': return 'text-green-600 bg-green-100';
      case 'low_stock': return 'text-yellow-600 bg-yellow-100';
      case 'out_of_stock': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  if (loading) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center h-96">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
        </div>
      </AdminLayout>
    );
  }

  const summary = data?.summary || {};
  const salesStats = data?.sales_stats || {};
  const stockDistribution = data?.stock_status_distribution || {};
  const categoryStock = data?.category_stock || [];
  const dailySales = data?.daily_sales_trend || [];
  const weeklySales = data?.weekly_sales_trend || [];
  const topSelling = data?.top_selling_products || [];
  const slowMoving = data?.slow_moving_products || [];
  const lowStock = data?.low_stock_products || [];
  const stockMovements = data?.recent_stock_movements || [];
  const stockAge = data?.stock_age_distribution || {};

  const stockStatusData = [
    { name: 'In Stock', value: stockDistribution.in_stock || 0, color: '#10B981' },
    { name: 'Low Stock', value: stockDistribution.low_stock || 0, color: '#F59E0B' },
    { name: 'Out of Stock', value: stockDistribution.out_of_stock || 0, color: '#EF4444' },
  ];

  const stockAgeData = [
    { name: 'Fresh (< 7 days)', value: stockAge.fresh || 0, color: '#10B981' },
    { name: 'Recent (7-30 days)', value: stockAge.recent || 0, color: '#3B82F6' },
    { name: 'Aging (30-90 days)', value: stockAge.aging || 0, color: '#F59E0B' },
    { name: 'Old (> 90 days)', value: stockAge.old || 0, color: '#EF4444' },
  ];

  const tabs = [
    { id: 'overview', label: 'Overview', icon: BarChart3 },
    { id: 'manage', label: 'Stock Management', icon: Edit3 },
    { id: 'stock', label: 'Stock Status', icon: Package },
    { id: 'sales', label: 'Sales Analysis', icon: TrendingUp },
    { id: 'movements', label: 'Stock Movements', icon: RefreshCw },
  ];

  return (
    <AdminLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Inventory Management</h1>
            <p className="text-gray-600 mt-1">Track stock levels, sales trends, and inventory analytics</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={fetchInventoryData}
              disabled={refreshing}
              className="btn btn-secondary flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <button className="btn btn-primary flex items-center gap-2">
              <Download className="w-4 h-4" />
              Export Report
            </button>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="card bg-gradient-to-br from-blue-500 to-blue-600 text-white">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-blue-100 text-sm">Total Products</p>
                <p className="text-3xl font-bold mt-1">{formatNumber(summary.total_products)}</p>
                <p className="text-blue-100 text-sm mt-2">{formatNumber(summary.total_units)} units in stock</p>
              </div>
              <div className="p-3 bg-white/20 rounded-lg">
                <Package className="w-8 h-8" />
              </div>
            </div>
          </div>

          <div className="card bg-gradient-to-br from-green-500 to-green-600 text-white">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-green-100 text-sm">Stock Value</p>
                <p className="text-3xl font-bold mt-1">{formatCurrency(summary.stock_value)}</p>
                <p className="text-green-100 text-sm mt-2">
                  Turnover: {summary.turnover_rate || 0}x/year
                </p>
              </div>
              <div className="p-3 bg-white/20 rounded-lg">
                <DollarSign className="w-8 h-8" />
              </div>
            </div>
          </div>

          <div className="card bg-gradient-to-br from-yellow-500 to-yellow-600 text-white">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-yellow-100 text-sm">Low Stock Items</p>
                <p className="text-3xl font-bold mt-1">{formatNumber(summary.low_stock)}</p>
                <p className="text-yellow-100 text-sm mt-2">Needs attention</p>
              </div>
              <div className="p-3 bg-white/20 rounded-lg">
                <AlertTriangle className="w-8 h-8" />
              </div>
            </div>
          </div>

          <div className="card bg-gradient-to-br from-red-500 to-red-600 text-white">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-red-100 text-sm">Out of Stock</p>
                <p className="text-3xl font-bold mt-1">{formatNumber(summary.out_of_stock)}</p>
                <p className="text-red-100 text-sm mt-2">Urgent restock needed</p>
              </div>
              <div className="p-3 bg-white/20 rounded-lg">
                <PackageX className="w-8 h-8" />
              </div>
            </div>
          </div>
        </div>

        {/* Sales Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900">Last 7 Days</h3>
              <span className="badge badge-primary">Weekly</span>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-gray-900">{formatNumber(salesStats.last_7_days?.orders)}</p>
                <p className="text-sm text-gray-500">Orders</p>
              </div>
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-gray-900">{formatNumber(salesStats.last_7_days?.units_sold)}</p>
                <p className="text-sm text-gray-500">Units Sold</p>
              </div>
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-green-600">{formatCurrency(salesStats.last_7_days?.revenue)}</p>
                <p className="text-sm text-gray-500">Revenue</p>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900">Last 30 Days</h3>
              <span className="badge badge-secondary">Monthly</span>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-gray-900">{formatNumber(salesStats.last_30_days?.orders)}</p>
                <p className="text-sm text-gray-500">Orders</p>
              </div>
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-gray-900">{formatNumber(salesStats.last_30_days?.units_sold)}</p>
                <p className="text-sm text-gray-500">Units Sold</p>
              </div>
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-green-600">{formatCurrency(salesStats.last_30_days?.revenue)}</p>
                <p className="text-sm text-gray-500">Revenue</p>
              </div>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200">
          <nav className="flex space-x-8">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${activeTab === tab.id
                    ? 'border-primary text-primary'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                    }`}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Tab Content */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Stock Status Pie Chart */}
              <div className="card">
                <h3 className="font-semibold text-gray-900 mb-4">Stock Status Distribution</h3>
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={stockStatusData}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={100}
                        paddingAngle={5}
                        dataKey="value"
                        label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                      >
                        {stockStatusData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value) => formatNumber(value)} />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Category Stock Bar Chart */}
              <div className="card">
                <h3 className="font-semibold text-gray-900 mb-4">Stock by Category</h3>
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={categoryStock.slice(0, 8)} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" />
                      <YAxis dataKey="category_name" type="category" width={100} tick={{ fontSize: 12 }} />
                      <Tooltip formatter={(value) => formatNumber(value)} />
                      <Bar dataKey="total_stock" fill="#3B82F6" name="Stock Units" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            {/* Daily Sales Trend */}
            <div className="card">
              <h3 className="font-semibold text-gray-900 mb-4">Daily Sales Trend (Last 30 Days)</h3>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={dailySales}>
                    <defs>
                      <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10B981" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="colorItems" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 11 }}
                      tickFormatter={(value) => value ? new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : ''}
                    />
                    <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
                    <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} />
                    <Tooltip
                      formatter={(value, name) => [
                        name === 'revenue' ? formatCurrency(value) : formatNumber(value),
                        name === 'revenue' ? 'Revenue' : 'Items Sold'
                      ]}
                      labelFormatter={(label) => label ? new Date(label).toLocaleDateString() : ''}
                    />
                    <Legend />
                    <Area
                      yAxisId="left"
                      type="monotone"
                      dataKey="revenue"
                      stroke="#10B981"
                      fillOpacity={1}
                      fill="url(#colorRevenue)"
                      name="Revenue"
                    />
                    <Area
                      yAxisId="right"
                      type="monotone"
                      dataKey="items"
                      stroke="#3B82F6"
                      fillOpacity={1}
                      fill="url(#colorItems)"
                      name="Items Sold"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Top Selling & Slow Moving */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Top Selling Products */}
              <div className="card">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold text-gray-900">Top Selling Products</h3>
                  <span className="text-sm text-gray-500">Last 30 days</span>
                </div>
                <div className="space-y-3">
                  {topSelling.length > 0 ? topSelling.slice(0, 5).map((product, index) => (
                    <div key={product.product_id} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                      <span className="w-8 h-8 flex items-center justify-center bg-primary text-white rounded-full text-sm font-bold">
                        {index + 1}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-900 truncate">{product.product_name}</p>
                        <p className="text-sm text-gray-500">SKU: {product.product_sku}</p>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold text-gray-900">{formatNumber(product.total_sold)} sold</p>
                        <p className="text-sm text-green-600">{formatCurrency(product.total_revenue)}</p>
                      </div>
                    </div>
                  )) : (
                    <p className="text-gray-500 text-center py-8">No sales data available</p>
                  )}
                </div>
              </div>

              {/* Slow Moving Products */}
              <div className="card">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold text-gray-900">Slow Moving Products</h3>
                  <span className="text-sm text-gray-500">No sales in 30 days</span>
                </div>
                <div className="space-y-3">
                  {slowMoving.length > 0 ? slowMoving.slice(0, 5).map((product) => (
                    <div key={product.id} className="flex items-center gap-3 p-3 bg-yellow-50 rounded-lg border border-yellow-100">
                      <div className="p-2 bg-yellow-100 rounded-lg">
                        <Clock className="w-5 h-5 text-yellow-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-900 truncate">{product.name}</p>
                        <p className="text-sm text-gray-500">SKU: {product.sku}</p>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold text-gray-900">{formatNumber(product.stock_quantity)} in stock</p>
                        <p className="text-sm text-yellow-600">Value: {formatCurrency(product.value)}</p>
                      </div>
                    </div>
                  )) : (
                    <p className="text-gray-500 text-center py-8">All products have recent sales!</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'manage' && (
          <div className="space-y-4">
            {/* Search & Filter Bar */}
            <div className="card p-4">
              <div className="flex flex-col sm:flex-row gap-3">
                <div className="flex-1 relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Search by product name, SKU, or barcode..."
                    value={stockSearch}
                    onChange={(e) => setStockSearch(e.target.value)}
                    className="input pl-10 w-full"
                  />
                </div>
                <select
                  value={stockFilter}
                  onChange={(e) => setStockFilter(e.target.value)}
                  className="input w-auto min-w-[160px]"
                >
                  <option value="">All Stock Status</option>
                  <option value="in_stock">In Stock</option>
                  <option value="low_stock">Low Stock</option>
                  <option value="out_of_stock">Out of Stock</option>
                </select>
              </div>
            </div>

            {/* Inventory Table */}
            <div className="card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                      <th className="text-left py-3 px-4 text-xs font-semibold text-gray-600 uppercase w-8"></th>
                      <th className="text-left py-3 px-4 text-xs font-semibold text-gray-600 uppercase">Product / Variant</th>
                      <th className="text-left py-3 px-4 text-xs font-semibold text-gray-600 uppercase">SKU</th>
                      <th className="text-left py-3 px-4 text-xs font-semibold text-gray-600 uppercase">Category</th>
                      <th className="text-right py-3 px-4 text-xs font-semibold text-gray-600 uppercase">Price</th>
                      <th className="text-center py-3 px-4 text-xs font-semibold text-gray-600 uppercase">Stock</th>
                      <th className="text-center py-3 px-4 text-xs font-semibold text-gray-600 uppercase">Status</th>
                      <th className="text-center py-3 px-4 text-xs font-semibold text-gray-600 uppercase">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inventoryLoading || inventoryRefreshing ? (
                      [...Array(8)].map((_, i) => (
                        <tr key={i} className="border-b border-gray-100">
                          <td colSpan={8} className="py-4 px-4">
                            <div className="h-5 bg-gray-100 rounded animate-pulse" />
                          </td>
                        </tr>
                      ))
                    ) : inventoryItems.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="text-center py-12 text-gray-500">
                          No products found
                        </td>
                      </tr>
                    ) : (
                      inventoryItems.map((product) => {
                        const isExpanded = expandedProducts[product.id];
                        const badge = getStockBadge(product.total_stock, product.low_stock_threshold);
                        return (
                          <>{/* Product Row */}
                            <tr key={product.id} className="border-b border-gray-100 hover:bg-gray-50">
                              <td className="py-3 px-4">
                                {product.has_variants ? (
                                  <button onClick={() => toggleExpand(product.id)} className="p-1 hover:bg-gray-200 rounded">
                                    {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                                  </button>
                                ) : <span className="w-6" />}
                              </td>
                              <td className="py-3 px-4">
                                <p className="font-medium text-gray-900">{product.name}</p>
                                {product.has_variants && (
                                  <p className="text-xs text-primary-600 mt-0.5">{product.variants.length} variant{product.variants.length > 1 ? 's' : ''}</p>
                                )}
                              </td>
                              <td className="py-3 px-4 text-sm text-gray-600 font-mono">{product.sku || '—'}</td>
                              <td className="py-3 px-4 text-sm text-gray-600">{product.category || '—'}</td>
                              <td className="py-3 px-4 text-right text-sm font-medium">৳{parseFloat(product.price).toLocaleString()}</td>
                              <td className="py-3 px-4 text-center">
                                <span className={`font-bold text-lg ${product.total_stock === 0 ? 'text-red-600' : product.total_stock <= product.low_stock_threshold ? 'text-yellow-600' : 'text-gray-900'}`}>
                                  {product.total_stock}
                                </span>
                              </td>
                              <td className="py-3 px-4 text-center">
                                <span className={`px-2 py-1 rounded-full text-xs font-medium ${badge.cls}`}>
                                  {badge.label}
                                </span>
                              </td>
                              <td className="py-3 px-4 text-center">
                                {!product.has_variants && (
                                  <button
                                    onClick={() => openStockModal('product', product.id, product.id, product.name, product.stock_quantity)}
                                    className="px-3 py-1.5 bg-primary-50 text-primary-700 hover:bg-primary-100 rounded-lg text-xs font-medium transition-colors"
                                  >
                                    Adjust Stock
                                  </button>
                                )}
                              </td>
                            </tr>
                            {/* Variant Rows */}
                            {product.has_variants && isExpanded && product.variants.map((variant) => {
                              const vLabel = [variant.size, variant.color].filter(Boolean).join(' / ') || 'Default';
                              const vBadge = getStockBadge(variant.stock_quantity, variant.low_stock_threshold ?? product.low_stock_threshold);
                              return (
                                <tr key={variant.id} className="border-b border-gray-50 bg-blue-50/30">
                                  <td className="py-2.5 px-4"></td>
                                  <td className="py-2.5 px-4 pl-12">
                                    <div className="flex items-center gap-2">
                                      <span className="w-2 h-2 bg-primary-400 rounded-full" />
                                      <span className="text-sm font-medium text-gray-800">{vLabel}</span>
                                    </div>
                                  </td>
                                  <td className="py-2.5 px-4 text-sm text-gray-500 font-mono">{variant.sku}</td>
                                  <td className="py-2.5 px-4 text-xs text-gray-400">
                                    {variant.barcode || '—'}
                                  </td>
                                  <td className="py-2.5 px-4 text-right text-sm text-gray-700">৳{parseFloat(variant.price).toLocaleString()}</td>
                                  <td className="py-2.5 px-4 text-center">
                                    <span className={`font-bold ${variant.stock_quantity === 0 ? 'text-red-600' : 'text-gray-900'}`}>
                                      {variant.stock_quantity}
                                    </span>
                                  </td>
                                  <td className="py-2.5 px-4 text-center">
                                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${vBadge.cls}`}>
                                      {vBadge.label}
                                    </span>
                                  </td>
                                  <td className="py-2.5 px-4 text-center">
                                    <button
                                      onClick={() => openStockModal('variant', variant.id, product.id, `${product.name} (${vLabel})`, variant.stock_quantity)}
                                      className="px-3 py-1.5 bg-primary-50 text-primary-700 hover:bg-primary-100 rounded-lg text-xs font-medium transition-colors"
                                    >
                                      Adjust
                                    </button>
                                  </td>
                                </tr>
                              );
                            })}
                          </>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
              {inventoryItems.length > 0 && (
                <div className="p-4 border-t bg-gray-50 text-sm text-gray-500">
                  Showing {inventoryItems.length} product{inventoryItems.length !== 1 ? 's' : ''}
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'stock' && (
          <div className="space-y-6">
            {/* Stock Age Distribution */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="card">
                <h3 className="font-semibold text-gray-900 mb-4">Stock Age Distribution</h3>
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={stockAgeData}
                        cx="50%"
                        cy="50%"
                        outerRadius={100}
                        dataKey="value"
                        label={({ name, value }) => `${name}: ${value}`}
                      >
                        {stockAgeData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="card">
                <h3 className="font-semibold text-gray-900 mb-4">Category Stock Value</h3>
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={categoryStock.slice(0, 6)}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="category_name" tick={{ fontSize: 11 }} />
                      <YAxis tickFormatter={(value) => `৳${(value / 1000).toFixed(0)}k`} />
                      <Tooltip formatter={(value) => formatCurrency(value)} />
                      <Bar dataKey="stock_value" fill="#8B5CF6" name="Stock Value" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            {/* Low Stock Alert Table */}
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-gray-900">Low Stock Alerts</h3>
                <span className="badge badge-warning">{lowStock.length} items need attention</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">Product</th>
                      <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">SKU</th>
                      <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">Category</th>
                      <th className="text-center py-3 px-4 text-sm font-medium text-gray-600">Current Stock</th>
                      <th className="text-center py-3 px-4 text-sm font-medium text-gray-600">Threshold</th>
                      <th className="text-right py-3 px-4 text-sm font-medium text-gray-600">Value</th>
                      <th className="text-center py-3 px-4 text-sm font-medium text-gray-600">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lowStock.map((product) => (
                      <tr key={product.id} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="py-3 px-4">
                          <p className="font-medium text-gray-900">{product.name}</p>
                        </td>
                        <td className="py-3 px-4 text-sm text-gray-600">{product.sku}</td>
                        <td className="py-3 px-4 text-sm text-gray-600">{product.category || 'N/A'}</td>
                        <td className="py-3 px-4 text-center">
                          <span className={`font-bold ${product.stock_quantity === 0 ? 'text-red-600' : 'text-yellow-600'}`}>
                            {product.stock_quantity}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-center text-gray-600">{product.threshold}</td>
                        <td className="py-3 px-4 text-right text-gray-900">{formatCurrency(product.value)}</td>
                        <td className="py-3 px-4 text-center">
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${product.stock_quantity === 0
                            ? 'bg-red-100 text-red-700'
                            : 'bg-yellow-100 text-yellow-700'
                            }`}>
                            {product.stock_quantity === 0 ? 'Out of Stock' : 'Low Stock'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {lowStock.length === 0 && (
                  <p className="text-gray-500 text-center py-8">All products are well-stocked!</p>
                )}
              </div>
            </div>

            {/* Category Stock Details */}
            <div className="card">
              <h3 className="font-semibold text-gray-900 mb-4">Category-wise Stock Details</h3>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">Category</th>
                      <th className="text-center py-3 px-4 text-sm font-medium text-gray-600">Products</th>
                      <th className="text-center py-3 px-4 text-sm font-medium text-gray-600">Total Stock</th>
                      <th className="text-right py-3 px-4 text-sm font-medium text-gray-600">Stock Value</th>
                      <th className="text-center py-3 px-4 text-sm font-medium text-gray-600">Low Stock</th>
                      <th className="text-center py-3 px-4 text-sm font-medium text-gray-600">Out of Stock</th>
                      <th className="text-center py-3 px-4 text-sm font-medium text-gray-600">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {categoryStock.map((category) => (
                      <tr key={category.category_id} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="py-3 px-4 font-medium text-gray-900">{category.category_name}</td>
                        <td className="py-3 px-4 text-center text-gray-600">{category.product_count}</td>
                        <td className="py-3 px-4 text-center font-semibold text-gray-900">{formatNumber(category.total_stock)}</td>
                        <td className="py-3 px-4 text-right text-green-600 font-medium">{formatCurrency(category.stock_value)}</td>
                        <td className="py-3 px-4 text-center">
                          {category.low_stock_count > 0 ? (
                            <span className="px-2 py-1 bg-yellow-100 text-yellow-700 rounded-full text-xs font-medium">
                              {category.low_stock_count}
                            </span>
                          ) : (
                            <span className="text-gray-400">-</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-center">
                          {category.out_of_stock_count > 0 ? (
                            <span className="px-2 py-1 bg-red-100 text-red-700 rounded-full text-xs font-medium">
                              {category.out_of_stock_count}
                            </span>
                          ) : (
                            <span className="text-gray-400">-</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-center">
                          <button
                            onClick={() => openCategoryDetail(category)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-primary-50 text-primary-700 hover:bg-primary-100 rounded-lg text-xs font-medium transition-colors"
                          >
                            <Eye className="w-3.5 h-3.5" />
                            Details
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'sales' && (
          <div className="space-y-6">
            {/* Weekly Sales Chart */}
            <div className="card">
              <h3 className="font-semibold text-gray-900 mb-4">Weekly Sales Trend (Last 90 Days)</h3>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={weeklySales}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="week"
                      tick={{ fontSize: 11 }}
                      tickFormatter={(value) => value ? new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : ''}
                    />
                    <YAxis yAxisId="left" tickFormatter={(value) => `৳${(value / 1000).toFixed(0)}k`} />
                    <YAxis yAxisId="right" orientation="right" />
                    <Tooltip
                      formatter={(value, name) => [
                        name === 'Revenue' ? formatCurrency(value) : formatNumber(value),
                        name
                      ]}
                    />
                    <Legend />
                    <Bar yAxisId="right" dataKey="orders" fill="#3B82F6" name="Orders" radius={[4, 4, 0, 0]} />
                    <Line yAxisId="left" type="monotone" dataKey="revenue" stroke="#10B981" name="Revenue" strokeWidth={2} dot={{ r: 4 }} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Top Products Chart */}
            <div className="card">
              <h3 className="font-semibold text-gray-900 mb-4">Top 10 Products by Sales</h3>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={topSelling} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis
                      dataKey="product_name"
                      type="category"
                      width={150}
                      tick={{ fontSize: 11 }}
                      tickFormatter={(value) => value.length > 20 ? value.substring(0, 20) + '...' : value}
                    />
                    <Tooltip
                      formatter={(value, name) => [
                        name === 'total_revenue' ? formatCurrency(value) : formatNumber(value),
                        name === 'total_revenue' ? 'Revenue' : 'Units Sold'
                      ]}
                    />
                    <Legend />
                    <Bar dataKey="total_sold" fill="#3B82F6" name="Units Sold" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Top Products Table */}
            <div className="card">
              <h3 className="font-semibold text-gray-900 mb-4">Product Performance Details</h3>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">#</th>
                      <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">Product</th>
                      <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">SKU</th>
                      <th className="text-center py-3 px-4 text-sm font-medium text-gray-600">Units Sold</th>
                      <th className="text-right py-3 px-4 text-sm font-medium text-gray-600">Revenue</th>
                      <th className="text-center py-3 px-4 text-sm font-medium text-gray-600">Current Stock</th>
                      <th className="text-center py-3 px-4 text-sm font-medium text-gray-600">Stock Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topSelling.map((product, index) => (
                      <tr key={product.product_id} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="py-3 px-4">
                          <span className="w-6 h-6 flex items-center justify-center bg-primary text-white rounded-full text-xs font-bold">
                            {index + 1}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-medium text-gray-900">{product.product_name}</td>
                        <td className="py-3 px-4 text-sm text-gray-600">{product.product_sku}</td>
                        <td className="py-3 px-4 text-center font-semibold text-gray-900">{formatNumber(product.total_sold)}</td>
                        <td className="py-3 px-4 text-right text-green-600 font-medium">{formatCurrency(product.total_revenue)}</td>
                        <td className="py-3 px-4 text-center">{formatNumber(product.current_stock)}</td>
                        <td className="py-3 px-4 text-center">
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${product.current_stock === 0
                            ? 'bg-red-100 text-red-700'
                            : product.current_stock < 10
                              ? 'bg-yellow-100 text-yellow-700'
                              : 'bg-green-100 text-green-700'
                            }`}>
                            {product.current_stock === 0 ? 'Out of Stock' : product.current_stock < 10 ? 'Low' : 'In Stock'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {topSelling.length === 0 && (
                  <p className="text-gray-500 text-center py-8">No sales data available</p>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'movements' && (
          <div className="space-y-6">
            {/* Recent Stock Movements */}
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-gray-900">Recent Stock Movements</h3>
                <div className="flex items-center gap-2">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      placeholder="Search movements..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="pl-10 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                    />
                  </div>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">Date & Time</th>
                      <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">Product</th>
                      <th className="text-center py-3 px-4 text-sm font-medium text-gray-600">Type</th>
                      <th className="text-center py-3 px-4 text-sm font-medium text-gray-600">Quantity</th>
                      <th className="text-center py-3 px-4 text-sm font-medium text-gray-600">Previous</th>
                      <th className="text-center py-3 px-4 text-sm font-medium text-gray-600">New</th>
                      <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">Reason</th>
                      <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">By</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stockMovements
                      .filter(m =>
                        m.product_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                        m.product_sku?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                        m.variant_label?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                        m.variant_sku?.toLowerCase().includes(searchTerm.toLowerCase())
                      )
                      .map((movement) => (
                        <tr key={movement.id} className="border-b border-gray-100 hover:bg-gray-50">
                          <td className="py-3 px-4 text-sm text-gray-600">
                            {new Date(movement.created_at).toLocaleString()}
                          </td>
                          <td className="py-3 px-4">
                            <p className="font-medium text-gray-900">{movement.product_name}</p>
                            {movement.variant_label && (
                              <p className="text-xs text-primary-600 font-medium">{movement.variant_label}</p>
                            )}
                            <p className="text-xs text-gray-500">SKU: {movement.variant_sku || movement.product_sku}</p>
                          </td>
                          <td className="py-3 px-4 text-center">
                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${movement.movement_type === 'in' || movement.movement_type === 'restock'
                              ? 'bg-green-100 text-green-700'
                              : movement.movement_type === 'out' || movement.movement_type === 'sale'
                                ? 'bg-blue-100 text-blue-700'
                                : movement.movement_type === 'adjustment'
                                  ? 'bg-yellow-100 text-yellow-700'
                                  : 'bg-gray-100 text-gray-700'
                              }`}>
                              {movement.movement_type}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-center">
                            <span className={`font-semibold ${movement.quantity > 0 ? 'text-green-600' : 'text-red-600'
                              }`}>
                              {movement.quantity > 0 ? '+' : ''}{movement.quantity}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-center text-gray-600">{movement.previous_stock}</td>
                          <td className="py-3 px-4 text-center font-semibold text-gray-900">{movement.new_stock}</td>
                          <td className="py-3 px-4 text-sm text-gray-600">
                            <p>{movement.reason || '-'}</p>
                            {movement.note && <p className="text-xs text-gray-400 mt-0.5">{movement.note}</p>}
                          </td>
                          <td className="py-3 px-4 text-sm text-gray-600">{movement.created_by || 'System'}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
                {stockMovements.length === 0 && (
                  <p className="text-gray-500 text-center py-8">No stock movements recorded yet</p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Category Detail Modal */}
      {categoryDetail && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setCategoryDetail(null)}>
          <div
            className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="p-6 border-b bg-gradient-to-r from-primary-50 to-blue-50 rounded-t-2xl">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold text-gray-900">{categoryDetail.category_name}</h2>
                  <p className="text-sm text-gray-500 mt-1">Category Stock Overview</p>
                </div>
                <button onClick={() => setCategoryDetail(null)} className="p-2 hover:bg-white/60 rounded-xl transition-colors">
                  <X className="w-5 h-5 text-gray-600" />
                </button>
              </div>

              {/* Summary Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
                <div className="bg-white/80 backdrop-blur rounded-xl p-3 text-center">
                  <p className="text-xs text-gray-500 font-medium">Products</p>
                  <p className="text-xl font-bold text-gray-900">{categoryDetail.product_count}</p>
                </div>
                <div className="bg-white/80 backdrop-blur rounded-xl p-3 text-center">
                  <p className="text-xs text-gray-500 font-medium">Total Stock</p>
                  <p className="text-xl font-bold text-gray-900">{formatNumber(categoryDetail.total_stock)}</p>
                </div>
                <div className="bg-white/80 backdrop-blur rounded-xl p-3 text-center">
                  <p className="text-xs text-gray-500 font-medium">Stock Value</p>
                  <p className="text-xl font-bold text-green-600">{formatCurrency(categoryDetail.stock_value)}</p>
                </div>
                <div className="bg-white/80 backdrop-blur rounded-xl p-3 text-center">
                  <p className="text-xs text-gray-500 font-medium">Alerts</p>
                  <div className="flex items-center justify-center gap-2 mt-0.5">
                    {categoryDetail.low_stock_count > 0 && (
                      <span className="px-1.5 py-0.5 bg-yellow-100 text-yellow-700 rounded text-xs font-bold">{categoryDetail.low_stock_count} Low</span>
                    )}
                    {categoryDetail.out_of_stock_count > 0 && (
                      <span className="px-1.5 py-0.5 bg-red-100 text-red-700 rounded text-xs font-bold">{categoryDetail.out_of_stock_count} Out</span>
                    )}
                    {!categoryDetail.low_stock_count && !categoryDetail.out_of_stock_count && (
                      <span className="text-green-600 font-bold text-sm">All Good</span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Modal Body — Product List */}
            <div className="flex-1 overflow-y-auto p-6">
              {categoryItemsLoading ? (
                <div className="space-y-3">
                  {[...Array(4)].map((_, i) => (
                    <div key={i} className="h-16 bg-gray-100 rounded-xl animate-pulse" />
                  ))}
                </div>
              ) : (categoryItemsData?.items || []).length === 0 ? (
                <div className="text-center py-12 text-gray-400">
                  <Package className="w-12 h-12 mx-auto mb-3 opacity-40" />
                  <p className="text-sm">No products found in this category</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {(categoryItemsData?.items || []).map((product) => {
                    const isExpanded = catExpandedProducts[product.id];
                    const badge = getStockBadge(product.total_stock, product.low_stock_threshold);
                    return (
                      <div key={product.id} className="border border-gray-200 rounded-xl overflow-hidden hover:border-gray-300 transition-colors">
                        {/* Product Row */}
                        <div
                          className={`flex items-center gap-4 p-4 cursor-pointer ${product.has_variants ? 'hover:bg-gray-50' : ''}`}
                          onClick={() => product.has_variants && toggleCatExpand(product.id)}
                        >
                          {/* Expand indicator */}
                          <div className="w-5 flex-shrink-0">
                            {product.has_variants && (
                              isExpanded
                                ? <ChevronDown className="w-4 h-4 text-gray-500" />
                                : <ChevronRight className="w-4 h-4 text-gray-400" />
                            )}
                          </div>

                          {/* Product info */}
                          <div className="flex-1 min-w-0">
                            <p className="font-semibold text-gray-900 truncate">{product.name}</p>
                            <div className="flex items-center gap-3 mt-0.5">
                              <span className="text-xs text-gray-400 font-mono">{product.sku || '—'}</span>
                              {product.has_variants && (
                                <span className="text-xs text-primary-600 font-medium">{product.variants.length} variant{product.variants.length > 1 ? 's' : ''}</span>
                              )}
                            </div>
                          </div>

                          {/* Price */}
                          <div className="text-right flex-shrink-0">
                            <p className="text-sm font-medium text-gray-900">৳{parseFloat(product.price).toLocaleString()}</p>
                            <p className="text-xs text-gray-400">Price</p>
                          </div>

                          {/* Stock */}
                          <div className="text-center flex-shrink-0 w-20">
                            <p className={`text-lg font-bold ${product.total_stock === 0 ? 'text-red-600' : product.total_stock <= product.low_stock_threshold ? 'text-yellow-600' : 'text-gray-900'}`}>
                              {product.total_stock}
                            </p>
                            <p className="text-xs text-gray-400">Stock</p>
                          </div>

                          {/* Status Badge */}
                          <div className="flex-shrink-0">
                            <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${badge.cls}`}>
                              {badge.label}
                            </span>
                          </div>
                        </div>

                        {/* Variant Rows */}
                        {product.has_variants && isExpanded && (
                          <div className="border-t bg-gradient-to-b from-blue-50/40 to-transparent">
                            <div className="px-4 py-2 border-b border-blue-100/60">
                              <div className="grid grid-cols-12 gap-2 text-xs font-semibold text-gray-500 uppercase">
                                <div className="col-span-3">Variant</div>
                                <div className="col-span-2">SKU</div>
                                <div className="col-span-2">Barcode</div>
                                <div className="col-span-2 text-right">Price</div>
                                <div className="col-span-1 text-center">Stock</div>
                                <div className="col-span-2 text-center">Status</div>
                              </div>
                            </div>
                            {product.variants.map((variant) => {
                              const vLabel = [variant.size, variant.color].filter(Boolean).join(' / ') || 'Default';
                              const vBadge = getStockBadge(variant.stock_quantity, variant.low_stock_threshold ?? product.low_stock_threshold);
                              return (
                                <div key={variant.id} className="px-4 py-2.5 border-b border-gray-100/60 last:border-b-0 hover:bg-blue-50/30 transition-colors">
                                  <div className="grid grid-cols-12 gap-2 items-center text-sm">
                                    <div className="col-span-3 flex items-center gap-2">
                                      <span className="w-1.5 h-1.5 bg-primary-400 rounded-full flex-shrink-0" />
                                      <span className="font-medium text-gray-800 truncate">{vLabel}</span>
                                    </div>
                                    <div className="col-span-2 text-gray-500 font-mono text-xs truncate">{variant.sku || '—'}</div>
                                    <div className="col-span-2 text-gray-400 font-mono text-xs truncate">{variant.barcode || '—'}</div>
                                    <div className="col-span-2 text-right text-gray-700">৳{parseFloat(variant.price).toLocaleString()}</div>
                                    <div className="col-span-1 text-center">
                                      <span className={`font-bold ${variant.stock_quantity === 0 ? 'text-red-600' : 'text-gray-900'}`}>
                                        {variant.stock_quantity}
                                      </span>
                                    </div>
                                    <div className="col-span-2 text-center">
                                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${vBadge.cls}`}>
                                        {vBadge.label}
                                      </span>
                                    </div>
                                  </div>
                                </div>
                              );
                            })}
                            {/* Variant Summary */}
                            <div className="px-4 py-2.5 bg-gray-50/80 border-t">
                              <div className="grid grid-cols-12 gap-2 items-center text-xs font-semibold text-gray-600">
                                <div className="col-span-7">Total across {product.variants.length} variants</div>
                                <div className="col-span-2 text-right">
                                  ৳{product.variants.reduce((sum, v) => sum + parseFloat(v.price) * v.stock_quantity, 0).toLocaleString()}
                                </div>
                                <div className="col-span-1 text-center font-bold text-gray-900">{product.total_stock}</div>
                                <div className="col-span-2"></div>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t bg-gray-50 rounded-b-2xl flex items-center justify-between">
              <p className="text-xs text-gray-400">
                {(categoryItemsData?.items || []).length} product{(categoryItemsData?.items || []).length !== 1 ? 's' : ''} in this category
              </p>
              <button
                onClick={() => setCategoryDetail(null)}
                className="btn btn-secondary text-sm"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Stock Adjustment Modal */}
      {stockModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
            <div className="p-5 border-b flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Adjust Stock</h2>
                <p className="text-sm text-gray-500 mt-0.5">{stockModal.name}</p>
              </div>
              <button onClick={() => setStockModal(null)} className="p-2 hover:bg-gray-100 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleStockUpdate} className="p-5 space-y-4">
              <div className="p-3 bg-gray-50 rounded-lg text-center">
                <p className="text-sm text-gray-500">Current Stock</p>
                <p className="text-3xl font-bold text-gray-900">{stockModal.currentStock}</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Operation</label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { value: 'add', label: 'Add Stock', icon: Plus, cls: 'border-green-500 bg-green-50 text-green-700' },
                    { value: 'subtract', label: 'Remove', icon: Minus, cls: 'border-red-500 bg-red-50 text-red-700' },
                    { value: 'set', label: 'Set To', icon: Edit3, cls: 'border-blue-500 bg-blue-50 text-blue-700' },
                  ].map(op => {
                    const Icon = op.icon;
                    const isActive = stockForm.operation === op.value;
                    return (
                      <button
                        key={op.value}
                        type="button"
                        onClick={() => setStockForm({ ...stockForm, operation: op.value })}
                        className={`flex flex-col items-center gap-1 p-3 rounded-xl border-2 transition-all text-sm font-medium ${isActive ? op.cls : 'border-gray-200 text-gray-600 hover:border-gray-300'
                          }`}
                      >
                        <Icon className="w-4 h-4" />
                        {op.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Quantity</label>
                <input
                  type="number"
                  value={stockForm.quantity}
                  onChange={(e) => setStockForm({ ...stockForm, quantity: e.target.value })}
                  className="input text-lg font-semibold text-center"
                  min="1"
                  placeholder="Enter quantity"
                  required
                  autoFocus
                />
                {stockForm.quantity && (
                  <p className="text-sm text-gray-500 mt-1 text-center">
                    New stock will be:{' '}
                    <span className="font-bold text-gray-900">
                      {stockForm.operation === 'add'
                        ? stockModal.currentStock + parseInt(stockForm.quantity || 0)
                        : stockForm.operation === 'subtract'
                          ? Math.max(0, stockModal.currentStock - parseInt(stockForm.quantity || 0))
                          : parseInt(stockForm.quantity || 0)
                      }
                    </span>
                  </p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Reason</label>
                <select
                  value={stockForm.reason}
                  onChange={(e) => setStockForm({ ...stockForm, reason: e.target.value })}
                  className="input"
                >
                  {REASON_OPTIONS.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Note (optional)</label>
                <textarea
                  value={stockForm.note}
                  onChange={(e) => setStockForm({ ...stockForm, note: e.target.value })}
                  className="input"
                  rows={2}
                  placeholder="e.g. Received from supplier XYZ"
                />
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setStockModal(null)}
                  className="flex-1 btn btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updatingProduct || updatingVariant}
                  className="flex-1 btn btn-primary"
                >
                  {updatingProduct || updatingVariant ? 'Updating...' : 'Update Stock'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}
