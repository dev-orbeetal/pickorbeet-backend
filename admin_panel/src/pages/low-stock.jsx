import { useState } from 'react';
import { AlertTriangle, Package, RefreshCw, Plus, Minus } from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import { useGetLowStockQuery, useUpdateStockMutation, useUpdateVariantStockMutation } from '@/store/api/productsApi';
import { getMediaUrl } from '@/lib/utils';

export default function LowStockPage() {
  const { data: productsData, isLoading: loading, refetch: fetchLowStock } = useGetLowStockQuery();
  const [updateStockMutation] = useUpdateStockMutation();
  const [updateVariantStockMutation] = useUpdateVariantStockMutation();

  const products = productsData?.results || productsData || [];
  const [updating, setUpdating] = useState(null);

  const updateStock = async (productId, operation, quantity) => {
    setUpdating(productId);
    try {
      await updateStockMutation({ id: productId, operation, quantity }).unwrap();
      toast.success('Stock updated');
    } catch (error) {
      toast.error(error?.data?.error || 'Failed to update stock');
    } finally {
      setUpdating(null);
    }
  };

  const updateVariantStock = async (variantId, operation, quantity) => {
    setUpdating(variantId);
    try {
      await updateVariantStockMutation({ variantId, operation, quantity }).unwrap();
      toast.success('Variant stock updated');
      fetchLowStock();
    } catch (error) {
      toast.error(error?.data?.error || 'Failed to update variant stock');
    } finally {
      setUpdating(null);
    }
  };

  const [stockInputs, setStockInputs] = useState({});

  return (
    <AdminLayout title="Low Stock Alerts">
      {/* Header */}
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
              Products with stock at or below threshold
            </p>
          </div>
        </div>

        <button
          onClick={fetchLowStock}
          className="btn btn-secondary"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </button>
      </div>

      {/* Products Grid */}
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

                {/* Stock Status */}
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
                          <div className="flex items-center gap-2 mt-2">
                            <input
                              type="number"
                              placeholder="Qty"
                              min="1"
                              value={stockInputs[v.id] || ''}
                              onChange={(e) => setStockInputs({
                                ...stockInputs,
                                [v.id]: parseInt(e.target.value) || ''
                              })}
                              className="input flex-1 text-sm py-1"
                            />
                            <button
                              onClick={() => {
                                const qty = stockInputs[v.id];
                                if (qty > 0) {
                                  updateVariantStock(v.id, 'add', qty);
                                  setStockInputs({ ...stockInputs, [v.id]: '' });
                                }
                              }}
                              disabled={updating === v.id || !stockInputs[v.id]}
                              className="btn btn-success text-sm py-1 px-3"
                            >
                              <Plus className="w-3 h-3 mr-1" />
                              Add
                            </button>
                          </div>
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

                {/* Quick Stock Update for non-variant products */}
                {!hasVariants && (
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      placeholder="Qty"
                      min="1"
                      value={stockInputs[product.id] || ''}
                      onChange={(e) => setStockInputs({
                        ...stockInputs,
                        [product.id]: parseInt(e.target.value) || ''
                      })}
                      className="input flex-1"
                    />
                    <button
                      onClick={() => {
                        const qty = stockInputs[product.id];
                        if (qty > 0) {
                          updateStock(product.id, 'add', qty);
                          setStockInputs({ ...stockInputs, [product.id]: '' });
                        }
                      }}
                      disabled={updating === product.id || !stockInputs[product.id]}
                      className="btn btn-success"
                    >
                      <Plus className="w-4 h-4 mr-1" />
                      Add
                    </button>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </AdminLayout>
  );
}
