import { useEffect, useMemo, useRef, useState } from 'react';
import { GripVertical, Plus, Search, Upload, X } from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import { getMediaUrl } from '@/lib/utils';
import {
  useGetCategoriesQuery,
  useCreateCategoryMutation,
  useUpdateCategoryMutation,
  useDeleteCategoryMutation,
  useCreateSubcategoryMutation,
  useUpdateSubcategoryMutation,
  useDeleteSubcategoryMutation,
} from '@/store/api/categoriesApi';

function byOrder(items) {
  return [...items].sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0) || (a.name || '').localeCompare(b.name || ''));
}

function moveItem(items, fromId, toId) {
  const next = [...items];
  const from = next.findIndex((item) => item.id === fromId);
  const to = next.findIndex((item) => item.id === toId);
  if (from < 0 || to < 0 || from === to) return items;
  const [moved] = next.splice(from, 1);
  next.splice(to, 0, moved);
  return next;
}

export default function CategoriesPage() {
  const token = typeof window !== 'undefined' ? localStorage.getItem('admin_access_token') : null;
  const { data: categoriesData, isLoading: loading, error } = useGetCategoriesQuery(undefined, { skip: !token });
  const [createCategory] = useCreateCategoryMutation();
  const [updateCategory] = useUpdateCategoryMutation();
  const [deleteCategory] = useDeleteCategoryMutation();
  const [createSubcategory] = useCreateSubcategoryMutation();
  const [updateSubcategory] = useUpdateSubcategoryMutation();
  const [deleteSubcategory] = useDeleteSubcategoryMutation();

  const categories = useMemo(
    () => byOrder(Array.isArray(categoriesData) ? categoriesData : []),
    [categoriesData],
  );

  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [categoryOrder, setCategoryOrder] = useState(null);
  const [subOrder, setSubOrder] = useState(null);
  const [drag, setDrag] = useState(null);
  const [modal, setModal] = useState(null);
  const imageInputRef = useRef(null);
  const bannerInputRef = useRef(null);

  const visibleCategories = (categoryOrder || categories).filter((category) =>
    category.name.toLowerCase().includes(query.trim().toLowerCase())
  );
  const selected = (categoryOrder || categories).find((category) => category.id === selectedId)
    || visibleCategories[0]
    || null;
  const subcategories = byOrder(subOrder || selected?.subcategories || []);

  useEffect(() => {
    if (!selectedId && categories[0]) setSelectedId(categories[0].id);
  }, [categories, selectedId]);

  useEffect(() => {
    setSubOrder(null);
  }, [selected?.id]);

  const emptyCategory = {
    name: '',
    description: '',
    tagline: '',
    display_order: categories.length,
    featured_order: 0,
    is_active: true,
    is_featured: false,
    imageFile: null,
    bannerFile: null,
    imagePreview: null,
    bannerPreview: null,
  };

  const openCategoryModal = (category) => {
    if (!category) {
      setModal({ kind: 'category', ...emptyCategory });
      return;
    }
    setModal({
      kind: 'category',
      id: category.id,
      name: category.name || '',
      description: category.description || '',
      tagline: category.tagline || '',
      display_order: category.display_order || 0,
      featured_order: category.featured_order || 0,
      is_active: category.is_active ?? true,
      is_featured: category.is_featured ?? false,
      imageFile: null,
      bannerFile: null,
      imagePreview: getMediaUrl(category.image),
      bannerPreview: getMediaUrl(category.banner_image),
    });
  };

  const openSubcategoryModal = (subcategory) => {
    if (!selected) return;
    if (!subcategory) {
      setModal({
        kind: 'subcategory',
        name: '',
        imageFile: null,
        imagePreview: null,
      });
      return;
    }
    setModal({
      kind: 'subcategory',
      id: subcategory.id,
      name: subcategory.name || '',
      imageFile: null,
      imagePreview: getMediaUrl(subcategory.image),
    });
  };

  const onFile = (file, field) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onloadend = () => {
      setModal((current) => ({
        ...current,
        [`${field}File`]: file,
        [`${field}Preview`]: reader.result,
      }));
    };
    reader.readAsDataURL(file);
  };

  const saveCategory = async (event) => {
    event.preventDefault();
    const body = new FormData();
    ['name', 'description', 'tagline', 'display_order', 'featured_order'].forEach((key) => {
      body.append(key, modal[key] ?? '');
    });
    body.append('is_active', modal.is_active);
    body.append('is_featured', modal.is_featured);
    if (modal.imageFile) body.append('image', modal.imageFile);
    if (modal.bannerFile) body.append('banner_image', modal.bannerFile);
    try {
      if (modal.id) {
        await updateCategory({ id: modal.id, data: body }).unwrap();
        toast.success('Category updated');
      } else {
        const created = await createCategory(body).unwrap();
        if (created?.id) setSelectedId(created.id);
        toast.success('Category created');
      }
      setModal(null);
    } catch (saveError) {
      toast.error(saveError.data?.detail || 'Failed to save category');
    }
  };

  const saveSubcategory = async (event) => {
    event.preventDefault();
    if (!selected) return;
    const body = new FormData();
    body.append('category', selected.id);
    body.append('name', modal.name);
    body.append('is_active', true);
    body.append('display_order', modal.id ? (subcategories.find((item) => item.id === modal.id)?.display_order ?? 0) : subcategories.length);
    if (modal.imageFile) body.append('image', modal.imageFile);
    try {
      if (modal.id) {
        await updateSubcategory({ id: modal.id, data: body }).unwrap();
        toast.success('Subcategory updated');
      } else {
        await createSubcategory(body).unwrap();
        toast.success('Subcategory created');
      }
      setModal(null);
    } catch (saveError) {
      toast.error(saveError.data?.detail || saveError.data?.name?.[0] || 'Failed to save subcategory');
    }
  };

  const removeCategory = async (category) => {
    if (!confirm(`Delete ${category.name}? Its subcategories will be removed too.`)) return;
    try {
      await deleteCategory(category.id).unwrap();
      if (selectedId === category.id) setSelectedId(null);
      toast.success('Category deleted');
    } catch (deleteError) {
      toast.error(deleteError.data?.detail || 'Failed to delete category');
    }
  };

  const removeSubcategory = async (subcategory) => {
    if (!confirm(`Delete ${subcategory.name}?`)) return;
    try {
      await deleteSubcategory(subcategory.id).unwrap();
      toast.success('Subcategory deleted');
    } catch (deleteError) {
      toast.error(deleteError.data?.detail || 'Failed to delete subcategory');
    }
  };

  const dropCategories = async (targetId) => {
    if (!drag || drag.kind !== 'category' || drag.id === targetId) return;
    const next = moveItem(categoryOrder || categories, drag.id, targetId);
    setCategoryOrder(next);
    setDrag(null);
    try {
      await Promise.all(next.map((item, index) => (
        (item.display_order ?? 0) === index
          ? Promise.resolve()
          : updateCategory({ id: item.id, data: { display_order: index } }).unwrap()
      )));
      setCategoryOrder(null);
    } catch {
      setCategoryOrder(null);
      toast.error('Failed to reorder categories');
    }
  };

  const dropSubcategories = async (targetId) => {
    if (!drag || drag.kind !== 'subcategory' || drag.id === targetId) return;
    const next = moveItem(subOrder || byOrder(selected?.subcategories || []), drag.id, targetId);
    setSubOrder(next);
    setDrag(null);
    try {
      await Promise.all(next.map((item, index) => (
        (item.display_order ?? 0) === index
          ? Promise.resolve()
          : updateSubcategory({ id: item.id, data: { display_order: index } }).unwrap()
      )));
      setSubOrder(null);
    } catch {
      setSubOrder(null);
      toast.error('Failed to reorder subcategories');
    }
  };

  return (
    <AdminLayout title="Categories">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Categories</h1>
          <p className="mt-1 text-sm text-gray-500">Manage categories and nested subcategories</p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search categories..."
              className="input pl-9 sm:w-64"
            />
          </div>
          <button type="button" onClick={() => openCategoryModal(null)} className="btn bg-rose-700 text-white hover:bg-rose-800">
            <Plus className="mr-1 h-4 w-4" /> Add Category
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error.data?.detail || 'Could not load categories'}
        </div>
      )}

      <div className="grid items-start gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <section className="rounded-xl border border-gray-200 bg-white">
          <div className="max-h-[70vh] space-y-2 overflow-y-auto p-3">
            {loading && <p className="p-4 text-sm text-gray-500">Loading categories...</p>}
            {!loading && visibleCategories.length === 0 && (
              <p className="p-4 text-sm text-gray-500">No categories found.</p>
            )}
            {visibleCategories.map((category) => {
              const active = selected?.id === category.id;
              return (
                <div
                  key={category.id}
                  draggable
                  onDragStart={() => setDrag({ kind: 'category', id: category.id })}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={() => dropCategories(category.id)}
                  onClick={() => setSelectedId(category.id)}
                  className={`flex cursor-pointer items-center gap-2 rounded-lg border px-2 py-2 ${active ? 'border-rose-200 bg-rose-50' : 'border-transparent hover:bg-gray-50'}`}
                >
                  <GripVertical className="h-4 w-4 shrink-0 text-gray-300" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-gray-900">{category.name}</p>
                    <p className="truncate text-xs text-gray-400">/{category.slug}</p>
                  </div>
                  <button type="button" onClick={(event) => { event.stopPropagation(); openCategoryModal(category); }} className="rounded px-2 py-1 text-xs text-gray-600 hover:bg-white">Edit</button>
                  <button type="button" onClick={(event) => { event.stopPropagation(); removeCategory(category); }} className="rounded px-2 py-1 text-xs text-rose-600 hover:bg-rose-100">Delete</button>
                </div>
              );
            })}
          </div>
          <p className="border-t border-gray-100 px-4 py-3 text-center text-xs text-sky-600">Drag and drop to reorder categories.</p>
        </section>

        <section className="rounded-xl border border-gray-200 bg-white p-5">
          {!selected ? (
            <p className="text-sm text-gray-500">Select a category to manage its subcategories.</p>
          ) : (
            <>
              <div className="mb-5 flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">{selected.name}</h2>
                  <p className="text-xs text-gray-400">/{selected.slug}</p>
                </div>
                <div className="flex gap-2">
                  <button type="button" onClick={() => openCategoryModal(selected)} className="rounded-md bg-rose-700 px-3 py-1.5 text-xs font-medium text-white">Edit</button>
                  <button type="button" onClick={() => removeCategory(selected)} className="rounded-md bg-rose-700 px-3 py-1.5 text-xs font-medium text-white">Delete</button>
                </div>
              </div>

              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-800">Subcategories ({subcategories.length})</h3>
                <button type="button" onClick={() => openSubcategoryModal(null)} className="rounded-md bg-rose-700 px-3 py-1.5 text-xs font-medium text-white">
                  <Plus className="mr-1 inline h-3.5 w-3.5" /> Add Subcategory
                </button>
              </div>

              <div className="divide-y divide-gray-100">
                {subcategories.length === 0 && (
                  <p className="py-8 text-center text-sm text-gray-500">No subcategories yet. Add Earphone, Charger, or whatever belongs under {selected.name}.</p>
                )}
                {subcategories.map((subcategory) => (
                  <div
                    key={subcategory.id}
                    draggable
                    onDragStart={() => setDrag({ kind: 'subcategory', id: subcategory.id })}
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={() => dropSubcategories(subcategory.id)}
                    className="flex items-center gap-3 py-3"
                  >
                    <GripVertical className="h-4 w-4 shrink-0 text-gray-300" />
                    {subcategory.image ? (
                      <img src={getMediaUrl(subcategory.image)} alt="" className="h-10 w-10 rounded-md object-cover" />
                    ) : (
                      <span className="h-10 w-10 rounded-md bg-gray-100" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-gray-900">{subcategory.name}</p>
                      <p className="truncate text-xs text-gray-400">/{subcategory.slug}</p>
                    </div>
                    <button type="button" onClick={() => openSubcategoryModal(subcategory)} className="rounded px-2 py-1 text-xs text-gray-600 hover:bg-gray-100">Edit</button>
                    <button type="button" onClick={() => removeSubcategory(subcategory)} className="rounded px-2 py-1 text-xs text-rose-600 hover:bg-rose-50">Delete</button>
                  </div>
                ))}
              </div>
              <p className="mt-4 text-center text-xs text-sky-600">Drag and drop to reorder subcategories.</p>
            </>
          )}
        </section>
      </div>

      {modal?.kind === 'category' && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/40 p-4">
          <form onSubmit={saveCategory} className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl bg-white p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">{modal.id ? 'Edit category' : 'Add category'}</h2>
              <button type="button" onClick={() => setModal(null)} aria-label="Close"><X className="h-5 w-5" /></button>
            </div>
            <label className="mb-3 block text-sm font-medium text-gray-700">
              Name
              <input required value={modal.name} onChange={(event) => setModal({ ...modal, name: event.target.value })} className="input mt-1" />
            </label>
            <label className="mb-3 block text-sm font-medium text-gray-700">
              Description
              <textarea value={modal.description} onChange={(event) => setModal({ ...modal, description: event.target.value })} className="input mt-1" rows={3} />
            </label>
            <label className="mb-3 block text-sm font-medium text-gray-700">
              Tagline
              <input value={modal.tagline} onChange={(event) => setModal({ ...modal, tagline: event.target.value })} className="input mt-1" />
            </label>
            <div className="mb-3">
              <p className="mb-1 text-sm font-medium text-gray-700">Cover image</p>
              <div className="flex items-center gap-3">
                {modal.imagePreview && <img src={modal.imagePreview} alt="" className="h-16 w-16 rounded-md object-cover" />}
                <input ref={imageInputRef} type="file" accept="image/*" className="hidden" onChange={(event) => onFile(event.target.files[0], 'image')} />
                <button type="button" onClick={() => imageInputRef.current?.click()} className="btn btn-secondary"><Upload className="mr-2 h-4 w-4" />Upload</button>
              </div>
            </div>
            <div className="mb-3">
              <p className="mb-1 text-sm font-medium text-gray-700">Banner image</p>
              <div className="flex items-center gap-3">
                {modal.bannerPreview && <img src={modal.bannerPreview} alt="" className="h-16 w-28 rounded-md object-cover" />}
                <input ref={bannerInputRef} type="file" accept="image/*" className="hidden" onChange={(event) => onFile(event.target.files[0], 'banner')} />
                <button type="button" onClick={() => bannerInputRef.current?.click()} className="btn btn-secondary"><Upload className="mr-2 h-4 w-4" />Upload</button>
              </div>
            </div>
            <div className="mb-4 flex gap-6 text-sm">
              <label className="flex items-center gap-2"><input type="checkbox" checked={modal.is_active} onChange={(event) => setModal({ ...modal, is_active: event.target.checked })} />Active</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={modal.is_featured} onChange={(event) => setModal({ ...modal, is_featured: event.target.checked })} />Featured</label>
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setModal(null)} className="btn btn-secondary">Cancel</button>
              <button type="submit" className="btn bg-rose-700 text-white hover:bg-rose-800">{modal.id ? 'Update' : 'Create'}</button>
            </div>
          </form>
        </div>
      )}

      {modal?.kind === 'subcategory' && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/40 p-4">
          <form onSubmit={saveSubcategory} className="w-full max-w-md rounded-xl bg-white p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">{modal.id ? 'Edit subcategory' : `Add subcategory under ${selected?.name}`}</h2>
              <button type="button" onClick={() => setModal(null)} aria-label="Close"><X className="h-5 w-5" /></button>
            </div>
            <label className="mb-4 block text-sm font-medium text-gray-700">
              Name
              <input required value={modal.name} onChange={(event) => setModal({ ...modal, name: event.target.value })} className="input mt-1" placeholder="Earphone, Charger..." />
            </label>
            <div className="mb-5">
              <p className="mb-1 text-sm font-medium text-gray-700">Cover image</p>
              <div className="flex items-center gap-3">
                {modal.imagePreview && <img src={modal.imagePreview} alt="" className="h-16 w-16 rounded-md object-cover" />}
                <input ref={imageInputRef} type="file" accept="image/*" className="hidden" onChange={(event) => onFile(event.target.files[0], 'image')} />
                <button type="button" onClick={() => imageInputRef.current?.click()} className="btn btn-secondary"><Upload className="mr-2 h-4 w-4" />Upload</button>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setModal(null)} className="btn btn-secondary">Cancel</button>
              <button type="submit" className="btn bg-rose-700 text-white hover:bg-rose-800">{modal.id ? 'Update' : 'Create'}</button>
            </div>
          </form>
        </div>
      )}
    </AdminLayout>
  );
}
