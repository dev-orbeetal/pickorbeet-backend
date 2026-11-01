import { useMemo, useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import {
  ArrowLeft, Minus, Plus, Search, ShoppingBag, Trash2, X,
} from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import { useCreateManualOrderMutation } from '@/store/api/ordersApi';
import { useLazyGetProductsQuery } from '@/store/api/productsApi';
import { getMediaUrl } from '@/lib/utils';

const INSIDE_DHAKA_CHARGE = 60;
const OUTSIDE_DHAKA_CHARGE = 120;

function isInsideDhaka(city, district) {
  const areas = ['dhaka', 'mirpur', 'uttara', 'gulshan', 'banani', 'dhanmondi', 'mohammadpur'];
  return areas.includes((city || '').trim().toLowerCase())
    || (district || '').trim().toLowerCase() === 'dhaka';
}

export default function CreateManualOrderPage() {
  const router = useRouter();
  const [createManualOrder, { isLoading: saving }] = useCreateManualOrderMutation();
  const [searchProducts] = useLazyGetProductsQuery();

  const [customer, setCustomer] = useState({
    guest_name: '',
    guest_phone: '',
    guest_email: '',
  });
  const [shipping, setShipping] = useState({
    shipping_address_line1: '',
    shipping_address_line2: '',
    shipping_city: 'Dhaka',
    shipping_district: 'Dhaka',
    shipping_postal_code: '',
  });
  const [cart, setCart] = useState([]);
  const [discount, setDiscount] = useState(0);
  const [deliveryOverride, setDeliveryOverride] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('cod');
  const [paymentStatus, setPaymentStatus] = useState('pending');
  const [orderStatus, setOrderStatus] = useState('pending');
  const [source, setSource] = useState('Facebook');
  const [notes, setNotes] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [variantPicker, setVariantPicker] = useState(null);

  const inside = isInsideDhaka(shipping.shipping_city, shipping.shipping_district);
  const autoDelivery = inside ? INSIDE_DHAKA_CHARGE : OUTSIDE_DHAKA_CHARGE;
  const deliveryCharge = deliveryOverride === ''
    ? autoDelivery
    : Math.max(0, parseFloat(deliveryOverride) || 0);

  const subtotal = cart.reduce((sum, item) => sum + item.unit_price * item.quantity, 0);
  const total = Math.max(0, subtotal + deliveryCharge - (parseFloat(discount) || 0));

  const getCartKey = (item) => (item.variant_id ? `${item.id}_${item.variant_id}` : item.id);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const response = await searchProducts({
        search: searchQuery.trim(),
        page_size: 12,
        is_active: true,
      }).unwrap();
      setSearchResults(response.results || response || []);
    } catch (error) {
      toast.error('Search failed');
    } finally {
      setSearching(false);
    }
  };

  const addProduct = (product) => {
    const variants = product.variants || [];
    if (variants.length > 0) {
      setVariantPicker(product);
      return;
    }
    addToCart({
      id: product.id,
      name: product.name,
      sku: product.sku,
      price: parseFloat(product.price),
      primary_image: product.primary_image,
      variant_id: null,
      variant_label: '',
    });
  };

  const addToCart = (product) => {
    const key = getCartKey(product);
    const existing = cart.findIndex((item) => getCartKey(item) === key);
    if (existing > -1) {
      const next = [...cart];
      next[existing].quantity += 1;
      setCart(next);
    } else {
      setCart([
        ...cart,
        {
          ...product,
          quantity: 1,
          unit_price: parseFloat(product.price) || 0,
        },
      ]);
    }
    setSearchResults([]);
    setSearchQuery('');
    setVariantPicker(null);
    toast.success(`${product.name} added`);
  };

  const updateQuantity = (index, change) => {
    const next = [...cart];
    next[index].quantity += change;
    if (next[index].quantity <= 0) next.splice(index, 1);
    setCart(next);
  };

  const updateUnitPrice = (index, value) => {
    const parsed = parseFloat(value);
    const next = [...cart];
    next[index] = {
      ...next[index],
      unit_price: Number.isFinite(parsed) && parsed >= 0 ? parsed : 0,
    };
    setCart(next);
  };

  const removeItem = (index) => {
    const next = [...cart];
    next.splice(index, 1);
    setCart(next);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!customer.guest_name.trim() || !customer.guest_phone.trim()) {
      toast.error('Customer name and phone are required');
      return;
    }
    if (!shipping.shipping_address_line1.trim()) {
      toast.error('Shipping address is required');
      return;
    }
    if (cart.length === 0) {
      toast.error('Add at least one product');
      return;
    }

    try {
      const response = await createManualOrder({
        guest_name: customer.guest_name.trim(),
        guest_phone: customer.guest_phone.trim(),
        guest_email: customer.guest_email.trim(),
        shipping_name: customer.guest_name.trim(),
        shipping_phone: customer.guest_phone.trim(),
        shipping_address_line1: shipping.shipping_address_line1.trim(),
        shipping_address_line2: shipping.shipping_address_line2.trim(),
        shipping_city: shipping.shipping_city.trim(),
        shipping_district: shipping.shipping_district.trim(),
        shipping_postal_code: shipping.shipping_postal_code.trim(),
        items: cart.map((item) => ({
          product_id: item.id,
          variant_id: item.variant_id || null,
          quantity: item.quantity,
          unit_price: item.unit_price,
        })),
        discount: parseFloat(discount) || 0,
        delivery_charge: deliveryCharge,
        payment_method: paymentMethod,
        payment_status: paymentStatus,
        order_status: orderStatus,
        source: source.trim(),
        notes: notes.trim(),
      }).unwrap();

      toast.success(`Order ${response.order.order_number} created`);
      router.push(`/orders/${response.order.id}`);
    } catch (error) {
      const message = error?.data?.error
        || error?.data?.guest_phone?.[0]
        || error?.data?.shipping_phone?.[0]
        || error?.data?.items?.[0]
        || error?.data?.detail
        || 'Failed to create order';
      toast.error(message);
    }
  };

  const sourcePresets = useMemo(
    () => ['Facebook', 'WhatsApp', 'Instagram', 'Phone', 'Other'],
    [],
  );

  return (
    <AdminLayout title="Create Order">
      <div className="mb-6 flex items-center justify-between gap-3">
        <div>
          <Link href="/orders" className="inline-flex items-center text-sm text-gray-500 hover:text-gray-800 mb-2">
            <ArrowLeft className="w-4 h-4 mr-1" /> Back to orders
          </Link>
          <h1 className="text-xl font-semibold text-gray-900">Create custom order</h1>
          <p className="text-sm text-gray-500">
            For Facebook, WhatsApp, phone, or other off-platform sales that need delivery.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="card p-5 space-y-4">
            <h2 className="font-semibold text-gray-900">Customer</h2>
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
                <input
                  className="input"
                  value={customer.guest_name}
                  onChange={(e) => setCustomer({ ...customer, guest_name: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Phone *</label>
                <input
                  className="input"
                  value={customer.guest_phone}
                  onChange={(e) => setCustomer({ ...customer, guest_phone: e.target.value })}
                  placeholder="01XXXXXXXXX"
                  required
                />
              </div>
              <div className="sm:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input
                  type="email"
                  className="input"
                  value={customer.guest_email}
                  onChange={(e) => setCustomer({ ...customer, guest_email: e.target.value })}
                />
              </div>
            </div>
          </div>

          <div className="card p-5 space-y-4">
            <h2 className="font-semibold text-gray-900">Shipping address</h2>
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="sm:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">Address line 1 *</label>
                <input
                  className="input"
                  value={shipping.shipping_address_line1}
                  onChange={(e) => setShipping({ ...shipping, shipping_address_line1: e.target.value })}
                  required
                />
              </div>
              <div className="sm:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">Address line 2</label>
                <input
                  className="input"
                  value={shipping.shipping_address_line2}
                  onChange={(e) => setShipping({ ...shipping, shipping_address_line2: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">City *</label>
                <input
                  className="input"
                  value={shipping.shipping_city}
                  onChange={(e) => setShipping({ ...shipping, shipping_city: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">District *</label>
                <input
                  className="input"
                  value={shipping.shipping_district}
                  onChange={(e) => setShipping({ ...shipping, shipping_district: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Postal code</label>
                <input
                  className="input"
                  value={shipping.shipping_postal_code}
                  onChange={(e) => setShipping({ ...shipping, shipping_postal_code: e.target.value })}
                />
              </div>
              <div className="flex items-end">
                <p className="text-sm text-gray-500 pb-2">
                  Zone: <span className="font-medium text-gray-800">{inside ? 'Inside Dhaka' : 'Outside Dhaka'}</span>
                </p>
              </div>
            </div>
          </div>

          <div className="card p-5 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-semibold text-gray-900">Products</h2>
              <span className="text-sm text-gray-500">{cart.length} item{cart.length === 1 ? '' : 's'}</span>
            </div>

            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  className="input pl-10"
                  placeholder="Search products by name, SKU, barcode…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleSearch();
                    }
                  }}
                />
              </div>
              <button type="button" onClick={handleSearch} className="btn btn-secondary" disabled={searching}>
                {searching ? '…' : 'Search'}
              </button>
            </div>

            {searchResults.length > 0 && (
              <div className="border rounded-xl overflow-hidden max-h-64 overflow-y-auto">
                {searchResults.map((product) => (
                  <button
                    key={product.id}
                    type="button"
                    onClick={() => addProduct(product)}
                    className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-gray-50 border-b last:border-0"
                  >
                    {product.primary_image ? (
                      <img src={getMediaUrl(product.primary_image)} alt="" className="w-10 h-10 rounded object-cover" />
                    ) : (
                      <div className="w-10 h-10 rounded bg-gray-100" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium truncate">{product.name}</p>
                      <p className="text-xs text-gray-500">{product.sku}</p>
                    </div>
                    <p className="text-sm font-semibold text-primary-600">
                      ৳{parseFloat(product.price).toLocaleString()}
                    </p>
                  </button>
                ))}
              </div>
            )}

            {cart.length === 0 ? (
              <div className="rounded-xl border border-dashed border-gray-200 py-12 text-center text-gray-400">
                <ShoppingBag className="w-10 h-10 mx-auto mb-2" />
                <p>Search and add products for this order</p>
              </div>
            ) : (
              <div className="space-y-3">
                {cart.map((item, index) => (
                  <div key={getCartKey(item)} className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
                    {item.primary_image ? (
                      <img src={getMediaUrl(item.primary_image)} alt="" className="w-12 h-12 rounded-lg object-cover" />
                    ) : (
                      <div className="w-12 h-12 rounded-lg bg-gray-200" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium truncate">{item.name}</p>
                      {item.variant_label && (
                        <p className="text-xs text-primary-600">{item.variant_label}</p>
                      )}
                      <div className="mt-1 flex items-center gap-2">
                        <div className="relative w-28">
                          <span className="absolute left-2 top-1/2 -translate-y-1/2 text-xs text-gray-400">৳</span>
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            value={item.unit_price}
                            onChange={(e) => updateUnitPrice(index, e.target.value)}
                            className="input py-1 pl-5 pr-2 text-sm"
                          />
                        </div>
                        {parseFloat(item.price) !== item.unit_price && (
                          <span className="text-xs text-gray-400 line-through">
                            ৳{parseFloat(item.price).toLocaleString()}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button type="button" onClick={() => updateQuantity(index, -1)} className="p-1 bg-white border rounded">
                        <Minus className="w-4 h-4" />
                      </button>
                      <span className="w-8 text-center font-medium">{item.quantity}</span>
                      <button type="button" onClick={() => updateQuantity(index, 1)} className="p-1 bg-white border rounded">
                        <Plus className="w-4 h-4" />
                      </button>
                    </div>
                    <div className="w-24 text-right font-semibold">
                      ৳{(item.unit_price * item.quantity).toLocaleString()}
                    </div>
                    <button type="button" onClick={() => removeItem(index)} className="p-1 text-red-500 hover:bg-red-50 rounded">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="space-y-6">
          <div className="card p-5 space-y-4">
            <h2 className="font-semibold text-gray-900">Order details</h2>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Source</label>
              <div className="flex flex-wrap gap-2 mb-2">
                {sourcePresets.map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    onClick={() => setSource(preset)}
                    className={`px-2.5 py-1 text-xs rounded-full border ${
                      source === preset
                        ? 'bg-primary-600 text-white border-primary-600'
                        : 'bg-white text-gray-600 border-gray-200'
                    }`}
                  >
                    {preset}
                  </button>
                ))}
              </div>
              <input
                className="input"
                value={source}
                onChange={(e) => setSource(e.target.value)}
                placeholder="Facebook / WhatsApp / Phone…"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Payment method</label>
              <select className="input" value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
                <option value="cod">Cash on delivery</option>
                <option value="bkash">bKash</option>
                <option value="nagad">Nagad</option>
                <option value="cash">Cash</option>
                <option value="card">Card</option>
                <option value="mobile_banking">Mobile banking</option>
                <option value="bank_transfer">Bank transfer</option>
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Payment status</label>
                <select className="input" value={paymentStatus} onChange={(e) => setPaymentStatus(e.target.value)}>
                  <option value="pending">Pending</option>
                  <option value="paid">Paid</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Order status</label>
                <select className="input" value={orderStatus} onChange={(e) => setOrderStatus(e.target.value)}>
                  <option value="pending">Pending</option>
                  <option value="confirmed">Confirmed</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Discount</label>
              <input
                type="number"
                min="0"
                step="0.01"
                className="input"
                value={discount}
                onChange={(e) => setDiscount(e.target.value)}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Delivery charge
                <span className="text-gray-400 font-normal"> (auto ৳{autoDelivery})</span>
              </label>
              <input
                type="number"
                min="0"
                step="0.01"
                className="input"
                value={deliveryOverride}
                onChange={(e) => setDeliveryOverride(e.target.value)}
                placeholder={String(autoDelivery)}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
              <textarea
                className="input min-h-[90px]"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Any special instructions…"
              />
            </div>
          </div>

          <div className="card p-5 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">Subtotal</span>
              <span>৳{subtotal.toLocaleString()}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">Delivery</span>
              <span>৳{deliveryCharge.toLocaleString()}</span>
            </div>
            {(parseFloat(discount) || 0) > 0 && (
              <div className="flex justify-between text-sm text-green-600">
                <span>Discount</span>
                <span>-৳{(parseFloat(discount) || 0).toLocaleString()}</span>
              </div>
            )}
            <div className="flex justify-between text-xl font-bold pt-2 border-t">
              <span>Total</span>
              <span className="text-primary-600">৳{total.toLocaleString()}</span>
            </div>
            <button type="submit" disabled={saving || cart.length === 0} className="w-full btn btn-primary py-3 mt-3">
              {saving ? 'Creating…' : 'Create order'}
            </button>
          </div>
        </div>
      </form>

      {variantPicker && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
            <div className="p-5 border-b flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold">Select variant</h2>
                <p className="text-sm text-gray-500">{variantPicker.name}</p>
              </div>
              <button type="button" onClick={() => setVariantPicker(null)} className="p-2 hover:bg-gray-100 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 max-h-80 overflow-y-auto space-y-2">
              {(variantPicker.variants || []).map((variant) => {
                const label = [variant.size, variant.color].filter(Boolean).join(' / ')
                  || variant.label
                  || 'Default';
                const price = parseFloat(variant.effective_price || variant.price || variantPicker.price);
                return (
                  <button
                    key={variant.id}
                    type="button"
                    onClick={() => addToCart({
                      id: variantPicker.id,
                      name: variantPicker.name,
                      sku: variant.sku || variantPicker.sku,
                      price,
                      primary_image: variantPicker.primary_image,
                      variant_id: variant.id,
                      variant_label: label,
                    })}
                    className="w-full flex items-center justify-between p-4 rounded-xl border-2 border-gray-200 hover:border-primary-500 hover:bg-primary-50 text-left"
                  >
                    <div>
                      <p className="font-medium">{label}</p>
                      <p className="text-xs text-gray-500">SKU: {variant.sku || '—'}</p>
                    </div>
                    <p className="font-semibold text-primary-600">৳{price.toLocaleString()}</p>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}
