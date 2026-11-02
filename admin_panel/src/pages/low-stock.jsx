import Link from 'next/link';
import { AlertTriangle, Package, RefreshCw } from 'lucide-react';
import AdminLayout from '@/components/layout/AdminLayout';
import { useGetLowStockQuery } from '@/store/api/productsApi';
import { getMediaUrl } from '@/lib/utils';

export default function LowStockPage() {
  const { data: productsData, isLoading: loading, refetch: fetchLowStock } = useGetLowStockQuery();
  const products = productsData?.results || productsData || [];

  return (
    <AdminLayout title="Low Stock Alerts">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-red-100 rounded-xl">
            <AlertTriangle className="w-6 h-6 text-red-600" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              {products.length} Products Need Attention
            </h2>
            <p className="text-sm text-gray-500">
              Quantities change through purchases and sales. Review stock and dealer availability on Products.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Link href="/products" className="btn btn-primary">
            Open Products
          </Link>
          <button
            type="button"
            onClick={fetchLowStock}
            className="btn btn-secondary"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </button>
        </div>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {loading ? (
          [...Array(6)].map((_, i) => (
            <div key={i} className="card p-6 animate-pulse">
              <div className="h-20 bg-gray-200 rounded mb-4" />
              <div className="h-4 bg-gray-200 rounded w-3/4" />
            </div>
          ))
        ) : products.length === 0 ? (
          <div className="col-span-full text-center py-12">
            <Package className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">All Stocked Up!</h3>
            <p className="text-gray-500">No products are running low on stock.</p>
          </div>
        ) : (
          products.map((product) => {
            const hasVariants = product.variants?.length > 0;
            const lowVariants = hasVariants
              ? product.variants.filter(v => v.stock_quantity <= (v.low_stock_threshold ?? product.low_stock_threshold))
              : [];
            const displayStock = hasVariants
              ? product.variants.reduce((sum, v) => sum + v.stock_quantity, 0)
              : product.stock_quantity;
            const isOut = hasVariants
              ? product.variants.every(v => v.stock_quantity === 0)
              : product.stock_quantity === 0;

            return (
              <div key={product.id} className="card p-6">
                <div className="flex items-start gap-4 mb-4">
                  <div className="w-16 h-16 bg-gray-100 rounded-lg flex-shrink-0 overflow-hidden flex items-center justify-center">
                    {product.primary_image ? (
                      <img
                        src={getMediaUrl(product.primary_image)}
                        alt={product.name}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <Package className="w-8 h-8 text-gray-400" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-gray-900 truncate">{product.name}</h3>
                    <p className="text-sm text-gray-500">SKU: {product.sku}</p>
                    <p className="text-sm text-gray-500">{product.category_name}</p>
                  </div>
                </div>

                {hasVariants ? (
                  <div className="space-y-2 mb-4">
                    {lowVariants.map((v) => {
                      const label = [v.size, v.color].filter(Boolean).join(' / ') || 'Default';
                      return (
                        <div
                          key={v.id}
                          className={`p-3 rounded-lg ${v.stock_quantity === 0
                            ? 'bg-red-50 border border-red-200'
                            : 'bg-yellow-50 border border-yellow-200'
                            }`}
                        >
                          <div className="flex items-center justify-between">
                            <div>
                              <span className="text-sm font-medium text-gray-800">{label}</span>
                              <span className={`ml-2 text-xs font-medium ${v.stock_quantity === 0 ? 'text-red-600' : 'text-yellow-600'}`}>
                                {v.stock_quantity === 0 ? 'Out of Stock' : 'Low Stock'}
                              </span>
                            </div>
                            <span className={`text-lg font-bold ${v.stock_quantity === 0 ? 'text-red-600' : 'text-yellow-600'}`}>
                              {v.stock_quantity}
                            </span>
                          </div>
                          <p className="text-xs text-gray-500 mt-1">
                            Threshold: {v.low_stock_threshold ?? product.low_stock_threshold}
                          </p>
                        </div>
                      );
                    })}
                    {lowVariants.length === 0 && (
                      <div className="p-3 rounded-lg bg-yellow-50 border border-yellow-200">
                        <span className="text-sm text-yellow-700">Total stock: {displayStock}</span>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className={`p-4 rounded-lg mb-4 ${isOut
                    ? 'bg-red-50 border border-red-200'
                    : 'bg-yellow-50 border border-yellow-200'
                    }`}>
                    <div className="flex items-center justify-between">
                      <span className={`text-sm font-medium ${isOut ? 'text-red-700' : 'text-yellow-700'}`}>
                        {isOut ? 'Out of Stock' : 'Low Stock'}
                      </span>
                      <span className={`text-2xl font-bold ${isOut ? 'text-red-600' : 'text-yellow-600'}`}>
                        {product.stock_quantity}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      Threshold: {product.low_stock_threshold}
                    </p>
                  </div>
                )}

                <Link href={`/products/${product.id}`} className="text-sm font-medium text-primary-600">
                  View product →
                </Link>
              </div>
            );
          })
        )}
      </div>
    </AdminLayout>
  );
}
