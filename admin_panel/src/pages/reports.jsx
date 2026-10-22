import React, { useState, useEffect, useRef } from 'react';
import {
  Calendar, Download, TrendingUp, Package,
  DollarSign, ShoppingCart, BarChart3, FileText,
  ChevronDown, ChevronRight, AlertTriangle, Layers,
  Printer, Filter, Search
} from 'lucide-react';
import AdminLayout from '@/components/layout/AdminLayout';
import { useGetSalesReportMutation, useGetStockReportQuery } from '@/store/api/reportsApi';

function StatCard({ icon: Icon, label, value, color = 'blue', sub }) {
  const colors = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    purple: 'bg-purple-50 text-purple-600',
    yellow: 'bg-amber-50 text-amber-600',
    red: 'bg-red-50 text-red-600',
    cyan: 'bg-cyan-50 text-cyan-600',
    indigo: 'bg-indigo-50 text-indigo-600',
  };
  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">{label}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1 truncate">{value}</p>
          {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
        </div>
        <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${colors[color]} flex-shrink-0 ml-3`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </div>
  );
}

function StockProductRow({ product }) {
  const [expanded, setExpanded] = useState(false);
  const stockStatus = product.stock_quantity === 0
    ? { label: 'Out', cls: 'bg-red-100 text-red-700' }
    : product.stock_quantity <= product.low_stock_threshold
      ? { label: 'Low', cls: 'bg-amber-100 text-amber-700' }
      : { label: 'OK', cls: 'bg-green-100 text-green-700' };

  return (
    <>
      <tr className="border-b border-gray-100 hover:bg-gray-50/50 transition-colors">
        <td className="py-3 px-4">
          {product.has_variants ? (
            <button onClick={() => setExpanded(!expanded)} className="flex items-center gap-1 text-gray-500 hover:text-gray-700">
              {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </button>
          ) : <span className="w-4 inline-block" />}
        </td>
        <td className="py-3 px-3">
          <div>
            <p className="font-medium text-gray-900 text-sm">{product.name}</p>
            <p className="text-xs text-gray-400">{product.category}</p>
          </div>
        </td>
        <td className="py-3 px-3 font-mono text-xs text-gray-500">{product.sku}</td>
        <td className="py-3 px-3 text-sm">৳{product.price.toLocaleString()}</td>
        <td className="py-3 px-3">
          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${stockStatus.cls}`}>
            {product.stock_quantity}
          </span>
        </td>
        <td className="py-3 px-3 text-sm text-gray-500">
          {product.has_variants ? product.variants.length : '—'}
        </td>
        <td className="py-3 px-3 text-sm text-gray-500">
          {product.has_variants ? product.total_variant_stock : '—'}
        </td>
        <td className="py-3 px-3 text-sm font-medium">৳{product.stock_value.toLocaleString()}</td>
      </tr>
      {expanded && product.variants.map((v) => (
        <tr key={v.id} className="bg-gray-50/70 border-b border-gray-50">
          <td className="py-2 px-4" />
          <td className="py-2 px-3 pl-10">
            <p className="text-xs text-gray-600">
              {v.size && <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-gray-200 text-gray-700 mr-1 font-medium">{v.size}</span>}
              {v.color && <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-gray-200 text-gray-700 font-medium">{v.color}</span>}
            </p>
          </td>
          <td className="py-2 px-3 font-mono text-xs text-gray-400">{v.sku}</td>
          <td className="py-2 px-3 text-xs text-gray-500">৳{v.price.toLocaleString()}</td>
          <td className="py-2 px-3">
            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${v.stock_quantity === 0 ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-600'
              }`}>
              {v.stock_quantity}
            </span>
          </td>
          <td className="py-2 px-3" />
          <td className="py-2 px-3" />
          <td className="py-2 px-3 text-xs text-gray-500">৳{v.stock_value.toLocaleString()}</td>
        </tr>
      ))}
    </>
  );
}

export default function ReportsPage() {
  const [reportType, setReportType] = useState('sales');
  const [dateRange, setDateRange] = useState({
    start_date: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    end_date: new Date().toISOString().split('T')[0],
  });
  const [salesData, setSalesData] = useState(null);
  const [stockFilter, setStockFilter] = useState('all');
  const [stockSearch, setStockSearch] = useState('');
  const salesPrintRef = useRef();
  const stockPrintRef = useRef();

  const [getSalesReport, { isLoading: salesLoading }] = useGetSalesReportMutation();
  const { data: stockData, isLoading: stockLoading } = useGetStockReportQuery(undefined, {
    skip: reportType !== 'stock',
  });

  const loading = salesLoading || stockLoading;

  // CSV Download
  const downloadCSV = (type) => {
    let csvContent = '';
    const filename = `${type}_report_${dateRange.start_date}_to_${dateRange.end_date}.csv`;

    if (type === 'sales' && salesData) {
      csvContent = 'Sales Report\n';
      csvContent += `Date Range,${dateRange.start_date} to ${dateRange.end_date}\n\n`;
      csvContent += 'Summary\n';
      csvContent += `Total Orders,${salesData.summary?.total_orders || 0}\n`;
      csvContent += `Total Revenue,${salesData.summary?.total_revenue || 0}\n`;
      csvContent += `Items Sold,${salesData.summary?.total_items_sold || 0}\n`;
      csvContent += `Average Order Value,${salesData.summary?.average_order_value || 0}\n\n`;
      csvContent += 'Daily Sales\nDate,Orders,Items,Revenue\n';
      salesData.daily_sales?.forEach(day => {
        csvContent += `${day.date},${day.orders},${day.items},${day.revenue}\n`;
      });
      csvContent += '\nTop Products\nProduct,Quantity Sold,Revenue\n';
      salesData.top_products?.forEach(p => {
        csvContent += `"${p.product_name}",${p.total_sold},${p.total_revenue}\n`;
      });
      csvContent += '\nCategory Sales\nCategory,Orders,Revenue\n';
      salesData.category_sales?.forEach(c => {
        csvContent += `"${c.category_name}",${c.total_orders},${c.total_revenue}\n`;
      });
    } else if (type === 'stock' && stockData) {
      csvContent = 'Stock Report\n';
      csvContent += `Generated,${new Date().toISOString().split('T')[0]}\n\n`;
      csvContent += 'Summary\n';
      csvContent += `Total Products,${stockData.summary?.total_products || 0}\n`;
      csvContent += `In Stock,${stockData.summary?.in_stock || 0}\n`;
      csvContent += `Low Stock,${stockData.summary?.low_stock || 0}\n`;
      csvContent += `Out of Stock,${stockData.summary?.out_of_stock || 0}\n`;
      csvContent += `Total Units,${stockData.summary?.total_units || 0}\n`;
      csvContent += `Total Variants,${stockData.summary?.total_variants || 0}\n`;
      csvContent += `Total Stock Value,${stockData.summary?.total_stock_value || 0}\n\n`;
      csvContent += 'Product,SKU,Category,Price,Stock,Variants,Variant Stock,Stock Value\n';
      stockData.all_products?.forEach(p => {
        csvContent += `"${p.name}","${p.sku}","${p.category}",${p.price},${p.stock_quantity},${p.variants.length},${p.total_variant_stock},${p.stock_value}\n`;
        p.variants?.forEach(v => {
          csvContent += `"  ↳ ${v.size || ''} ${v.color || ''}","${v.sku}","",${v.price},${v.stock_quantity},,,"${v.stock_value}"\n`;
        });
      });
    }

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
  };

  // PDF via browser print
  const downloadPDF = (type) => {
    const ref = type === 'sales' ? salesPrintRef : stockPrintRef;
    const printWindow = window.open('', '_blank');
    printWindow.document.write(`
      <html><head><title>${type === 'sales' ? 'Sales' : 'Stock'} Report — Zzuhana</title>
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; color: #1a1a1a; padding: 32px; font-size: 12px; }
        h1 { font-size: 22px; font-weight: 800; letter-spacing: 1px; text-transform: uppercase; }
        h2 { font-size: 14px; font-weight: 700; margin: 20px 0 8px; color: #333; border-bottom: 2px solid #e5e5e5; padding-bottom: 4px; }
        .header { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 3px solid #1a1a1a; padding-bottom: 16px; margin-bottom: 20px; }
        .meta { font-size: 11px; color: #888; }
        .stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
        .stat-box { border: 1px solid #e5e5e5; border-radius: 8px; padding: 12px; text-align: center; }
        .stat-box .val { font-size: 20px; font-weight: 800; }
        .stat-box .lbl { font-size: 10px; text-transform: uppercase; color: #888; letter-spacing: 0.5px; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
        th { text-align: left; padding: 8px 6px; font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; color: #888; border-bottom: 2px solid #e5e5e5; }
        td { padding: 6px; font-size: 11px; border-bottom: 1px solid #f0f0f0; }
        .sub-row td { padding-left: 24px; color: #666; background: #fafafa; }
        .text-right { text-align: right; }
        .text-center { text-align: center; }
        .bold { font-weight: 700; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 600; }
        .badge-ok { background: #dcfce7; color: #166534; }
        .badge-low { background: #fef3c7; color: #92400e; }
        .badge-out { background: #fee2e2; color: #991b1b; }
        .footer { margin-top: 24px; padding-top: 12px; border-top: 1px solid #e5e5e5; display: flex; justify-content: space-between; font-size: 10px; color: #aaa; }
        @media print { body { padding: 16px; } }
      </style></head><body>${ref.current.innerHTML}
      <div class="footer"><span>Generated on ${new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })} by Zzuhana Admin</span><span>www.zzuhana.com</span></div>
      </body></html>
    `);
    printWindow.document.close();
    setTimeout(() => { printWindow.print(); }, 300);
  };

  const fetchSalesReport = async () => {
    try {
      const response = await getSalesReport(dateRange).unwrap();
      setSalesData(response);
    } catch (error) {
      console.error('Failed to fetch sales report:', error);
    }
  };

  useEffect(() => {
    if (reportType === 'sales') {
      fetchSalesReport();
    }
  }, [reportType]);

  // Filter stock products
  const filteredProducts = stockData?.all_products?.filter(p => {
    if (stockFilter === 'in_stock') return p.stock_quantity > p.low_stock_threshold;
    if (stockFilter === 'low_stock') return p.stock_quantity > 0 && p.stock_quantity <= p.low_stock_threshold;
    if (stockFilter === 'out_of_stock') return p.stock_quantity === 0;
    if (stockFilter === 'has_variants') return p.has_variants;
    return true;
  }).filter(p => {
    if (!stockSearch) return true;
    const s = stockSearch.toLowerCase();
    return p.name.toLowerCase().includes(s) || p.sku.toLowerCase().includes(s) || p.category.toLowerCase().includes(s);
  }) || [];

  return (
    <AdminLayout title="Reports">
      {/* Tab Selector */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex bg-gray-100 rounded-xl p-1 gap-1">
          <button
            onClick={() => setReportType('sales')}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all ${reportType === 'sales'
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
              }`}
          >
            <TrendingUp className="w-4 h-4" />
            Sales Report
          </button>
          <button
            onClick={() => setReportType('stock')}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all ${reportType === 'stock'
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
              }`}
          >
            <Package className="w-4 h-4" />
            Stock Report
          </button>
        </div>
      </div>

      {/* ============ SALES REPORT ============ */}
      {reportType === 'sales' && (
        <>
          {/* Toolbar */}
          <div className="bg-white rounded-xl border shadow-sm p-4 mb-6">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2 flex-1 min-w-[280px]">
                <Calendar className="w-4 h-4 text-gray-400 flex-shrink-0" />
                <input type="date" value={dateRange.start_date}
                  onChange={(e) => setDateRange({ ...dateRange, start_date: e.target.value })}
                  className="input w-auto text-sm" />
                <span className="text-gray-400 text-sm">to</span>
                <input type="date" value={dateRange.end_date}
                  onChange={(e) => setDateRange({ ...dateRange, end_date: e.target.value })}
                  className="input w-auto text-sm" />
              </div>
              <button onClick={fetchSalesReport} className="btn btn-primary text-sm">
                Generate
              </button>
              {salesData && (
                <div className="flex gap-2">
                  <button onClick={() => downloadCSV('sales')} className="btn btn-secondary text-sm">
                    <Download className="w-4 h-4 mr-1.5" />CSV
                  </button>
                  <button onClick={() => downloadPDF('sales')} className="btn btn-secondary text-sm">
                    <FileText className="w-4 h-4 mr-1.5" />PDF
                  </button>
                </div>
              )}
            </div>
          </div>

          {loading ? (
            <div className="animate-pulse space-y-4">
              <div className="grid grid-cols-4 gap-4">
                {[1, 2, 3, 4].map(i => <div key={i} className="h-24 bg-gray-200 rounded-xl" />)}
              </div>
            </div>
          ) : salesData && (
            <>
              {/* Summary */}
              <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                <StatCard icon={ShoppingCart} label="Total Orders" value={salesData.summary?.total_orders || 0} color="blue"
                  sub={`Online: ${salesData.summary?.online_orders || 0} · In-shop: ${salesData.summary?.in_shop_orders || 0}`} />
                <StatCard icon={DollarSign} label="Total Revenue" value={`৳${(salesData.summary?.total_revenue || 0).toLocaleString()}`} color="green" />
                <StatCard icon={Package} label="Items Sold" value={salesData.summary?.total_items_sold || 0} color="purple" />
                <StatCard icon={BarChart3} label="Avg. Order Value" value={`৳${Math.round(salesData.summary?.average_order_value || 0).toLocaleString()}`} color="yellow" />
              </div>

              <div className="grid lg:grid-cols-2 gap-6 mb-6">
                {/* Top Products */}
                <div className="bg-white rounded-xl border shadow-sm p-6">
                  <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-4">Top Selling Products</h3>
                  <div className="space-y-3">
                    {salesData.top_products?.slice(0, 8).map((product, index) => {
                      const maxRevenue = salesData.top_products[0]?.total_revenue || 1;
                      return (
                        <div key={product.product_id} className="flex items-center gap-3">
                          <span className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0 ${index < 3 ? 'bg-primary-100 text-primary-700' : 'bg-gray-100 text-gray-500'
                            }`}>{index + 1}</span>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-900 truncate">{product.product_name}</p>
                            <div className="w-full bg-gray-100 rounded-full h-1.5 mt-1">
                              <div className="bg-primary-500 h-1.5 rounded-full" style={{ width: `${(product.total_revenue / maxRevenue) * 100}%` }} />
                            </div>
                          </div>
                          <div className="text-right flex-shrink-0">
                            <p className="text-sm font-bold text-gray-900">৳{product.total_revenue?.toLocaleString()}</p>
                            <p className="text-xs text-gray-400">{product.total_sold} sold</p>
                          </div>
                        </div>
                      );
                    })}
                    {(!salesData.top_products || salesData.top_products.length === 0) && (
                      <p className="text-sm text-gray-400 text-center py-4">No sales data for this period</p>
                    )}
                  </div>
                </div>

                {/* Category Sales */}
                <div className="bg-white rounded-xl border shadow-sm p-6">
                  <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-4">Revenue by Category</h3>
                  <div className="space-y-3">
                    {salesData.category_sales?.map((cat) => {
                      const totalRev = salesData.summary?.total_revenue || 1;
                      const pct = ((cat.total_revenue / totalRev) * 100).toFixed(1);
                      return (
                        <div key={cat.category_id}>
                          <div className="flex items-center justify-between mb-1">
                            <p className="text-sm font-medium text-gray-700">{cat.category_name}</p>
                            <p className="text-sm font-bold text-gray-900">৳{cat.total_revenue?.toLocaleString()}</p>
                          </div>
                          <div className="flex items-center gap-2">
                            <div className="flex-1 bg-gray-100 rounded-full h-2">
                              <div className="bg-indigo-500 h-2 rounded-full transition-all" style={{ width: `${pct}%` }} />
                            </div>
                            <span className="text-xs text-gray-400 w-10 text-right">{pct}%</span>
                          </div>
                        </div>
                      );
                    })}
                    {(!salesData.category_sales || salesData.category_sales.length === 0) && (
                      <p className="text-sm text-gray-400 text-center py-4">No category data</p>
                    )}
                  </div>
                </div>
              </div>

              {/* Daily Sales */}
              <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
                <div className="px-6 py-4 border-b bg-gray-50/50">
                  <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider">Daily Sales Breakdown</h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b bg-gray-50/30">
                        <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Date</th>
                        <th className="text-right py-3 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Orders</th>
                        <th className="text-right py-3 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Items</th>
                        <th className="text-right py-3 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Revenue</th>
                      </tr>
                    </thead>
                    <tbody>
                      {salesData.daily_sales?.map((day) => (
                        <tr key={day.date} className="border-b border-gray-50 hover:bg-gray-50/50 transition-colors">
                          <td className="py-2.5 px-4 text-sm">{new Date(day.date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}</td>
                          <td className="py-2.5 px-4 text-sm text-right">{day.orders}</td>
                          <td className="py-2.5 px-4 text-sm text-right">{day.items}</td>
                          <td className="py-2.5 px-4 text-sm text-right font-semibold">৳{day.revenue?.toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                    {salesData.daily_sales?.length > 0 && (
                      <tfoot>
                        <tr className="bg-gray-50 font-semibold">
                          <td className="py-3 px-4 text-sm">Total</td>
                          <td className="py-3 px-4 text-sm text-right">{salesData.daily_sales.reduce((s, d) => s + d.orders, 0)}</td>
                          <td className="py-3 px-4 text-sm text-right">{salesData.daily_sales.reduce((s, d) => s + (d.items || 0), 0)}</td>
                          <td className="py-3 px-4 text-sm text-right">৳{salesData.daily_sales.reduce((s, d) => s + (d.revenue || 0), 0).toLocaleString()}</td>
                        </tr>
                      </tfoot>
                    )}
                  </table>
                </div>
              </div>
            </>
          )}

          {/* Sales Print Template (hidden) */}
          <div className="hidden">
            <div ref={salesPrintRef}>
              <div className="header">
                <div><h1>Zzuhana</h1><p className="meta">Sales Report</p></div>
                <div style={{ textAlign: 'right' }}><p className="bold">{dateRange.start_date} — {dateRange.end_date}</p></div>
              </div>
              {salesData && (
                <>
                  <div className="stat-grid">
                    <div className="stat-box"><div className="val">{salesData.summary?.total_orders || 0}</div><div className="lbl">Orders</div></div>
                    <div className="stat-box"><div className="val">৳{(salesData.summary?.total_revenue || 0).toLocaleString()}</div><div className="lbl">Revenue</div></div>
                    <div className="stat-box"><div className="val">{salesData.summary?.total_items_sold || 0}</div><div className="lbl">Items Sold</div></div>
                    <div className="stat-box"><div className="val">৳{Math.round(salesData.summary?.average_order_value || 0).toLocaleString()}</div><div className="lbl">Avg. Order</div></div>
                  </div>
                  <h2>Daily Sales</h2>
                  <table>
                    <thead><tr><th>Date</th><th className="text-right">Orders</th><th className="text-right">Items</th><th className="text-right">Revenue</th></tr></thead>
                    <tbody>
                      {salesData.daily_sales?.map(d => (
                        <tr key={d.date}><td>{d.date}</td><td className="text-right">{d.orders}</td><td className="text-right">{d.items}</td><td className="text-right bold">৳{d.revenue?.toLocaleString()}</td></tr>
                      ))}
                    </tbody>
                  </table>
                  <h2>Top Products</h2>
                  <table>
                    <thead><tr><th>Product</th><th className="text-right">Sold</th><th className="text-right">Revenue</th></tr></thead>
                    <tbody>
                      {salesData.top_products?.map(p => (
                        <tr key={p.product_id}><td>{p.product_name}</td><td className="text-right">{p.total_sold}</td><td className="text-right bold">৳{p.total_revenue?.toLocaleString()}</td></tr>
                      ))}
                    </tbody>
                  </table>
                  <h2>Category Sales</h2>
                  <table>
                    <thead><tr><th>Category</th><th className="text-right">Orders</th><th className="text-right">Revenue</th></tr></thead>
                    <tbody>
                      {salesData.category_sales?.map(c => (
                        <tr key={c.category_id}><td>{c.category_name}</td><td className="text-right">{c.total_orders}</td><td className="text-right bold">৳{c.total_revenue?.toLocaleString()}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </div>
          </div>
        </>
      )}

      {/* ============ STOCK REPORT ============ */}
      {reportType === 'stock' && (
        <>
          {/* Toolbar */}
          <div className="bg-white rounded-xl border shadow-sm p-4 mb-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-gray-500">Current inventory status with product &amp; variant details</p>
              {stockData && (
                <div className="flex gap-2">
                  <button onClick={() => downloadCSV('stock')} className="btn btn-secondary text-sm">
                    <Download className="w-4 h-4 mr-1.5" />CSV
                  </button>
                  <button onClick={() => downloadPDF('stock')} className="btn btn-secondary text-sm">
                    <FileText className="w-4 h-4 mr-1.5" />PDF
                  </button>
                </div>
              )}
            </div>
          </div>

          {loading ? (
            <div className="animate-pulse space-y-4">
              <div className="grid grid-cols-4 gap-4">
                {[1, 2, 3, 4].map(i => <div key={i} className="h-24 bg-gray-200 rounded-xl" />)}
              </div>
            </div>
          ) : stockData && (
            <>
              {/* Summary */}
              <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                <StatCard icon={Package} label="Total Products" value={stockData.summary?.total_products || 0} color="blue"
                  sub={`${stockData.summary?.total_variants || 0} variants`} />
                <StatCard icon={BarChart3} label="In Stock" value={stockData.summary?.in_stock || 0} color="green"
                  sub={`${stockData.summary?.total_units?.toLocaleString() || 0} units`} />
                <StatCard icon={AlertTriangle} label="Low / Out of Stock" value={`${stockData.summary?.low_stock || 0} / ${stockData.summary?.out_of_stock || 0}`} color="red" />
                <StatCard icon={DollarSign} label="Stock Value" value={`৳${(stockData.summary?.total_stock_value || 0).toLocaleString()}`} color="indigo"
                  sub={`Variant units: ${(stockData.summary?.total_variant_units || 0).toLocaleString()}`} />
              </div>

              <div className="grid lg:grid-cols-2 gap-6 mb-6">
                {/* Category Stock */}
                <div className="bg-white rounded-xl border shadow-sm p-6">
                  <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-4">Stock by Category</h3>
                  <div className="space-y-3">
                    {stockData.category_stock?.map((cat) => {
                      const maxStock = Math.max(...stockData.category_stock.map(c => c.total_stock)) || 1;
                      return (
                        <div key={cat.category_id}>
                          <div className="flex justify-between mb-1">
                            <span className="text-sm font-medium text-gray-700">{cat.category_name}</span>
                            <span className="text-sm font-bold">{cat.total_stock} units</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <div className="flex-1 bg-gray-100 rounded-full h-2">
                              <div className="bg-cyan-500 h-2 rounded-full" style={{ width: `${(cat.total_stock / maxStock) * 100}%` }} />
                            </div>
                            <span className="text-xs text-gray-400 w-16 text-right">৳{cat.stock_value?.toLocaleString()}</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Stock Health */}
                <div className="bg-white rounded-xl border shadow-sm p-6">
                  <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-4">Stock Health Overview</h3>
                  <div className="space-y-4">
                    {[
                      { label: 'Healthy Stock', count: stockData.summary?.in_stock || 0, total: stockData.summary?.total_products || 1, color: 'bg-green-500' },
                      { label: 'Low Stock', count: stockData.summary?.low_stock || 0, total: stockData.summary?.total_products || 1, color: 'bg-amber-500' },
                      { label: 'Out of Stock', count: stockData.summary?.out_of_stock || 0, total: stockData.summary?.total_products || 1, color: 'bg-red-500' },
                    ].map(item => {
                      const pct = ((item.count / item.total) * 100).toFixed(1);
                      return (
                        <div key={item.label}>
                          <div className="flex justify-between mb-1">
                            <span className="text-sm text-gray-600">{item.label}</span>
                            <span className="text-sm font-bold">{item.count} <span className="font-normal text-gray-400">({pct}%)</span></span>
                          </div>
                          <div className="w-full bg-gray-100 rounded-full h-2.5">
                            <div className={`${item.color} h-2.5 rounded-full transition-all`} style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Detailed Product Table with Variants */}
              <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
                <div className="px-6 py-4 border-b bg-gray-50/50 flex flex-wrap items-center justify-between gap-3">
                  <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider flex items-center gap-2">
                    <Layers className="w-4 h-4" />
                    All Products &amp; Variants ({filteredProducts.length})
                  </h3>
                  <div className="flex items-center gap-2">
                    <div className="relative">
                      <Search className="w-4 h-4 text-gray-400 absolute left-2.5 top-2.5" />
                      <input
                        type="text"
                        value={stockSearch}
                        onChange={(e) => setStockSearch(e.target.value)}
                        placeholder="Search products..."
                        className="pl-8 pr-3 py-2 border rounded-lg text-sm w-48 focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                      />
                    </div>
                    <select
                      value={stockFilter}
                      onChange={(e) => setStockFilter(e.target.value)}
                      className="border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 bg-white"
                    >
                      <option value="all">All Products</option>
                      <option value="in_stock">In Stock</option>
                      <option value="low_stock">Low Stock</option>
                      <option value="out_of_stock">Out of Stock</option>
                      <option value="has_variants">Has Variants</option>
                    </select>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b bg-gray-50/30">
                        <th className="w-10 py-3 px-4" />
                        <th className="text-left py-3 px-3 text-xs font-semibold text-gray-500 uppercase">Product</th>
                        <th className="text-left py-3 px-3 text-xs font-semibold text-gray-500 uppercase">SKU</th>
                        <th className="text-left py-3 px-3 text-xs font-semibold text-gray-500 uppercase">Price</th>
                        <th className="text-left py-3 px-3 text-xs font-semibold text-gray-500 uppercase">Stock</th>
                        <th className="text-left py-3 px-3 text-xs font-semibold text-gray-500 uppercase">Variants</th>
                        <th className="text-left py-3 px-3 text-xs font-semibold text-gray-500 uppercase">Var. Stock</th>
                        <th className="text-left py-3 px-3 text-xs font-semibold text-gray-500 uppercase">Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredProducts.map((product) => (
                        <StockProductRow key={product.id} product={product} />
                      ))}
                      {filteredProducts.length === 0 && (
                        <tr><td colSpan={8} className="py-12 text-center text-gray-400 text-sm">No products match your filter</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}

          {/* Stock Print Template (hidden) */}
          <div className="hidden">
            <div ref={stockPrintRef}>
              <div className="header">
                <div><h1>Zzuhana</h1><p className="meta">Stock Report</p></div>
                <div style={{ textAlign: 'right' }}><p className="bold">{new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}</p></div>
              </div>
              {stockData && (
                <>
                  <div className="stat-grid">
                    <div className="stat-box"><div className="val">{stockData.summary?.total_products || 0}</div><div className="lbl">Products</div></div>
                    <div className="stat-box"><div className="val">{stockData.summary?.in_stock || 0}</div><div className="lbl">In Stock</div></div>
                    <div className="stat-box"><div className="val" style={{ color: '#dc2626' }}>{stockData.summary?.out_of_stock || 0}</div><div className="lbl">Out of Stock</div></div>
                    <div className="stat-box"><div className="val">৳{(stockData.summary?.total_stock_value || 0).toLocaleString()}</div><div className="lbl">Stock Value</div></div>
                  </div>
                  <h2>All Products &amp; Variants</h2>
                  <table>
                    <thead>
                      <tr><th>Product</th><th>SKU</th><th>Category</th><th className="text-right">Price</th><th className="text-center">Stock</th><th className="text-right">Value</th></tr>
                    </thead>
                    <tbody>
                      {stockData.all_products?.map(p => (
                        <React.Fragment key={p.id}>
                          <tr>
                            <td className="bold">{p.name}</td>
                            <td>{p.sku}</td>
                            <td>{p.category}</td>
                            <td className="text-right">৳{p.price.toLocaleString()}</td>
                            <td className="text-center">
                              <span className={`badge ${p.stock_quantity === 0 ? 'badge-out' : p.stock_quantity <= p.low_stock_threshold ? 'badge-low' : 'badge-ok'}`}>
                                {p.stock_quantity}
                              </span>
                            </td>
                            <td className="text-right">৳{p.stock_value.toLocaleString()}</td>
                          </tr>
                          {p.variants?.map(v => (
                            <tr key={v.id} className="sub-row">
                              <td>↳ {v.size || ''} {v.color || ''}</td>
                              <td>{v.sku}</td>
                              <td></td>
                              <td className="text-right">৳{v.price.toLocaleString()}</td>
                              <td className="text-center">
                                <span className={`badge ${v.stock_quantity === 0 ? 'badge-out' : 'badge-ok'}`}>{v.stock_quantity}</span>
                              </td>
                              <td className="text-right">৳{v.stock_value.toLocaleString()}</td>
                            </tr>
                          ))}
                        </React.Fragment>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </div>
          </div>
        </>
      )}
    </AdminLayout>
  );
}
