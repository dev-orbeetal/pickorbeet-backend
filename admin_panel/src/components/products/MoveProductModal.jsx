import { useState } from 'react';
import { X } from 'lucide-react';
import toast from 'react-hot-toast';
import { useGetCategoriesQuery } from '@/store/api/categoriesApi';
import { useUpdateProductMutation } from '@/store/api/productsApi';

export default function MoveProductModal({ product, onClose }) {
  const { data: categories = [] } = useGetCategoriesQuery();
  const [updateProduct, { isLoading }] = useUpdateProductMutation();
  const [category, setCategory] = useState(product.category || '');
  const [subcategory, setSubcategory] = useState(product.subcategory || '');

  const destination = categories.find((item) => item.id === category);
  const subcategories = destination?.subcategories || [];
  const unchanged = category === product.category && subcategory === (product.subcategory || '');

  const save = async (event) => {
    event.preventDefault();
    try {
      await updateProduct({ id: product.id, category, subcategory: subcategory || null }).unwrap();
      toast.success(`${product.name} moved`);
      onClose();
    } catch (error) {
      toast.error(error?.data?.subcategory?.[0] || error?.data?.detail || 'Could not move this product');
    }
  };

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/40 p-4">
      <form onSubmit={save} className="w-full max-w-md rounded-xl bg-white p-6">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="min-w-0 truncate text-lg font-semibold">Move {product.name}</h2>
          <button type="button" onClick={onClose} aria-label="Close"><X className="h-5 w-5" /></button>
        </div>
        <p className="mb-4 text-sm text-gray-500">
          Now in {[product.category_name, product.subcategory_name].filter(Boolean).join(' › ')}. Stock, variants, and purchase history stay with the product.
        </p>
        <label className="mb-3 block text-sm font-medium text-gray-700">
          Category
          <select
            required
            value={category}
            onChange={(event) => {
              setCategory(event.target.value);
              setSubcategory('');
            }}
            className="input mt-1"
          >
            <option value="">Select category</option>
            {categories.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>
        </label>
        <label className="mb-5 block text-sm font-medium text-gray-700">
          Subcategory
          <select
            value={subcategory}
            onChange={(event) => setSubcategory(event.target.value)}
            disabled={subcategories.length === 0}
            className="input mt-1 disabled:bg-gray-50 disabled:text-gray-400"
          >
            <option value="">No subcategory</option>
            {subcategories.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>
        </label>
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="btn btn-secondary">Cancel</button>
          <button type="submit" disabled={isLoading || unchanged || !category} className="btn btn-primary">
            {isLoading ? 'Moving…' : 'Move product'}
          </button>
        </div>
      </form>
    </div>
  );
}
