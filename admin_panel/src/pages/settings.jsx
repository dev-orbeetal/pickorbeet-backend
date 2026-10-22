import { useState, useEffect } from 'react';
import { Settings, Save, Search, MapPin, Phone, Mail, Clock, Map, Tag, Loader2, Truck, Plus, Edit, Trash2, X, Check, GripVertical, Upload, Image as ImageIcon } from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import { getMediaUrl } from '@/lib/utils';
import {
  useGetStoreSettingsQuery,
  useUpdateStoreSettingsMutation,
  useGetBannersQuery,
  useCreateBannerMutation,
  useUpdateBannerMutation,
  useDeleteBannerMutation,
} from '@/store/api/productsApi';
import {
  useGetDeliveryOptionsQuery,
  useCreateDeliveryOptionMutation,
  useUpdateDeliveryOptionMutation,
  useDeleteDeliveryOptionMutation,
} from '@/store/api/ordersApi';

export default function SettingsPage() {
  const { data: settings, isLoading } = useGetStoreSettingsQuery();
  const [updateSettings, { isLoading: saving }] = useUpdateStoreSettingsMutation();
  const { data: bannersRaw } = useGetBannersQuery();
  const [createBanner, { isLoading: creatingBanner }] = useCreateBannerMutation();
  const [updateBanner] = useUpdateBannerMutation();
  const [deleteBanner] = useDeleteBannerMutation();
  const [logoFile, setLogoFile] = useState(null);
  const [logoPreview, setLogoPreview] = useState(null);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [slideForm, setSlideForm] = useState({ title: '', link: '', image: null, preview: '' });
  const [sideForm, setSideForm] = useState({ title: '', link: '', image: null, preview: '' });

  // Delivery Options
  const { data: deliveryOptionsRaw, isLoading: deliveryLoading } = useGetDeliveryOptionsQuery();
  const [createDeliveryOption] = useCreateDeliveryOptionMutation();
  const [updateDeliveryOption] = useUpdateDeliveryOptionMutation();
  const [deleteDeliveryOption] = useDeleteDeliveryOptionMutation();

  const deliveryOptions = Array.isArray(deliveryOptionsRaw?.results || deliveryOptionsRaw)
    ? (deliveryOptionsRaw?.results || deliveryOptionsRaw)
    : [];

  const [deliveryForm, setDeliveryForm] = useState({ name: '', charge: '', is_active: true });
  const [editingDelivery, setEditingDelivery] = useState(null);
  const [showDeliveryForm, setShowDeliveryForm] = useState(false);

  const handleDeliverySubmit = async (e) => {
    e.preventDefault();
    if (!deliveryForm.name.trim() || deliveryForm.charge === '') return;
    try {
      const payload = { ...deliveryForm, charge: parseFloat(deliveryForm.charge) };
      if (editingDelivery) {
        await updateDeliveryOption({ id: editingDelivery.id, ...payload }).unwrap();
        toast.success('Delivery option updated');
      } else {
        await createDeliveryOption(payload).unwrap();
        toast.success('Delivery option created');
      }
      setDeliveryForm({ name: '', charge: '', is_active: true });
      setEditingDelivery(null);
      setShowDeliveryForm(false);
    } catch (err) {
      toast.error(err?.data?.name?.[0] || err?.data?.detail || 'Failed to save delivery option');
    }
  };

  const handleDeliveryEdit = (option) => {
    setEditingDelivery(option);
    setDeliveryForm({ name: option.name, charge: option.charge, is_active: option.is_active });
    setShowDeliveryForm(true);
  };

  const handleDeliveryDelete = async (id) => {
    if (!confirm('Delete this delivery option?')) return;
    try {
      await deleteDeliveryOption(id).unwrap();
      toast.success('Delivery option deleted');
    } catch (err) {
      toast.error('Failed to delete');
    }
  };

  const handleDeliveryToggle = async (option) => {
    try {
      await updateDeliveryOption({ id: option.id, is_active: !option.is_active }).unwrap();
      toast.success(`${option.name} ${option.is_active ? 'disabled' : 'enabled'}`);
    } catch (err) {
      toast.error('Failed to update');
    }
  };

  const [formData, setFormData] = useState({
    barcode_prefix: '',
    popular_searches: '',
    contact_address: '',
    contact_phone_1: '',
    contact_phone_2: '',
    contact_email_1: '',
    contact_email_2: '',
    business_hours: '',
    map_embed_url: '',
  });

  useEffect(() => {
    if (settings) {
      setFormData({
        barcode_prefix: settings.barcode_prefix || '',
        popular_searches: settings.popular_searches || '',
        contact_address: settings.contact_address || '',
        contact_phone_1: settings.contact_phone_1 || '',
        contact_phone_2: settings.contact_phone_2 || '',
        contact_email_1: settings.contact_email_1 || '',
        contact_email_2: settings.contact_email_2 || '',
        business_hours: settings.business_hours || '',
        map_embed_url: settings.map_embed_url || '',
      });
    }
  }, [settings]);

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    try {
      await updateSettings(formData).unwrap();
      toast.success('Settings saved successfully');
    } catch (error) {
      toast.error(error?.data?.detail || 'Failed to save settings');
    }
  };

  if (isLoading) {
    return (
      <AdminLayout title="Store Settings">
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
        </div>
      </AdminLayout>
    );
  }

  const allBanners = Array.isArray(bannersRaw) ? bannersRaw : bannersRaw?.results || [];
  const banners = allBanners
    .filter((banner) => banner.placement === 'hero')
    .sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0));
  const sideCards = allBanners
    .filter((banner) => banner.placement === 'promo')
    .sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0));

  const handleLogoFile = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setLogoFile(file);
    const reader = new FileReader();
    reader.onloadend = () => setLogoPreview(reader.result);
    reader.readAsDataURL(file);
  };

  const handleLogoUpload = async () => {
    if (!logoFile) return;
    const body = new FormData();
    body.append('logo', logoFile);
    setUploadingLogo(true);
    try {
      await updateSettings(body).unwrap();
      setLogoFile(null);
      toast.success('Logo updated');
    } catch (err) {
      toast.error(err?.data?.detail || 'Failed to upload logo');
    } finally {
      setUploadingLogo(false);
    }
  };

  const handleSlideImage = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onloadend = () => setSlideForm((current) => ({ ...current, image: file, preview: reader.result }));
    reader.readAsDataURL(file);
  };

  const handleSlideCreate = async (event) => {
    event.preventDefault();
    if (!slideForm.image) {
      toast.error('Choose a slide image');
      return;
    }
    const body = new FormData();
    body.append('image', slideForm.image);
    body.append('title', slideForm.title);
    body.append('link', slideForm.link);
    body.append('placement', 'hero');
    body.append('is_active', true);
    body.append('display_order', banners.length);
    try {
      await createBanner(body).unwrap();
      setSlideForm({ title: '', link: '', image: null, preview: '' });
      toast.success('Hero slide added');
    } catch (err) {
      toast.error(err?.data?.detail || err?.data?.image?.[0] || 'Failed to add slide');
    }
  };

  const handleSlideDelete = async (id) => {
    if (!confirm('Delete this image?')) return;
    try {
      await deleteBanner(id).unwrap();
      toast.success('Hero slide deleted');
    } catch {
      toast.error('Failed to delete slide');
    }
  };

  const handleSlideToggle = async (banner) => {
    try {
      await updateBanner({ id: banner.id, data: { is_active: !banner.is_active } }).unwrap();
    } catch {
      toast.error('Failed to update slide');
    }
  };

  const handleSideImage = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onloadend = () => setSideForm((current) => ({ ...current, image: file, preview: reader.result }));
    reader.readAsDataURL(file);
  };

  const handleSideCreate = async (event) => {
    event.preventDefault();
    if (!sideForm.image) {
      toast.error('Choose an image for the right card');
      return;
    }
    const body = new FormData();
    body.append('image', sideForm.image);
    body.append('title', sideForm.title);
    body.append('link', sideForm.link);
    body.append('placement', 'promo');
    body.append('is_active', true);
    body.append('display_order', sideCards.length);
    try {
      await createBanner(body).unwrap();
      setSideForm({ title: '', link: '', image: null, preview: '' });
      toast.success('Right card added');
    } catch (err) {
      toast.error(err?.data?.detail || err?.data?.image?.[0] || 'Failed to add card');
    }
  };

  const handleReplaceImage = async (id, file) => {
    if (!file) return;
    const body = new FormData();
    body.append('image', file);
    try {
      await updateBanner({ id, data: body }).unwrap();
      toast.success('Image replaced');
    } catch {
      toast.error('Failed to replace image');
    }
  };

  const popularList = formData.popular_searches
    ? formData.popular_searches.split(',').map((s) => s.trim()).filter(Boolean)
    : [];

  return (
    <AdminLayout title="Store Settings">
      <div className="max-w-4xl">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Settings className="w-6 h-6 text-primary-600" />
            <h1 className="text-2xl font-bold text-gray-900">Store Settings</h1>
          </div>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-5 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors font-medium"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {saving ? 'Saving...' : 'Save All Settings'}
          </button>
        </div>

        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-4">
              <ImageIcon className="w-5 h-5 text-primary-600" />
              Store logo
            </h2>
            <div className="flex flex-wrap items-center gap-4">
              {logoPreview || settings?.logo ? (
                <img
                  src={logoPreview || settings.logo}
                  alt="Store logo"
                  className="h-16 w-auto rounded-md bg-gray-900 p-2"
                />
              ) : (
                <div className="flex h-16 w-16 items-center justify-center rounded-md bg-gray-100 text-xs text-gray-400">No logo</div>
              )}
              <div>
                <input id="store-logo" type="file" accept="image/*" className="hidden" onChange={handleLogoFile} />
                <label htmlFor="store-logo" className="btn btn-secondary cursor-pointer">
                  <Upload className="w-4 h-4 mr-2" /> Choose logo
                </label>
                <button
                  type="button"
                  onClick={handleLogoUpload}
                  disabled={!logoFile || uploadingLogo}
                  className="btn bg-primary-600 text-white hover:bg-primary-700 ml-2"
                >
                  {uploadingLogo ? 'Uploading...' : 'Upload logo'}
                </button>
                <p className="mt-2 text-xs text-gray-500">Shown in the shop header and footer. A wide transparent PNG works best.</p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-1">Hero slides</h2>
            <p className="text-sm text-gray-500 mb-4">Images for the homepage slider. Use a 3:1 image so it fills the slide.</p>
            <form onSubmit={handleSlideCreate} className="grid gap-3 sm:grid-cols-2 mb-5">
              <input
                value={slideForm.title}
                onChange={(event) => setSlideForm((current) => ({ ...current, title: event.target.value }))}
                placeholder="Title (optional)"
                className="input"
              />
              <input
                value={slideForm.link}
                onChange={(event) => setSlideForm((current) => ({ ...current, link: event.target.value }))}
                placeholder="Link, e.g. /products"
                className="input"
              />
              <div className="sm:col-span-2 flex flex-wrap items-center gap-3">
                <input id="hero-slide" type="file" accept="image/*" className="hidden" onChange={handleSlideImage} />
                <label htmlFor="hero-slide" className="btn btn-secondary cursor-pointer">
                  <Upload className="w-4 h-4 mr-2" /> Slide image
                </label>
                {slideForm.preview && <img src={slideForm.preview} alt="" className="h-14 w-auto rounded-md border" />}
                <button type="submit" disabled={creatingBanner} className="btn bg-primary-600 text-white hover:bg-primary-700">
                  <Plus className="w-4 h-4 mr-1" /> {creatingBanner ? 'Adding...' : 'Add slide'}
                </button>
              </div>
            </form>
            <div className="space-y-3">
              {banners.length === 0 && <p className="text-sm text-gray-500">No hero slides yet.</p>}
              {banners.map((banner) => (
                <div key={banner.id} className="flex items-center gap-3 rounded-lg border border-gray-200 p-2">
                  <img src={getMediaUrl(banner.image)} alt="" className="h-14 w-36 rounded-md object-cover bg-gray-100" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-gray-900">{banner.title || 'Untitled slide'}</p>
                    <p className="truncate text-xs text-gray-400">{banner.link || 'No link'}</p>
                  </div>
                  <button type="button" onClick={() => handleSlideToggle(banner)} className={`text-xs px-2 py-1 rounded ${banner.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                    {banner.is_active ? 'Active' : 'Hidden'}
                  </button>
                  <label className="btn btn-secondary cursor-pointer text-xs">
                    Replace
                    <input type="file" accept="image/*" className="hidden" onChange={(event) => handleReplaceImage(banner.id, event.target.files?.[0])} />
                  </label>
                  <button type="button" onClick={() => handleSlideDelete(banner.id)} className="p-2 text-red-600 hover:bg-red-50 rounded-lg" aria-label="Delete slide">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-1">Right side cards</h2>
            <p className="text-sm text-gray-500 mb-4">The two images beside the hero slider. The first two active cards are shown, top then bottom. Use a 3:1 image.</p>
            <form onSubmit={handleSideCreate} className="grid gap-3 sm:grid-cols-2 mb-5">
              <input
                value={sideForm.title}
                onChange={(event) => setSideForm((current) => ({ ...current, title: event.target.value }))}
                placeholder="Title (optional)"
                className="input"
              />
              <input
                value={sideForm.link}
                onChange={(event) => setSideForm((current) => ({ ...current, link: event.target.value }))}
                placeholder="Link, e.g. /products"
                className="input"
              />
              <div className="sm:col-span-2 flex flex-wrap items-center gap-3">
                <input id="side-card" type="file" accept="image/*" className="hidden" onChange={handleSideImage} />
                <label htmlFor="side-card" className="btn btn-secondary cursor-pointer">
                  <Upload className="w-4 h-4 mr-2" /> Card image
                </label>
                {sideForm.preview && <img src={sideForm.preview} alt="" className="h-14 w-auto rounded-md border" />}
                <button type="submit" disabled={creatingBanner} className="btn bg-primary-600 text-white hover:bg-primary-700">
                  <Plus className="w-4 h-4 mr-1" /> {creatingBanner ? 'Adding...' : 'Add right card'}
                </button>
              </div>
            </form>
            <div className="space-y-3">
              {sideCards.length === 0 && <p className="text-sm text-gray-500">No right-side cards yet.</p>}
              {sideCards.map((banner, index) => (
                <div key={banner.id} className="flex items-center gap-3 rounded-lg border border-gray-200 p-2">
                  <img src={getMediaUrl(banner.image)} alt="" className="h-14 w-36 rounded-md object-cover bg-gray-100" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-gray-900">{banner.title || 'Untitled card'}</p>
                    <p className="truncate text-xs text-gray-400">{index === 0 ? 'Top card' : index === 1 ? 'Bottom card' : 'Hidden until the ones above are removed'}{banner.link ? ` · ${banner.link}` : ''}</p>
                  </div>
                  <button type="button" onClick={() => handleSlideToggle(banner)} className={`text-xs px-2 py-1 rounded ${banner.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                    {banner.is_active ? 'Active' : 'Hidden'}
                  </button>
                  <label className="btn btn-secondary cursor-pointer text-xs">
                    Replace
                    <input type="file" accept="image/*" className="hidden" onChange={(event) => handleReplaceImage(banner.id, event.target.files?.[0])} />
                  </label>
                  <button type="button" onClick={() => handleSlideDelete(banner.id)} className="p-2 text-red-600 hover:bg-red-50 rounded-lg" aria-label="Delete card">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Barcode Settings */}
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-4">
              <Tag className="w-5 h-5 text-primary-600" />
              Barcode Settings
            </h2>
            <div className="max-w-xs">
              <label className="block text-sm font-medium text-gray-700 mb-1">Barcode Prefix</label>
              <input
                type="text"
                value={formData.barcode_prefix}
                onChange={(e) => handleChange('barcode_prefix', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                placeholder="ZZ"
              />
              <p className="text-xs text-gray-500 mt-1">Prefix used for auto-generated product barcodes</p>
            </div>
          </div>

          {/* Delivery Options */}
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <Truck className="w-5 h-5 text-primary-600" />
                Delivery Options
              </h2>
              <button
                onClick={() => { setShowDeliveryForm(true); setEditingDelivery(null); setDeliveryForm({ name: '', charge: '', is_active: true }); }}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-primary-600 bg-primary-50 rounded-lg hover:bg-primary-100 transition-colors"
              >
                <Plus className="w-4 h-4" />
                Add Option
              </button>
            </div>

            {/* Add/Edit Form */}
            {showDeliveryForm && (
              <form onSubmit={handleDeliverySubmit} className="mb-4 p-4 bg-gray-50 rounded-xl border border-gray-200">
                <div className="flex items-center gap-3 mb-3">
                  <p className="text-sm font-medium text-gray-700">
                    {editingDelivery ? 'Edit Delivery Option' : 'New Delivery Option'}
                  </p>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">Name</label>
                    <input
                      type="text"
                      value={deliveryForm.name}
                      onChange={(e) => setDeliveryForm({ ...deliveryForm, name: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                      placeholder="Inside Dhaka"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">Charge (৳)</label>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={deliveryForm.charge}
                      onChange={(e) => setDeliveryForm({ ...deliveryForm, charge: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                      placeholder="60"
                      required
                    />
                  </div>
                  <div className="flex items-end gap-2">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={deliveryForm.is_active}
                        onChange={(e) => setDeliveryForm({ ...deliveryForm, is_active: e.target.checked })}
                        className="w-4 h-4 text-primary-600 rounded focus:ring-primary-500"
                      />
                      <span className="text-sm text-gray-700">Active</span>
                    </label>
                  </div>
                </div>
                <div className="flex justify-end gap-2 mt-3">
                  <button
                    type="button"
                    onClick={() => { setShowDeliveryForm(false); setEditingDelivery(null); }}
                    className="px-3 py-1.5 text-sm text-gray-600 bg-white border rounded-lg hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-1.5 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700"
                  >
                    {editingDelivery ? 'Update' : 'Create'}
                  </button>
                </div>
              </form>
            )}

            {/* Options List */}
            {deliveryLoading ? (
              <div className="flex justify-center py-6">
                <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
              </div>
            ) : deliveryOptions.length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                <Truck className="w-10 h-10 mx-auto mb-2 opacity-40" />
                <p className="text-sm">No delivery options yet. Add one to get started.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {deliveryOptions.map((opt) => (
                  <div
                    key={opt.id}
                    className={`flex items-center justify-between px-4 py-3 rounded-xl border transition-all ${opt.is_active
                        ? 'bg-white border-gray-200 hover:border-primary-200 hover:shadow-sm'
                        : 'bg-gray-50 border-gray-100 opacity-60'
                      }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-2 h-2 rounded-full ${opt.is_active ? 'bg-green-500' : 'bg-gray-300'}`} />
                      <div>
                        <p className="font-medium text-gray-900 text-sm">{opt.name}</p>
                        <p className="text-xs text-gray-500">{opt.is_active ? 'Active' : 'Inactive'}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-lg font-bold text-primary-600">৳{parseFloat(opt.charge).toLocaleString()}</span>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleDeliveryToggle(opt)}
                          className={`p-1.5 rounded-lg transition-colors ${opt.is_active
                              ? 'text-green-600 hover:bg-green-50'
                              : 'text-gray-400 hover:bg-gray-100'
                            }`}
                          title={opt.is_active ? 'Disable' : 'Enable'}
                        >
                          <Check className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDeliveryEdit(opt)}
                          className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDeliveryDelete(opt.id)}
                          className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <p className="text-xs text-gray-400 mt-3">These delivery options appear during checkout for customers to choose from.</p>
          </div>

          {/* Popular Searches */}
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-4">
              <Search className="w-5 h-5 text-primary-600" />
              Popular Searches
            </h2>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Search Terms (comma-separated)
              </label>
              <input
                type="text"
                value={formData.popular_searches}
                onChange={(e) => handleChange('popular_searches', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                placeholder="Borkha, Hijab, Abaya, Niqab"
              />
              <p className="text-xs text-gray-500 mt-1">These appear in the client search modal as quick suggestions</p>
              {popularList.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-3">
                  {popularList.map((term, i) => (
                    <span key={i} className="px-3 py-1 bg-primary-50 text-primary-700 rounded-full text-sm font-medium">
                      {term}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Contact Information */}
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-4">
              <Phone className="w-5 h-5 text-primary-600" />
              Contact Information
            </h2>
            <div className="grid md:grid-cols-2 gap-5">
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  <MapPin className="w-3.5 h-3.5 inline mr-1" />
                  Store Address
                </label>
                <textarea
                  value={formData.contact_address}
                  onChange={(e) => handleChange('contact_address', e.target.value)}
                  rows={2}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder="123 Fashion Street, Gulshan, Dhaka 1212, Bangladesh"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  <Phone className="w-3.5 h-3.5 inline mr-1" />
                  Phone Number 1
                </label>
                <input
                  type="text"
                  value={formData.contact_phone_1}
                  onChange={(e) => handleChange('contact_phone_1', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder="+880 1234-567890"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  <Phone className="w-3.5 h-3.5 inline mr-1" />
                  Phone Number 2
                </label>
                <input
                  type="text"
                  value={formData.contact_phone_2}
                  onChange={(e) => handleChange('contact_phone_2', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder="+880 1234-567891"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  <Mail className="w-3.5 h-3.5 inline mr-1" />
                  Email 1
                </label>
                <input
                  type="email"
                  value={formData.contact_email_1}
                  onChange={(e) => handleChange('contact_email_1', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder="contact@zzuhana.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  <Mail className="w-3.5 h-3.5 inline mr-1" />
                  Email 2
                </label>
                <input
                  type="email"
                  value={formData.contact_email_2}
                  onChange={(e) => handleChange('contact_email_2', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder="support@zzuhana.com"
                />
              </div>
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  <Clock className="w-3.5 h-3.5 inline mr-1" />
                  Business Hours
                </label>
                <textarea
                  value={formData.business_hours}
                  onChange={(e) => handleChange('business_hours', e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder={"Sat - Thu: 10:00 AM - 8:00 PM\nFriday: Closed"}
                />
                <p className="text-xs text-gray-500 mt-1">One entry per line</p>
              </div>
            </div>
          </div>

          {/* Map Embed */}
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-4">
              <Map className="w-5 h-5 text-primary-600" />
              Google Map Embed
            </h2>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Map Embed URL</label>
              <input
                type="text"
                value={formData.map_embed_url}
                onChange={(e) => handleChange('map_embed_url', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
                placeholder="https://www.google.com/maps/embed?pb=..."
              />
              <p className="text-xs text-gray-500 mt-1">
                Paste the embed URL from Google Maps (Share → Embed a map → copy the src URL)
              </p>
              {formData.map_embed_url && (
                <div className="mt-4 rounded-lg overflow-hidden border h-48">
                  <iframe
                    src={formData.map_embed_url}
                    width="100%"
                    height="100%"
                    style={{ border: 0 }}
                    allowFullScreen=""
                    loading="lazy"
                  />
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Bottom Save Button */}
        <div className="mt-6 flex justify-end">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors font-medium"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {saving ? 'Saving...' : 'Save All Settings'}
          </button>
        </div>
      </div>
    </AdminLayout>
  );
}
