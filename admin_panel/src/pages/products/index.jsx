import { useState, useMemo } from 'react';
import Link from 'next/link';
import {
  Search, Plus, Edit, Trash2, AlertTriangle,
  ChevronDown, ChevronRight, Copy, Check, Barcode,
  Package, Layers
} from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import { useGetProductsQuery, useDeleteProductMutation } from '@/store/api/productsApi';
import { useGetCategoriesQuery } from '@/store/api/categoriesApi';
import { getMediaUrl } from '@/lib/utils';

export default function ProductsPage() {
  const [filters, setFilters] = useState({
    search: '',
    category: '',
    is_active: '',
  });
  const [expandedProducts, setExpandedProducts] = useState({});
  const [copiedBarcode, setCopiedBarcode] = useState(null);

  const queryParams = useMemo(() => {
    const params = {};
    if (filters.search) params.search = filters.search;
    if (filters.category) params.category = filters.category;
    if (filters.is_active) params.is_active = filters.is_active;
    return params;
  }, [filters]);

  const { data: categoriesData } = useGetCategoriesQuery();
  const { data: productsData, isLoading: loading } = useGetProductsQuery(queryParams);
  const [deleteProduct] = useDeleteProductMutation();

  const categories = Array.isArray(categoriesData?.results || categoriesData)
    ? (categoriesData?.results || categoriesData)
    : [];
  const products = productsData?.results || productsData || [];

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this product?')) return;
    try {
      await deleteProduct(id).unwrap();
      toast.success('Product deleted');
    } catch (error) {
      toast.error('Failed to delete product');
    }
  };

  const toggleExpand = (productId) => {
    setExpandedProducts(prev => ({ ...prev, [productId]: !prev[productId] }));
  };

  const copyBarcode = (barcode) => {
    if (!barcode) return;
    navigator.clipboard.writeText(barcode);
    setCopiedBarcode(barcode);
    toast.success('Barcode copied!');
    setTimeout(() => setCopiedBarcode(null), 2000);
  };

  const getImageUrl = (img) => getMediaUrl(img);

  const getStockBadge = (product) => {
    const variants = product.variants || [];
    const hasVariants = variants.length > 0;
    const totalStock = hasVariants
      ? variants.reduce((sum, v) => sum + (v.stock_quantity || 0), 0)
      : product.stock_quantity;

    if (totalStock === 0) return { label: 'Out of Stock', cls: 'bg-red-100 text-red-700' };
    if (product.is_low_stock || totalStock <= (product.low_stock_threshold || 5))
      return { label: `Low: ${totalStock}`, cls: 'bg-yellow-100 text-yellow-700' };
    return { label: totalStock, cls: 'text-gray-900' };
  };

  return (
    <AdminLayout title="Products">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div className="flex-1">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search products..."
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              className="input pl-10"
            />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={filters.category}
            onChange={(e) => setFilters({ ...filters, category: e.target.value })}
            className="input w-auto"
          >
            <option value="">All Categories</option>
            {Array.isArray(categories) && categories.map((cat) => (
              <option key={cat.id} value={cat.id}>{cat.name}</option>
            ))}
          </select>

          <Link href="/products/new" className="btn btn-primary">
            <Plus className="w-4 h-4 mr-2" />
            Add Product
          </Link>
        </div>
      </div>

      {/* Products Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="w-8 py-3 px-3"></th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-600 uppercase">Product</th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-600 uppercase">SKU / Barcode</th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-600 uppercase">Category</th>
                <th className="text-right py-3 px-4 text-xs font-semibold text-gray-600 uppercase">Price</th>
                <th className="text-center py-3 px-4 text-xs font-semibold text-gray-600 uppercase">Stock</th>
                <th className="text-center py-3 px-4 text-xs font-semibold text-gray-600 uppercase">Status</th>
                <th className="text-center py-3 px-4 text-xs font-semibold text-gray-600 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                [...Array(6)].map((_, i) => (
                  <tr key={i} className="border-b border-gray-100">
                    <td colSpan={8} className="py-5 px-4">
                      <div className="flex items-center gap-4">
                        <div className="w-8" />
                        <div className="w-12 h-12 bg-gray-100 rounded-lg animate-pulse" />
                        <div className="flex-1 space-y-2">
                          <div className="h-4 bg-gray-100 rounded w-40 animate-pulse" />
                          <div className="h-3 bg-gray-50 rounded w-24 animate-pulse" />
                        </div>
                      </div>
                    </td>
                  </tr>
                ))
              ) : products.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center py-16">
                    <Package className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                    <p className="text-gray-500 font-medium">No products found</p>
                    <p className="text-gray-400 text-sm mt-1">Try adjusting your search or filters</p>
                  </td>
                </tr>
              ) : (
                products.map((product) => {
                  const variants = product.variants || [];
                  const hasVariants = variants.length > 0;
                  const isExpanded = expandedProducts[product.id];
                  const stockBadge = getStockBadge(product);
                  const totalStock = hasVariants
                    ? variants.reduce((sum, v) => sum + (v.stock_quantity || 0), 0)
                    : product.stock_quantity;

                  return (
                    <>{/* Product Row */}
                      <tr key={product.id} className="border-b border-gray-100 hover:bg-gray-50/70 transition-colors">
                        {/* Expand toggle */}
                        <td className="py-3 px-3">
                          {hasVariants ? (
                            <button
                              onClick={() => toggleExpand(product.id)}
                              className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors"
                              title={`${variants.length} variant${variants.length > 1 ? 's' : ''}`}
                            >
                              {isExpanded ? <ChevronDown className="w-4 h-4 text-gray-600" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
                            </button>
                          ) : <span className="w-7" />}
                        </td>

                        {/* Product info */}
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-3">
                            <div className="w-12 h-12 bg-gray-100 rounded-xl flex-shrink-0 overflow-hidden border border-gray-200">
                              {product.primary_image ? (
                                <img src={getImageUrl(product.primary_image)} alt="" className="w-full h-full object-cover" />
                              ) : (
                                <div className="w-full h-full flex items-center justify-center">
                                  <Package className="w-5 h-5 text-gray-300" />
                                </div>
                              )}
                            </div>
                            <div className="min-w-0">
                              <p className="font-semibold text-gray-900 truncate">{product.name}</p>
                              <div className="flex items-center gap-2 mt-0.5">
                                {product.is_featured && (
                                  <span className="px-1.5 py-0.5 bg-primary-50 text-primary-700 rounded text-[10px] font-bold uppercase">Featured</span>
                                )}
                                {hasVariants && (
                                  <span className="flex items-center gap-1 text-xs text-gray-500">
                                    <Layers className="w-3 h-3" />
                                    {variants.length} variant{variants.length > 1 ? 's' : ''}
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                        </td>

                        {/* SKU / Barcode */}
                        <td className="py-3 px-4">
                          <div className="space-y-1">
                            {product.sku && (
                              <p className="font-mono text-sm text-gray-700">{product.sku}</p>
                            )}
                            {product.barcode && (
                              <button
                                onClick={() => copyBarcode(product.barcode)}
                                className="inline-flex items-center gap-1.5 px-2 py-0.5 bg-gray-100 hover:bg-gray-200 rounded text-xs font-mono text-gray-600 transition-colors group"
                                title="Click to copy barcode"
                              >
                                {copiedBarcode === product.barcode ? (
                                  <Check className="w-3 h-3 text-green-600" />
                                ) : (
                                  <Copy className="w-3 h-3 text-gray-400 group-hover:text-gray-600" />
                                )}
                                {product.barcode}
                              </button>
                            )}
                            {!product.sku && !product.barcode && (
                              <span className="text-gray-300 text-sm">—</span>
                            )}
                          </div>
                        </td>

                        {/* Category */}
                        <td className="py-3 px-4">
                          <span className="text-sm text-gray-600">{product.category_name || '—'}</span>
                        </td>

                        {/* Price */}
                        <td className="py-3 px-4 text-right">
                          <p className="font-semibold text-gray-900">৳{parseFloat(product.price).toLocaleString()}</p>
                          {product.compare_price && parseFloat(product.compare_price) > parseFloat(product.price) && (
                            <p className="text-xs text-gray-400 line-through">৳{parseFloat(product.compare_price).toLocaleString()}</p>
                          )}
                        </td>

                        {/* Stock */}
                        <td className="py-3 px-4 text-center">
                          {product.is_out_of_stock || totalStock === 0 ? (
                            <span className="px-2 py-1 bg-red-100 text-red-700 rounded-full text-xs font-medium">Out of Stock</span>
                          ) : product.is_low_stock ? (
                            <span className="px-2 py-1 bg-yellow-100 text-yellow-700 rounded-full text-xs font-medium flex items-center justify-center gap-1 w-fit mx-auto">
                              <AlertTriangle className="w-3 h-3" />
                              {totalStock}
                            </span>
                          ) : (
                            <span className="font-bold text-gray-900">{totalStock}</span>
                          )}
                        </td>

                        {/* Status */}
                        <td className="py-3 px-4 text-center">
                          <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${product.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                            {product.is_active ? 'Active' : 'Inactive'}
                          </span>
                        </td>

                        {/* Actions */}
                        <td className="py-3 px-4 text-center">
                          <div className="flex items-center justify-center gap-1">
                            <Link
                              href={`/products/${product.id}`}
                              className="p-2 text-gray-500 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                              title="Edit product"
                            >
                              <Edit className="w-4 h-4" />
                            </Link>
                            <button
                              onClick={() => handleDelete(product.id)}
                              className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                              title="Delete product"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>

                      {/* Variant Rows */}
                      {hasVariants && isExpanded && variants.map((variant) => {
                        const vLabel = [variant.size, variant.color].filter(Boolean).join(' / ') || 'Default';
                        return (
                          <tr key={variant.id} className="border-b border-gray-50 bg-blue-50/30 transition-colors hover:bg-blue-50/50">
                            <td className="py-2.5 px-3"></td>
                            <td className="py-2.5 px-4 pl-16">
                              <div className="flex items-center gap-2">
                                <span className="w-2 h-2 bg-primary-400 rounded-full flex-shrink-0" />
                                <span className="text-sm font-medium text-gray-800">{vLabel}</span>
                              </div>
                            </td>
                            <td className="py-2.5 px-4">
                              <div className="space-y-1">
                                {variant.sku && (
                                  <p className="font-mono text-xs text-gray-500">{variant.sku}</p>
                                )}
                                {variant.barcode && (
                                  <button
                                    onClick={() => copyBarcode(variant.barcode)}
                                    className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-gray-100 hover:bg-gray-200 rounded text-[11px] font-mono text-gray-500 transition-colors group"
                                    title="Click to copy barcode"
                                  >
                                    {copiedBarcode === variant.barcode ? (
                                      <Check className="w-2.5 h-2.5 text-green-600" />
                                    ) : (
                                      <Copy className="w-2.5 h-2.5 text-gray-400 group-hover:text-gray-600" />
                                    )}
                                    {variant.barcode}
                                  </button>
                                )}
                              </div>
                            </td>
                            <td className="py-2.5 px-4"></td>
                            <td className="py-2.5 px-4 text-right text-sm text-gray-700">
                              ৳{parseFloat(variant.effective_price || variant.price).toLocaleString()}
                            </td>
                            <td className="py-2.5 px-4 text-center">
                              <span className={`font-bold text-sm ${variant.stock_quantity === 0 ? 'text-red-600' : 'text-gray-800'}`}>
                                {variant.stock_quantity}
                              </span>
                            </td>
                            <td className="py-2.5 px-4 text-center">
                              <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${variant.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                                {variant.is_active ? 'Active' : 'Inactive'}
                              </span>
                            </td>
                            <td className="py-2.5 px-4"></td>
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

        {/* Footer */}
        {!loading && products.length > 0 && (
          <div className="px-4 py-3 border-t bg-gray-50 text-sm text-gray-500 flex items-center justify-between">
            <span>{products.length} product{products.length !== 1 ? 's' : ''}</span>
            <span>{products.reduce((sum, p) => sum + (p.variants?.length || 0), 0)} total variants</span>
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
