import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useSelector } from 'react-redux';
import {
  ChevronDown, ChevronRight, Edit, FolderPlus, GripVertical, Plus, Search, Trash2, Upload, X,
} from 'lucide-react';
import toast from 'react-hot-toast';
import CatalogProductList from '@/components/products/CatalogProductList';
import MoveProductModal from '@/components/products/MoveProductModal';
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

const VIEW_STORAGE_KEY = 'pickorbeet_catalog_view';
const ICON_ACTION = 'rounded-lg p-1.5 text-gray-500 transition-colors hover:bg-primary-50 hover:text-primary-600';
const COUNT_CHIP = 'shrink-0 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium tabular-nums text-gray-600';

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

function plural(count, noun) {
  return `${count} ${noun}${count === 1 ? '' : 's'}`;
}

function newProductHref(categoryId, subcategoryId) {
  const params = new URLSearchParams({ category: categoryId });
  if (subcategoryId) params.set('subcategory', subcategoryId);
  return `/products/new?${params}`;
}

// Selection and open sections survive a trip to the add or edit product page.
function readView() {
  try {
    return JSON.parse(sessionStorage.getItem(VIEW_STORAGE_KEY)) || {};
  } catch {
    return {};
  }
}

function SectionToggle({ open, label, onClick }) {
  const Icon = open ? ChevronDown : ChevronRight;
  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={open}
      aria-label={`${open ? 'Collapse' : 'Expand'} ${label}`}
      className="rounded p-0.5 text-gray-500 hover:bg-gray-100"
    >
      <Icon className="h-4 w-4" />
    </button>
  );
}

function AddProductLink({ categoryId, subcategoryId, onClick }) {
  return (
    <Link
      href={newProductHref(categoryId, subcategoryId)}
      onClick={onClick}
      className="inline-flex shrink-0 items-center rounded-lg px-2 py-1 text-xs font-medium text-primary-600 hover:bg-primary-50"
    >
      <Plus className="mr-1 h-3.5 w-3.5" />
      Add Product
    </Link>
  );
}

export default function CatalogManager() {
  const role = useSelector((state) => state.auth.user?.role);
  // Accountants work with products here, but categories stay with sellers and admins.
  const canManageCategories = role === 'seller' || role === 'super_admin';
  const { data: categoriesData, isLoading: loading, error } = useGetCategoriesQuery(undefined, { refetchOnFocus: true });
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
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState(() => readView().selectedId || null);
  const [expanded, setExpanded] = useState(() => readView().expanded || {});
  const [categoryOrder, setCategoryOrder] = useState(null);
  const [subOrder, setSubOrder] = useState(null);
  const [drag, setDrag] = useState(null);
  const [modal, setModal] = useState(null);
  const [moving, setMoving] = useState(null);
  const imageInputRef = useRef(null);
  const bannerInputRef = useRef(null);

  const orderedCategories = categoryOrder || categories;
  const selected = orderedCategories.find((category) => category.id === selectedId)
    || orderedCategories[0]
    || null;
  const subcategories = byOrder(subOrder || selected?.subcategories || []);
  const directCount = selected?.direct_product_count ?? 0;

  const term = search.toLowerCase();
  const matchedCategories = term
    ? categories.filter((category) => category.name.toLowerCase().includes(term))
    : [];
  const matchedSubcategories = term
    ? categories.flatMap((category) => byOrder(category.subcategories || [])
      .filter((subcategory) => subcategory.name.toLowerCase().includes(term))
      .map((subcategory) => ({ ...subcategory, parent: category })))
    : [];

  useEffect(() => {
    const timer = setTimeout(() => setSearch(query.trim()), 250);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    setSubOrder(null);
  }, [selected?.id]);

  useEffect(() => {
    try {
      sessionStorage.setItem(VIEW_STORAGE_KEY, JSON.stringify({ selectedId, expanded }));
    } catch {
      // The page works without it; the selection just resets on return.
    }
  }, [selectedId, expanded]);

  const isOpen = (key, fallback = false) => expanded[key] ?? fallback;
  const setOpen = (key, open) => setExpanded((current) => ({ ...current, [key]: open }));

  const openResult = (categoryId, subcategoryId) => {
    setSelectedId(categoryId);
    if (subcategoryId) setOpen(subcategoryId, true);
    setQuery('');
    setSearch('');
  };

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

  const openSubcategoryModal = (category, subcategory) => {
    if (!subcategory) {
      setModal({
        kind: 'subcategory',
        category,
        name: '',
        imageFile: null,
        imagePreview: null,
      });
      return;
    }
    setModal({
      kind: 'subcategory',
      category,
      id: subcategory.id,
      name: subcategory.name || '',
      display_order: subcategory.display_order ?? 0,
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
    const body = new FormData();
    body.append('category', modal.category.id);
    body.append('name', modal.name);
    body.append('is_active', true);
    body.append('display_order', modal.id ? modal.display_order : (modal.category.subcategories || []).length);
    if (modal.imageFile) body.append('image', modal.imageFile);
    try {
      if (modal.id) {
        await updateSubcategory({ id: modal.id, data: body }).unwrap();
        toast.success('Subcategory updated');
      } else {
        await createSubcategory(body).unwrap();
        setSelectedId(modal.category.id);
        toast.success('Subcategory created');
      }
      setModal(null);
    } catch (saveError) {
      toast.error(saveError.data?.detail || saveError.data?.name?.[0] || saveError.data?.non_field_errors?.[0] || 'Failed to save subcategory');
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
    const kept = subcategory.product_count
      ? ` Its ${plural(subcategory.product_count, 'product')} will stay in ${selected?.name} with no subcategory.`
      : '';
    if (!confirm(`Delete ${subcategory.name}?${kept}`)) return;
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

  const showDirect = Boolean(selected) && (directCount > 0 || subcategories.length === 0);
  const directKey = `direct:${selected?.id}`;
  const directOpen = isOpen(directKey, subcategories.length === 0);

  return (
    <>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative sm:w-80">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search categories, subcategories, products..."
            aria-label="Search categories, subcategories, and products"
            className="input pl-9"
          />
        </div>
        {canManageCategories && (
          <button type="button" onClick={() => openCategoryModal(null)} className="btn btn-secondary">
            <Plus className="mr-1 h-4 w-4" /> Add Category
          </button>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error.data?.detail || 'Could not load categories'}
        </div>
      )}

      {term ? (
        <section className="rounded-xl border border-gray-200 bg-white p-5">
          {matchedCategories.length > 0 && (
            <div className="mb-4">
              <h2 className="mb-1 text-sm font-semibold text-gray-800">Categories ({matchedCategories.length})</h2>
              {matchedCategories.map((category) => (
                <button
                  key={category.id}
                  type="button"
                  onClick={() => openResult(category.id)}
                  className="flex w-full items-center justify-between gap-3 rounded-lg px-2 py-1.5 text-left hover:bg-gray-50"
                >
                  <span className="truncate text-sm font-medium text-gray-900">{category.name}</span>
                  <span className={COUNT_CHIP}>{category.product_count}</span>
                </button>
              ))}
            </div>
          )}
          {matchedSubcategories.length > 0 && (
            <div className="mb-4">
              <h2 className="mb-1 text-sm font-semibold text-gray-800">Subcategories ({matchedSubcategories.length})</h2>
              {matchedSubcategories.map((subcategory) => (
                <button
                  key={subcategory.id}
                  type="button"
                  onClick={() => openResult(subcategory.parent.id, subcategory.id)}
                  className="flex w-full items-center justify-between gap-3 rounded-lg px-2 py-1.5 text-left hover:bg-gray-50"
                >
                  <span className="truncate text-sm text-gray-900">
                    <span className="text-gray-500">{subcategory.parent.name} › </span>
                    <span className="font-medium">{subcategory.name}</span>
                  </span>
                  <span className={COUNT_CHIP}>{subcategory.product_count}</span>
                </button>
              ))}
            </div>
          )}
          <h2 className="text-sm font-semibold text-gray-800">Products</h2>
          <CatalogProductList
            params={{ search }}
            showPath
            emptyText={`No products match “${search}”.`}
            onMove={setMoving}
          />
        </section>
      ) : (
        <div className="grid items-start gap-6 lg:grid-cols-[340px_minmax(0,1fr)]">
          <section className="rounded-xl border border-gray-200 bg-white">
            <div className="max-h-[70vh] space-y-1 overflow-y-auto p-2">
              {loading && <p className="p-4 text-sm text-gray-500">Loading categories...</p>}
              {!loading && orderedCategories.length === 0 && (
                <p className="p-4 text-sm text-gray-500">No categories found.</p>
              )}
              {orderedCategories.map((category) => {
                const active = selected?.id === category.id;
                return (
                  <div
                    key={category.id}
                    draggable={canManageCategories}
                    onDragStart={() => setDrag({ kind: 'category', id: category.id })}
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={() => dropCategories(category.id)}
                    onClick={() => setSelectedId(category.id)}
                    className={`flex cursor-pointer items-center gap-1.5 rounded-lg border px-2 py-1.5 ${active ? 'border-primary-200 bg-primary-50' : 'border-transparent hover:bg-gray-50'}`}
                  >
                    {canManageCategories && <GripVertical className="h-4 w-4 shrink-0 text-gray-300" />}
                    <button
                      type="button"
                      aria-current={active ? 'true' : undefined}
                      className="min-w-0 flex-1 truncate text-left text-sm font-medium text-gray-900"
                    >
                      {category.name}
                    </button>
                    <span className={COUNT_CHIP}>{category.product_count}</span>
                    {canManageCategories && (
                      <div className="flex shrink-0 items-center" onClick={(event) => event.stopPropagation()}>
                        <button type="button" onClick={() => openSubcategoryModal(category, null)} className={ICON_ACTION} title="Add subcategory" aria-label={`Add subcategory to ${category.name}`}>
                          <FolderPlus className="h-4 w-4" />
                        </button>
                        <button type="button" onClick={() => openCategoryModal(category)} className={ICON_ACTION} title="Edit category" aria-label={`Edit ${category.name}`}>
                          <Edit className="h-4 w-4" />
                        </button>
                        <button type="button" onClick={() => removeCategory(category)} className={ICON_ACTION} title="Delete category" aria-label={`Delete ${category.name}`}>
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            {canManageCategories && (
              <p className="border-t border-gray-100 px-4 py-2.5 text-center text-xs text-primary-600">Drag and drop to reorder categories.</p>
            )}
          </section>

          <section className="min-w-0 rounded-xl border border-gray-200 bg-white p-5">
            {!selected ? (
              <p className="text-sm text-gray-500">Select a category to manage its subcategories and products.</p>
            ) : (
              <>
                <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="truncate text-lg font-semibold text-gray-900">{selected.name}</h2>
                    <p className="text-xs text-gray-500">
                      {plural(selected.product_count, 'product')} · {subcategories.length} {subcategories.length === 1 ? 'subcategory' : 'subcategories'}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    {canManageCategories && (
                      <button type="button" onClick={() => openSubcategoryModal(selected, null)} className="rounded-md bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-200">
                        <FolderPlus className="mr-1 inline h-3.5 w-3.5" /> Add Subcategory
                      </button>
                    )}
                    <Link href={newProductHref(selected.id)} className="rounded-md bg-primary-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-primary-700">
                      <Plus className="mr-1 inline h-3.5 w-3.5" /> Add Product
                    </Link>
                  </div>
                </div>

                <div className="divide-y divide-gray-100 border-t border-gray-100">
                  {subcategories.map((subcategory) => {
                    const open = isOpen(subcategory.id);
                    return (
                      <div key={subcategory.id}>
                        <div
                          draggable={canManageCategories}
                          onDragStart={() => setDrag({ kind: 'subcategory', id: subcategory.id })}
                          onDragOver={(event) => event.preventDefault()}
                          onDrop={() => dropSubcategories(subcategory.id)}
                          className="flex flex-wrap items-center gap-x-2 gap-y-1 py-2"
                        >
                          {canManageCategories && <GripVertical className="h-4 w-4 shrink-0 text-gray-300" />}
                          <SectionToggle open={open} label={subcategory.name} onClick={() => setOpen(subcategory.id, !open)} />
                          {subcategory.image ? (
                            <img src={getMediaUrl(subcategory.image)} alt="" className="h-8 w-8 rounded-md object-cover" />
                          ) : (
                            <span className="h-8 w-8 rounded-md bg-gray-100" />
                          )}
                          <button
                            type="button"
                            onClick={() => setOpen(subcategory.id, !open)}
                            className="min-w-0 flex-1 basis-24 truncate text-left text-sm font-medium text-gray-900"
                          >
                            {subcategory.name}
                          </button>
                          <span className={COUNT_CHIP}>{subcategory.product_count}</span>
                          <div className="ml-auto flex shrink-0 items-center">
                            <AddProductLink
                              categoryId={selected.id}
                              subcategoryId={subcategory.id}
                              onClick={() => setOpen(subcategory.id, true)}
                            />
                            {canManageCategories && (
                              <>
                                <button type="button" onClick={() => openSubcategoryModal(selected, subcategory)} className={ICON_ACTION} title="Edit subcategory" aria-label={`Edit ${subcategory.name}`}>
                                  <Edit className="h-4 w-4" />
                                </button>
                                <button type="button" onClick={() => removeSubcategory(subcategory)} className={ICON_ACTION} title="Delete subcategory" aria-label={`Delete ${subcategory.name}`}>
                                  <Trash2 className="h-4 w-4" />
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                        {open && (
                          <div className="pb-2 pl-3 sm:pl-12">
                            <CatalogProductList
                              params={{ category: selected.id, subcategory: subcategory.id }}
                              emptyText="No products here yet."
                              onMove={setMoving}
                            />
                          </div>
                        )}
                      </div>
                    );
                  })}

                  {showDirect && (
                    <div>
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 py-2">
                        <SectionToggle open={directOpen} label="products with no subcategory" onClick={() => setOpen(directKey, !directOpen)} />
                        <button
                          type="button"
                          onClick={() => setOpen(directKey, !directOpen)}
                          className="min-w-0 flex-1 basis-24 truncate text-left text-sm font-medium text-gray-700"
                        >
                          No subcategory
                        </button>
                        <span className={COUNT_CHIP}>{directCount}</span>
                        <AddProductLink categoryId={selected.id} onClick={() => setOpen(directKey, true)} />
                      </div>
                      {directOpen && (
                        <div className="pb-2 pl-3 sm:pl-6">
                          <CatalogProductList
                            params={{ category: selected.id, direct: 'true' }}
                            emptyText={`No products directly under ${selected.name} yet.`}
                            onMove={setMoving}
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>
                {canManageCategories && subcategories.length > 1 && (
                  <p className="mt-3 text-center text-xs text-primary-600">Drag and drop to reorder subcategories.</p>
                )}
              </>
            )}
          </section>
        </div>
      )}

      {moving && <MoveProductModal product={moving} onClose={() => setMoving(null)} />}

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
              <button type="submit" className="btn btn-primary">{modal.id ? 'Update' : 'Create'}</button>
            </div>
          </form>
        </div>
      )}

      {modal?.kind === 'subcategory' && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/40 p-4">
          <form onSubmit={saveSubcategory} className="w-full max-w-md rounded-xl bg-white p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">{modal.id ? 'Edit subcategory' : `Add subcategory under ${modal.category.name}`}</h2>
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
              <button type="submit" className="btn btn-primary">{modal.id ? 'Update' : 'Create'}</button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}
