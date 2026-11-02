import { useEffect, useMemo, useState } from 'react';
import {
  ArrowDown, ArrowUp, LayoutTemplate, Loader2, Plus, Save, Search, Trash2,
} from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import {
  useGetHomepageSectionsQuery,
  useLazyGetProductsQuery,
  useUpdateHomepageSectionMutation,
} from '@/store/api/productsApi';
import { getMediaUrl } from '@/lib/utils';

const SECTION_HINTS = {
  trending: 'Default: products with “Show in Trending” enabled. Or switch to Custom list to pick exact items and order.',
  'new-arrivals': 'Choose specific new arrivals, or switch to automatic newest-first products.',
};

function SectionEditor({ section }) {
  const [title, setTitle] = useState(section.title || '');
  const [isEnabled, setIsEnabled] = useState(Boolean(section.is_enabled));
  const [itemLimit, setItemLimit] = useState(section.item_limit || 8);
  const [productSource, setProductSource] = useState(section.product_source || 'manual');
  const [viewAllLabel, setViewAllLabel] = useState(section.view_all_label || 'View All');
  const [viewAllUrl, setViewAllUrl] = useState(section.view_all_url || '/products');
  const [products, setProducts] = useState(section.products || []);
  const [bannerFile, setBannerFile] = useState(null);
  const [bannerPreview, setBannerPreview] = useState(() => getMediaUrl(section.banner_image) || '');
  const [clearBanner, setClearBanner] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [updateSection, { isLoading: saving }] = useUpdateHomepageSectionMutation();
  const [searchProducts, { isFetching: searching }] = useLazyGetProductsQuery();

  useEffect(() => {
    setTitle(section.title || '');
    setIsEnabled(Boolean(section.is_enabled));
    setItemLimit(section.item_limit || 8);
    setProductSource(section.product_source || 'manual');
    setViewAllLabel(section.view_all_label || 'View All');
    setViewAllUrl(section.view_all_url || '/products');
    setProducts(section.products || []);
    setBannerFile(null);
    setBannerPreview(getMediaUrl(section.banner_image) || '');
    setClearBanner(false);
  }, [section]);

  const selectedIds = useMemo(() => new Set(products.map((item) => item.id)), [products]);
  const isManual = productSource === 'manual';
  const sourceHint = {
    featured: 'Uses products with “Show in Trending” turned on in the product editor. Toggle products there to control the homepage.',
    latest: 'This row will automatically show the newest active products. Switch to Custom list to pick exact items.',
    on_sale: 'Shows active products that currently have a compare-at price higher than the selling price.',
  }[productSource];

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    try {
      const response = await searchProducts({
        search: searchQuery.trim(),
        page_size: 10,
        is_active: true,
      }).unwrap();
      setSearchResults(response.results || response || []);
    } catch (error) {
      toast.error('Product search failed');
    }
  };

  const addProduct = (product) => {
    if (selectedIds.has(product.id)) {
      toast.error('Already in this list');
      return;
    }
    setProducts((current) => [
      ...current,
      {
        id: product.id,
        name: product.name,
        sku: product.sku,
        price: product.price,
        primary_image: product.primary_image,
        is_active: product.is_active,
        display_order: current.length,
      },
    ]);
    setSearchResults([]);
    setSearchQuery('');
  };

  const removeProduct = (productId) => {
    setProducts((current) => current.filter((item) => item.id !== productId));
  };

  const moveProduct = (index, direction) => {
    setProducts((current) => {
      const next = [...current];
      const target = index + direction;
      if (target < 0 || target >= next.length) return current;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  const onBannerPick = (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setClearBanner(false);
    setBannerFile(file);
    const reader = new FileReader();
    reader.onload = () => setBannerPreview(reader.result);
    reader.readAsDataURL(file);
  };

  const onBannerClear = () => {
    setBannerFile(null);
    setBannerPreview('');
    setClearBanner(Boolean(section.banner_image));
  };

  const handleSave = async () => {
    try {
      const useForm = Boolean(bannerFile) || clearBanner;
      let data;
      if (useForm) {
        data = new FormData();
        data.append('title', title.trim() || section.title);
        data.append('is_enabled', isEnabled ? 'true' : 'false');
        data.append('item_limit', String(Number(itemLimit) || 8));
        data.append('product_source', productSource);
        data.append('view_all_label', viewAllLabel.trim());
        data.append('view_all_url', viewAllUrl.trim() || '/products');
        if (isManual) {
          if (products.length) {
            products.forEach((item) => data.append('product_ids', item.id));
          } else {
            // Explicit empty list for multipart (omit would leave old picks).
            data.append('product_ids', '');
          }
        } else {
          data.append('product_ids', '');
        }
        if (bannerFile) data.append('banner_image', bannerFile);
        if (clearBanner) data.append('clear_banner_image', 'true');
      } else {
        data = {
          title: title.trim() || section.title,
          is_enabled: isEnabled,
          item_limit: Number(itemLimit) || 8,
          product_source: productSource,
          view_all_label: viewAllLabel.trim(),
          view_all_url: viewAllUrl.trim() || '/products',
          product_ids: isManual ? products.map((item) => item.id) : [],
        };
      }
      await updateSection({ key: section.key, data }).unwrap();
      setBannerFile(null);
      setClearBanner(false);
      toast.success(`${title || section.title} saved`);
    } catch (error) {
      const productIdError = error?.data?.product_ids;
      const productMsg = typeof productIdError === 'string'
        ? productIdError
        : productIdError?.[0]
          || (productIdError && typeof productIdError === 'object'
            ? Object.values(productIdError).flat()?.[0]
            : null);
      toast.error(error?.data?.detail || productMsg || 'Failed to save section');
    }
  };

  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-4 border-b bg-gray-50 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-gray-900">{section.title || section.key}</h2>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-white border text-gray-500">{section.key}</span>
          </div>
          <p className="text-sm text-gray-500 mt-1">{SECTION_HINTS[section.key] || 'Customize products shown in this homepage row.'}</p>
        </div>
        <label className="inline-flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={isEnabled}
            onChange={(e) => setIsEnabled(e.target.checked)}
            className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
          />
          Visible on homepage
        </label>
      </div>

      <div className="p-5 space-y-5">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="sm:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">Section title</label>
            <input value={title} onChange={(e) => setTitle(e.target.value)} className="input" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Max products</label>
            <input
              type="number"
              min="1"
              max="24"
              value={itemLimit}
              onChange={(e) => setItemLimit(e.target.value)}
              className="input"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Product source</label>
            <select
              value={productSource}
              onChange={(e) => setProductSource(e.target.value)}
              className="input"
            >
              {section.key === 'trending' && (
                <option value="featured">Products marked Trending</option>
              )}
              <option value="manual">Custom list</option>
              {section.key === 'new-arrivals' && <option value="latest">Newest automatically</option>}
              <option value="on_sale">On sale</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">View all label</label>
            <input value={viewAllLabel} onChange={(e) => setViewAllLabel(e.target.value)} className="input" />
          </div>
          <div className="sm:col-span-2 lg:col-span-3">
            <label className="block text-sm font-medium text-gray-700 mb-1">View all link</label>
            <input value={viewAllUrl} onChange={(e) => setViewAllUrl(e.target.value)} className="input" placeholder="/products" />
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 p-4 space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700">Listing page banner</label>
            <p className="text-xs text-gray-500 mt-1">
              Listing page header — recommended ~2:1 (e.g. 1200×600). Shown at the top of Trending / New Arrivals in the app.
            </p>
          </div>
          {bannerPreview ? (
            <img
              src={bannerPreview}
              alt=""
              className="w-full max-w-xl h-28 rounded-lg object-cover border border-gray-100 bg-gray-50"
            />
          ) : (
            <div className="w-full max-w-xl h-28 rounded-lg border border-dashed border-gray-200 bg-gray-50 flex items-center justify-center text-xs text-gray-400">
              No banner yet — gradient fallback in the app
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <label className="btn btn-secondary cursor-pointer">
              {bannerPreview ? 'Replace image' : 'Upload image'}
              <input type="file" accept="image/jpeg,image/png,image/webp,image/gif" className="sr-only" onChange={onBannerPick} />
            </label>
            {(bannerPreview || section.banner_image) && (
              <button type="button" onClick={onBannerClear} className="btn btn-secondary text-red-600">
                Remove banner
              </button>
            )}
          </div>
        </div>

        {isManual ? (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Add products</label>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        handleSearch();
                      }
                    }}
                    className="input pl-10"
                    placeholder="Search by name, SKU, or barcode"
                  />
                </div>
                <button type="button" onClick={handleSearch} className="btn btn-secondary" disabled={searching}>
                  {searching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                </button>
              </div>
              {searchResults.length > 0 && (
                <div className="mt-2 border rounded-xl overflow-hidden max-h-56 overflow-y-auto">
                  {searchResults.map((product) => (
                    <button
                      key={product.id}
                      type="button"
                      onClick={() => addProduct(product)}
                      disabled={selectedIds.has(product.id)}
                      className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-gray-50 border-b last:border-0 disabled:opacity-40"
                    >
                      {product.primary_image ? (
                        <img src={getMediaUrl(product.primary_image)} alt="" className="w-10 h-10 rounded object-cover" />
                      ) : (
                        <div className="w-10 h-10 rounded bg-gray-100" />
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-gray-900 truncate">{product.name}</p>
                        <p className="text-xs text-gray-500">{product.sku}</p>
                      </div>
                      <Plus className="w-4 h-4 text-primary-600" />
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-gray-900">Selected products ({products.length})</h3>
                {products.length > itemLimit && (
                  <span className="text-xs text-amber-700 bg-amber-50 px-2 py-1 rounded">
                    Only the first {itemLimit} will show on the homepage
                  </span>
                )}
              </div>
              {products.length === 0 ? (
                <div className="rounded-xl border border-dashed border-gray-200 px-4 py-10 text-center text-sm text-gray-500">
                  No products selected yet. Search and add products above.
                </div>
              ) : (
                <div className="space-y-2">
                  {products.map((product, index) => (
                    <div
                      key={product.id}
                      className={`flex items-center gap-3 rounded-xl border px-3 py-2 ${
                        index >= Number(itemLimit) ? 'border-amber-200 bg-amber-50/40' : 'border-gray-200 bg-white'
                      }`}
                    >
                      <span className="w-6 text-xs text-gray-400 font-mono">{index + 1}</span>
                      {product.primary_image ? (
                        <img src={getMediaUrl(product.primary_image)} alt="" className="w-11 h-11 rounded-lg object-cover" />
                      ) : (
                        <div className="w-11 h-11 rounded-lg bg-gray-100" />
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-gray-900 truncate">{product.name}</p>
                        <p className="text-xs text-gray-500">
                          {product.sku || 'No SKU'}
                          {product.price != null ? ` · ৳${parseFloat(product.price).toLocaleString()}` : ''}
                          {product.is_active === false ? ' · Inactive' : ''}
                        </p>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => moveProduct(index, -1)}
                          disabled={index === 0}
                          className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-30"
                          aria-label="Move up"
                        >
                          <ArrowUp className="w-4 h-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => moveProduct(index, 1)}
                          disabled={index === products.length - 1}
                          className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-30"
                          aria-label="Move down"
                        >
                          <ArrowDown className="w-4 h-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => removeProduct(product.id)}
                          className="p-2 rounded-lg text-red-600 hover:bg-red-50"
                          aria-label="Remove"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="rounded-xl border border-blue-100 bg-blue-50 px-4 py-4 text-sm text-blue-900">
            {sourceHint || 'Switch to Custom list to pick exact items.'}
          </div>
        )}

        <div className="flex justify-end pt-2 border-t">
          <button type="button" onClick={handleSave} disabled={saving} className="btn btn-primary">
            {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
            Save {section.title || 'section'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function HomepagePage() {
  const { data, isLoading, error, refetch } = useGetHomepageSectionsQuery();
  const sections = Array.isArray(data) ? data : data?.results || [];

  return (
    <AdminLayout title="Homepage">
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="p-2.5 rounded-xl bg-primary-50 text-primary-700">
            <LayoutTemplate className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-gray-900">Homepage product rows</h1>
            <p className="text-sm text-gray-500">
              Customize Trending and New Arrivals shown on the website and app homepage.
            </p>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="card p-10 text-center text-gray-500">
          <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2" />
          Loading homepage sections…
        </div>
      ) : error ? (
        <div className="card p-8 text-center">
          <p className="text-red-600 font-medium mb-3">Could not load homepage sections.</p>
          <button type="button" onClick={refetch} className="btn btn-secondary">Retry</button>
        </div>
      ) : sections.length === 0 ? (
        <div className="card p-8 text-center text-gray-500">No product sections found.</div>
      ) : (
        <div className="space-y-6">
          {sections.map((section) => (
            <SectionEditor key={section.id || section.key} section={section} />
          ))}
        </div>
      )}
    </AdminLayout>
  );
}
