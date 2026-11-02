import { useState, useMemo, useEffect, Fragment } from 'react';
import Link from 'next/link';
import {
  Search, Plus, Edit, Trash2, Info,
  ChevronDown, ChevronRight,
  Package, Layers, Home,
} from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import SupplyBadge from '@/components/products/SupplyBadge';
import LoadError from '@/components/ui/LoadError';
import Pager from '@/components/ui/Pager';
import {
  useGetProductsQuery,
  useDeleteProductMutation,
  useUpdateProductMutation,
} from '@/store/api/productsApi';
import { useGetCategoriesQuery } from '@/store/api/categoriesApi';
import { getMediaUrl } from '@/lib/utils';

function stockTotals(product) {
  const variants = product.variants || [];
  if (variants.length > 0) {
    const warehouse = variants.reduce((sum, v) => sum + Number(v.warehouse_stock || 0), 0);
    const dealer = variants.reduce((sum, v) => sum + Number(v.dealer_stock || 0), 0);
    return { warehouse, dealer, total: warehouse + dealer };
  }
  const warehouse = Number(product.warehouse_stock || 0);
  const dealer = Number(product.dealer_stock || 0);
  return {
    warehouse,
    dealer,
    total: warehouse + dealer || Number(product.stock_quantity || 0),
  };
}

function FlagToggle({ checked, onToggle, disabled, ariaLabel, onLabel, offLabel }) {
  return (
    <div className="flex items-center justify-center gap-2">
      <input
        type="checkbox"
        className="toggle"
        checked={checked}
        disabled={disabled}
        onChange={onToggle}
        aria-label={ariaLabel}
      />
      <span
        className={`px-2 py-0.5 rounded-full text-[11px] font-medium whitespace-nowrap ${
          checked ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
        }`}
      >
        {checked ? onLabel : offLabel}
      </span>
    </div>
  );
}

export default function ProductsPage() {
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({
    search: '',
    category: '',
    is_active: '',
    supply_type: '',
  });
  const [expandedProducts, setExpandedProducts] = useState({});
  const [togglingKey, setTogglingKey] = useState(null);

  useEffect(() => {
    setPage(1);
  }, [filters.search, filters.category, filters.is_active, filters.supply_type]);

  const queryParams = useMemo(() => {
    const params = { page };
    if (filters.search) params.search = filters.search;
    if (filters.category) params.category = filters.category;
    if (filters.is_active) params.is_active = filters.is_active;
    if (filters.supply_type) params.supply_type = filters.supply_type;
    return params;
  }, [filters, page]);

  const { data: categoriesData } = useGetCategoriesQuery();
  const { data: productsData, isLoading: loading, isError, refetch } = useGetProductsQuery(queryParams);
  const [deleteProduct] = useDeleteProductMutation();
  const [updateProduct] = useUpdateProductMutation();

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

  const handleDealerAvailability = async (product) => {
    const next = !product.dealer_available;
    setTogglingKey(`${product.id}:dealer`);
    try {
      await updateProduct({ id: product.id, dealer_available: next }).unwrap();
      toast.success(next ? 'Dealer availability enabled' : 'Dealer availability disabled');
    } catch (error) {
      toast.error(error?.data?.detail || 'Could not update dealer availability');
    } finally {
      setTogglingKey(null);
    }
  };

  const handleFeatured = async (product) => {
    const next = !product.is_featured;
    setTogglingKey(`${product.id}:featured`);
    try {
      await updateProduct({ id: product.id, is_featured: next }).unwrap();
      toast.success(next ? 'Marked as featured' : 'Removed from featured');
    } catch (error) {
      toast.error(error?.data?.detail || 'Could not update featured status');
    } finally {
      setTogglingKey(null);
    }
  };

  const toggleExpand = (productId) => {
    setExpandedProducts((prev) => ({ ...prev, [productId]: !prev[productId] }));
  };

  const getImageUrl = (img) => getMediaUrl(img);

  return (
    <AdminLayout title="Products">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Products</h1>
        <p className="text-sm text-gray-500 mt-1">
          Manage products, view stock from purchase records, and set dealer availability.
        </p>
      </div>

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

        <div className="flex flex-wrap items-center gap-3">
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

          <select
            value={filters.is_active}
            onChange={(e) => setFilters({ ...filters, is_active: e.target.value })}
            className="input w-auto"
          >
            <option value="">All Status</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>

          <select
            value={filters.supply_type}
            onChange={(e) => setFilters({ ...filters, supply_type: e.target.value })}
            className="input w-auto"
          >
            <option value="">All sources</option>
            <option value="available_stock">Available Stock</option>
            <option value="seller_provided">Seller-Provided</option>
          </select>

          <Link href="/products/new" className="btn btn-primary">
            <Plus className="w-4 h-4 mr-2" />
            Add Product
          </Link>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="w-8 py-3 px-3" />
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-600 uppercase">
                  Product
                </th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-600 uppercase">
                  SKU
                </th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-600 uppercase">
                  Category
                </th>
                <th className="text-right py-3 px-4 text-xs font-semibold text-gray-600 uppercase">
                  Selling Price
                </th>
                <th className="text-center py-3 px-4 text-xs font-semibold text-gray-600 uppercase">
                  <span className="inline-flex items-center gap-1 justify-center">
                    <Home className="w-3.5 h-3.5" /> Warehouse Stock
                  </span>
                </th>
                <th className="text-center py-3 px-4 text-xs font-semibold text-gray-600 uppercase">
                  <span className="inline-flex items-center gap-1">
                    Dealer Availability
                    <span title="Manual flag. Independent of warehouse stock. Enables dealer fulfillment when warehouse is empty.">
                      <Info className="w-3.5 h-3.5 text-gray-400" />
                    </span>
                  </span>
                </th>
                <th className="text-center py-3 px-4 text-xs font-semibold text-gray-600 uppercase">
                  Featured
                </th>
                <th className="text-center py-3 px-4 text-xs font-semibold text-gray-600 uppercase">
                  Status
                </th>
                <th className="text-center py-3 px-4 text-xs font-semibold text-gray-600 uppercase">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                [...Array(6)].map((_, i) => (
                  <tr key={i} className="border-b border-gray-100">
                    <td colSpan={10} className="py-5 px-4">
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
              ) : isError ? (
                <tr>
                  <td colSpan={10} className="py-4">
                    <LoadError title="Could not load products" onRetry={refetch} />
                  </td>
                </tr>
              ) : products.length === 0 ? (
                <tr>
                  <td colSpan={10} className="text-center py-16">
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
                  const { warehouse } = stockTotals(product);

                  return (
                    <Fragment key={product.id}>
                      <tr className="border-b border-gray-100 hover:bg-gray-50/70 transition-colors">
                        <td className="py-3 px-3">
                          {hasVariants ? (
                            <button
                              type="button"
                              onClick={() => toggleExpand(product.id)}
                              className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors"
                              title={`${variants.length} variant${variants.length > 1 ? 's' : ''}`}
                            >
                              {isExpanded
                                ? <ChevronDown className="w-4 h-4 text-gray-600" />
                                : <ChevronRight className="w-4 h-4 text-gray-400" />}
                            </button>
                          ) : <span className="w-7" />}
                        </td>

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
                              <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                                {product.is_featured && (
                                  <span className="px-1.5 py-0.5 bg-primary-50 text-primary-700 rounded text-[10px] font-bold uppercase">
                                    Featured
                                  </span>
                                )}
                                {hasVariants && (
                                  <span className="flex items-center gap-1 text-xs text-gray-500">
                                    <Layers className="w-3 h-3" />
                                    {variants.length} variant{variants.length > 1 ? 's' : ''}
                                  </span>
                                )}
                                <SupplyBadge type={product.supply_type} seller={product.supplied_by_name} />
                              </div>
                            </div>
                          </div>
                        </td>

                        <td className="py-3 px-4">
                          <p className="font-mono text-sm text-gray-700">{product.sku || '—'}</p>
                        </td>

                        <td className="py-3 px-4">
                          <span className="text-sm text-gray-600">{product.category_name || '—'}</span>
                        </td>

                        <td className="py-3 px-4 text-right">
                          <p className="font-semibold text-gray-900">৳{parseFloat(product.price).toLocaleString()}</p>
                          {product.compare_price && parseFloat(product.compare_price) > parseFloat(product.price) && (
                            <p className="text-xs text-gray-400 line-through">
                              ৳{parseFloat(product.compare_price).toLocaleString()}
                            </p>
                          )}
                        </td>

                        <td className="py-3 px-4 text-center text-sm tabular-nums text-gray-800 font-semibold">
                          {warehouse}
                        </td>

                        <td className="py-3 px-4">
                          <FlagToggle
                            checked={Boolean(product.dealer_available)}
                            onToggle={() => handleDealerAvailability(product)}
                            disabled={togglingKey === `${product.id}:dealer`}
                            ariaLabel={`Dealer availability for ${product.name}`}
                            onLabel="Available"
                            offLabel="Not Available"
                          />
                        </td>

                        <td className="py-3 px-4">
                          <FlagToggle
                            checked={Boolean(product.is_featured)}
                            onToggle={() => handleFeatured(product)}
                            disabled={togglingKey === `${product.id}:featured`}
                            ariaLabel={`Featured for ${product.name}`}
                            onLabel="Featured"
                            offLabel="Not Featured"
                          />
                        </td>

                        <td className="py-3 px-4 text-center">
                          <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${product.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                            {product.is_active ? 'Active' : 'Inactive'}
                          </span>
                        </td>

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
                              type="button"
                              onClick={() => handleDelete(product.id)}
                              className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                              title="Delete product"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>

                      {hasVariants && isExpanded && variants.map((variant) => {
                        const vLabel = [variant.size, variant.color].filter(Boolean).join(' / ') || 'Default';
                        const vWarehouse = Number(variant.warehouse_stock || 0);
                        return (
                          <tr key={variant.id} className="border-b border-gray-50 bg-blue-50/30 transition-colors hover:bg-blue-50/50">
                            <td className="py-2.5 px-3" />
                            <td className="py-2.5 px-4 pl-16">
                              <div className="flex items-center gap-2">
                                <span className="w-2 h-2 bg-primary-400 rounded-full flex-shrink-0" />
                                <span className="text-sm font-medium text-gray-800">{vLabel}</span>
                              </div>
                            </td>
                            <td className="py-2.5 px-4">
                              <p className="font-mono text-xs text-gray-500">{variant.sku || '—'}</p>
                            </td>
                            <td className="py-2.5 px-4" />
                            <td className="py-2.5 px-4 text-right text-sm text-gray-700">
                              ৳{parseFloat(variant.effective_price || variant.price).toLocaleString()}
                            </td>
                            <td className="py-2.5 px-4 text-center text-sm tabular-nums text-gray-700 font-semibold">{vWarehouse}</td>
                            <td className="py-2.5 px-4 text-center text-xs text-gray-400">—</td>
                            <td className="py-2.5 px-4 text-center text-xs text-gray-400">—</td>
                            <td className="py-2.5 px-4 text-center">
                              <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${variant.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                                {variant.is_active ? 'Active' : 'Inactive'}
                              </span>
                            </td>
                            <td className="py-2.5 px-4" />
                          </tr>
                        );
                      })}
                    </Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {!loading && !isError && products.length > 0 && (
          <div className="px-4 py-3 border-t bg-gray-50 text-sm text-gray-500 flex items-center justify-between">
            <span>{productsData?.count || products.length} product{(productsData?.count || products.length) !== 1 ? 's' : ''}</span>
            <span>{products.reduce((sum, p) => sum + (p.variants?.length || 0), 0)} variants on this page</span>
          </div>
        )}
        <Pager page={page} count={productsData?.count} onPage={setPage} />
      </div>
    </AdminLayout>
  );
}
