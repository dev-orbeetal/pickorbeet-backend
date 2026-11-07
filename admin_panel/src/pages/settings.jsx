import { useState, useEffect } from 'react';
import { Settings, Save, Search, MapPin, Phone, Mail, Clock, Map, Tag, Loader2, Truck, Plus, Trash2, X, GripVertical, Upload, Image as ImageIcon, BadgeCheck } from 'lucide-react';
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

export default function SettingsPage() {
  const { data: settings, isLoading } = useGetStoreSettingsQuery();
  const [updateSettings, { isLoading: saving }] = useUpdateStoreSettingsMutation();
  const { data: bannersRaw } = useGetBannersQuery();
  const [createBanner, { isLoading: creatingBanner }] = useCreateBannerMutation();
  const [updateBanner] = useUpdateBannerMutation();
  const [deleteBanner] = useDeleteBannerMutation();
  const [directoryBannerFile, setDirectoryBannerFile] = useState(null);
  const [directoryBannerPreview, setDirectoryBannerPreview] = useState(null);
  const [uploadingDirectoryBanner, setUploadingDirectoryBanner] = useState(false);
  const [clearingDirectoryBanner, setClearingDirectoryBanner] = useState(false);
  const [slideForm, setSlideForm] = useState({ title: '', link: '', image: null, preview: '' });
  const [sideForm, setSideForm] = useState({ title: '', link: '', image: null, preview: '' });

  const [formData, setFormData] = useState({
    popular_searches: '',
    contact_address: '',
    contact_phone_1: '',
    contact_phone_2: '',
    contact_email_1: '',
    contact_email_2: '',
    business_hours: '',
    map_embed_url: '',
    official_badge_size: 'medium',
    official_badge_color: '#2864E8',
    official_badge_position: 'top-left',
  });

  useEffect(() => {
    if (settings) {
      setFormData({
        popular_searches: settings.popular_searches || '',
        contact_address: settings.contact_address || '',
        contact_phone_1: settings.contact_phone_1 || '',
        contact_phone_2: settings.contact_phone_2 || '',
        contact_email_1: settings.contact_email_1 || '',
        contact_email_2: settings.contact_email_2 || '',
        business_hours: settings.business_hours || '',
        map_embed_url: settings.map_embed_url || '',
        official_badge_size: settings.official_badge_size || 'medium',
        official_badge_color: settings.official_badge_color || '#2864E8',
        official_badge_position: settings.official_badge_position || 'top-left',
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

  const handleDirectoryBannerFile = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setDirectoryBannerFile(file);
    const reader = new FileReader();
    reader.onloadend = () => setDirectoryBannerPreview(reader.result);
    reader.readAsDataURL(file);
  };

  const handleDirectoryBannerUpload = async () => {
    if (!directoryBannerFile) return;
    const body = new FormData();
    body.append('default_directory_banner', directoryBannerFile);
    setUploadingDirectoryBanner(true);
    try {
      await updateSettings(body).unwrap();
      setDirectoryBannerFile(null);
      setDirectoryBannerPreview(null);
      toast.success('Directory banner updated');
    } catch (err) {
      toast.error(err?.data?.detail || 'Failed to upload directory banner');
    } finally {
      setUploadingDirectoryBanner(false);
    }
  };

  const handleDirectoryBannerClear = async () => {
    const body = new FormData();
    body.append('clear_default_directory_banner', 'true');
    setClearingDirectoryBanner(true);
    try {
      await updateSettings(body).unwrap();
      setDirectoryBannerFile(null);
      setDirectoryBannerPreview(null);
      toast.success('Directory banner cleared');
    } catch (err) {
      toast.error(err?.data?.detail || 'Failed to clear directory banner');
    } finally {
      setClearingDirectoryBanner(false);
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
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-1">
              <ImageIcon className="w-5 h-5 text-primary-600" />
              Default directory banner
            </h2>
            <p className="text-sm text-gray-500 mb-4">
              Hero image for pages like Products, categories, and Home &gt; page lists when that page has no
              category or section banner of its own. Leave empty to keep the blue–orange gradient.
            </p>
            <div className="flex flex-wrap items-start gap-4">
              {directoryBannerPreview || settings?.default_directory_banner ? (
                <img
                  src={directoryBannerPreview || getMediaUrl(settings.default_directory_banner)}
                  alt="Default directory banner"
                  className="h-28 w-48 rounded-lg object-cover bg-gray-100"
                />
              ) : (
                <div className="flex h-28 w-48 items-center justify-center rounded-lg bg-gradient-to-br from-[#2F6BFF] via-[#5B8CFF] to-[#FF8A3D] text-xs font-medium text-white">
                  Gradient fallback
                </div>
              )}
              <div>
                <input
                  id="directory-banner"
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={handleDirectoryBannerFile}
                />
                <label htmlFor="directory-banner" className="btn btn-secondary cursor-pointer">
                  <Upload className="w-4 h-4 mr-2" /> Choose image
                </label>
                <button
                  type="button"
                  onClick={handleDirectoryBannerUpload}
                  disabled={!directoryBannerFile || uploadingDirectoryBanner}
                  className="btn bg-primary-600 text-white hover:bg-primary-700 ml-2"
                >
                  {uploadingDirectoryBanner ? 'Uploading...' : 'Upload banner'}
                </button>
                {(settings?.default_directory_banner || directoryBannerPreview) && (
                  <button
                    type="button"
                    onClick={handleDirectoryBannerClear}
                    disabled={clearingDirectoryBanner}
                    className="btn btn-secondary ml-2 text-red-600"
                  >
                    {clearingDirectoryBanner ? 'Clearing...' : 'Clear'}
                  </button>
                )}
                <p className="mt-2 text-xs text-gray-500">
                  Wide landscape image works best (about 2:1). Category and homepage-section banners still override this.
                </p>
              </div>
            </div>
          </div>

          <OfficialBadgeSettings formData={formData} onChange={handleChange} />

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

          <DeliveryChargesSettings settings={settings} onSave={updateSettings} />

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
                  placeholder="+8801819217424"
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
                  placeholder="+8801819217424"
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
                  placeholder="support@pickorbeet.com"
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
                  placeholder="support@pickorbeet.com"
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

const chargeText = (value, fallback) => String(Number(value ?? fallback));

function DeliveryChargesSettings({ settings, onSave }) {
  const savedInside = chargeText(settings?.delivery_charge_inside_dhaka, 70);
  const savedOutside = chargeText(settings?.delivery_charge_outside_dhaka, 125);
  const [inside, setInside] = useState(savedInside);
  const [outside, setOutside] = useState(savedOutside);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setInside(savedInside);
    setOutside(savedOutside);
  }, [savedInside, savedOutside]);

  const valid = (value) => value !== '' && Number(value) >= 0 && Number(value) <= 10000;
  const changed = inside !== savedInside || outside !== savedOutside;

  const save = async (event) => {
    event.preventDefault();
    if (!valid(inside) || !valid(outside)) {
      toast.error('Enter a delivery charge between 0 and 10,000 taka.');
      return;
    }
    setSaving(true);
    try {
      await onSave({ delivery_charge_inside_dhaka: inside, delivery_charge_outside_dhaka: outside }).unwrap();
      toast.success('Delivery charges saved');
    } catch (err) {
      toast.error(err?.data?.detail || 'Failed to save delivery charges');
    } finally {
      setSaving(false);
    }
  };

  const field = (label, hint, value, onChange) => (
    <label className="block">
      <span className="block text-sm font-medium text-gray-700 mb-1">{label}</span>
      <div className="relative">
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">৳</span>
        <input
          type="number"
          min="0"
          max="10000"
          step="1"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full pl-7 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          required
        />
      </div>
      <span className="block text-xs text-gray-500 mt-1">{hint}</span>
    </label>
  );

  return (
    <form onSubmit={save} className="bg-white rounded-xl shadow-sm border p-6">
      <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-1">
        <Truck className="w-5 h-5 text-primary-600" />
        Delivery charges
      </h2>
      <p className="text-sm text-gray-500 mb-4">
        Checkout charges one of these by the delivery district. New orders use the new amounts; placed orders keep theirs.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        {field('Inside Dhaka', 'Addresses in Dhaka district', inside, setInside)}
        {field('Outside Dhaka', 'Every other district, including Gazipur and Narayanganj', outside, setOutside)}
      </div>
      <div className="mt-4 flex justify-end">
        <button
          type="submit"
          disabled={saving || !changed}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors text-sm font-medium"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          {saving ? 'Saving...' : 'Save delivery charges'}
        </button>
      </div>
    </form>
  );
}

const BADGE_SIZES = [
  { id: 'small', label: 'Small' },
  { id: 'medium', label: 'Medium' },
  { id: 'large', label: 'Large' },
];

const BADGE_CORNERS = [
  { id: 'top-left', label: 'Top left', className: 'left-3 top-3', origin: 'origin-top-left' },
  { id: 'top-right', label: 'Top right', className: 'right-3 top-3', origin: 'origin-top-right' },
  { id: 'bottom-left', label: 'Bottom left', className: 'left-3 bottom-3', origin: 'origin-bottom-left' },
  { id: 'bottom-right', label: 'Bottom right', className: 'right-3 bottom-3', origin: 'origin-bottom-right' },
];

const BADGE_SCALE = { small: 'scale-90', medium: 'scale-100', large: 'scale-125' };

function OfficialBadgeSettings({ formData, onChange }) {
  const color = /^#[0-9A-Fa-f]{6}$/.test(formData.official_badge_color)
    ? formData.official_badge_color
    : '#2864E8';
  const corner = BADGE_CORNERS.find((item) => item.id === formData.official_badge_position) || BADGE_CORNERS[0];
  const scale = BADGE_SCALE[formData.official_badge_size] || BADGE_SCALE.medium;

  const setColor = (value) => {
    const next = value.startsWith('#') || value === '' ? value : `#${value}`;
    onChange('official_badge_color', next.toUpperCase());
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border p-6">
      <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-1">
        <BadgeCheck className="w-5 h-5 text-primary-600" />
        Official badge
      </h2>
      <p className="text-sm text-gray-500 mb-5">Shown on official products on the shop and in the app. Save all settings to publish it.</p>
      <div className="grid gap-6 md:grid-cols-[220px_minmax(0,1fr)]">
        <div className="relative h-44 overflow-hidden rounded-xl border border-gray-200 bg-[#F7F9FC]">
          <span className={`absolute ${corner.className} ${scale} ${corner.origin}`}>
            <img
              src="/images/badges/official.png"
              alt="Official"
              className="block h-7 w-auto select-none"
              draggable={false}
            />
          </span>
        </div>
        <div className="space-y-4">
          <div>
            <p className="mb-2 text-sm font-medium text-gray-700">Size</p>
            <div className="flex flex-wrap gap-2">
              {BADGE_SIZES.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onChange('official_badge_size', item.id)}
                  className={`rounded-lg border px-3 py-1.5 text-sm font-medium ${formData.official_badge_size === item.id ? 'border-primary-600 bg-primary-50 text-primary-700' : 'border-gray-200 text-gray-600'}`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-gray-700">Color</p>
            <div className="flex items-center gap-3">
              <input
                type="color"
                aria-label="Official badge color"
                value={color}
                onChange={(event) => setColor(event.target.value)}
                className="h-10 w-14 cursor-pointer rounded border border-gray-200 bg-white p-1"
              />
              <input
                value={formData.official_badge_color}
                onChange={(event) => setColor(event.target.value)}
                aria-label="Official badge hex color"
                maxLength={7}
                className="input w-32 font-mono uppercase"
              />
            </div>
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-gray-700">Position</p>
            <div className="grid grid-cols-2 gap-2 max-w-xs">
              {BADGE_CORNERS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onChange('official_badge_position', item.id)}
                  className={`rounded-lg border px-3 py-2 text-sm font-medium ${formData.official_badge_position === item.id ? 'border-primary-600 bg-primary-50 text-primary-700' : 'border-gray-200 text-gray-600'}`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
