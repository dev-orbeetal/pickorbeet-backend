import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Edit, FolderInput, Layers, Package, Trash2 } from 'lucide-react';
import toast from 'react-hot-toast';
import SupplyBadge from '@/components/products/SupplyBadge';
import LoadError from '@/components/ui/LoadError';
import Pager from '@/components/ui/Pager';
import { useDeleteProductMutation, useGetProductsQuery } from '@/store/api/productsApi';
import { getMediaUrl, stockTotals } from '@/lib/utils';

const ROW_ACTION = 'rounded-lg p-1.5 text-gray-500 transition-colors';

function StockCount({ product }) {
  const { warehouse, dealer, total } = stockTotals(product);
  if (product.supply_type === 'seller_provided' && total === 0) {
    return <SupplyBadge type={product.supply_type} />;
  }
  const tone = total === 0 ? 'text-red-600' : product.is_low_stock ? 'text-amber-600' : 'text-gray-900';
  return (
    <p className="text-right text-sm" title={`Warehouse ${warehouse} · Dealer ${dealer}`}>
      <span className={`font-semibold tabular-nums ${tone}`}>{total.toLocaleString()}</span>
      <span className="text-xs text-gray-400"> in stock</span>
    </p>
  );
}

function ProductRow({ product, showPath, onMove }) {
  const [deleteProduct] = useDeleteProductMutation();
  const variantCount = product.variants?.length || 0;
  const details = [
    showPath && [product.category_name, product.subcategory_name].filter(Boolean).join(' › '),
    product.sku,
    `৳${parseFloat(product.price).toLocaleString()}`,
  ].filter(Boolean);

  const remove = async () => {
    if (!confirm(`Delete ${product.name}?`)) return;
    try {
      await deleteProduct(product.id).unwrap();
      toast.success('Product deleted');
    } catch (error) {
      toast.error(error?.data?.detail || 'Failed to delete product');
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-gray-100">
        {product.primary_image ? (
          <img src={getMediaUrl(product.primary_image)} alt="" className="h-full w-full object-cover" />
        ) : (
          <Package className="h-4 w-4 text-gray-300" />
        )}
      </span>
      <div className="min-w-0 flex-1 basis-40">
        <Link
          href={`/products/${product.id}`}
          className="block truncate text-sm font-medium text-gray-900 hover:text-primary-600"
        >
          {product.name}
        </Link>
        <p className="flex flex-wrap items-center gap-x-2 text-xs text-gray-500">
          <span className="truncate">{details.join(' · ')}</span>
          {variantCount > 0 && (
            <span className="inline-flex items-center gap-1">
              <Layers className="h-3 w-3" />
              {variantCount} variant{variantCount > 1 ? 's' : ''}
            </span>
          )}
          {!product.is_active && (
            <span className="rounded-full bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-500">Inactive</span>
          )}
        </p>
      </div>
      <div className="ml-auto flex items-center gap-2">
        <StockCount product={product} />
        <div className="flex items-center">
          <button
            type="button"
            onClick={() => onMove(product)}
            className={`${ROW_ACTION} hover:bg-primary-50 hover:text-primary-600`}
            title="Move product"
            aria-label={`Move ${product.name}`}
          >
            <FolderInput className="h-4 w-4" />
          </button>
          <Link
            href={`/products/${product.id}`}
            className={`${ROW_ACTION} hover:bg-primary-50 hover:text-primary-600`}
            title="Edit product"
            aria-label={`Edit ${product.name}`}
          >
            <Edit className="h-4 w-4" />
          </Link>
          <button
            type="button"
            onClick={remove}
            className={`${ROW_ACTION} hover:bg-red-50 hover:text-red-600`}
            title="Delete product"
            aria-label={`Delete ${product.name}`}
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

/** Products for one place in the catalog: a subcategory, a category's direct products, or a search. */
export default function CatalogProductList({ params, emptyText, showPath = false, onMove }) {
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, error, refetch } = useGetProductsQuery(
    { ...params, page },
    // Stock also changes from Finance, often in another tab.
    { refetchOnFocus: true, refetchOnMountOrArgChange: true },
  );
  const products = data?.results || [];

  useEffect(() => {
    setPage(1);
  }, [params.category, params.subcategory, params.direct, params.search]);

  useEffect(() => {
    // Deleting or moving the last row on the last page leaves that page empty.
    if (error?.status === 404 && page > 1) setPage(page - 1);
  }, [error, page]);

  if (isLoading) {
    return (
      <div className="space-y-2 py-2">
        {[0, 1].map((row) => <div key={row} className="h-10 animate-pulse rounded-lg bg-gray-100" />)}
      </div>
    );
  }
  if (isError && error?.status !== 404) {
    return <div className="py-2"><LoadError title="Could not load products" onRetry={refetch} /></div>;
  }
  if (products.length === 0) {
    return <p className="py-3 text-sm text-gray-500">{emptyText}</p>;
  }
  return (
    <>
      <div className="divide-y divide-gray-100">
        {products.map((product) => (
          <ProductRow key={product.id} product={product} showPath={showPath} onMove={onMove} />
        ))}
      </div>
      <Pager page={page} count={data?.count} onPage={setPage} />
    </>
  );
}
