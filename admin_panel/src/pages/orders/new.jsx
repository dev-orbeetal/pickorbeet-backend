import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import {
  ArrowLeft, Plus, Search, Trash2, X, Package,
} from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import BdAddressFields from '@/components/BdAddressFields';
import { useGetInventoryItemsQuery, useGetStoreSettingsQuery } from '@/store/api/productsApi';
import { useCreateExternalOrderMutation } from '@/store/api/ordersApi';
import { getMediaUrl } from '@/lib/utils';

const emptyCustomer = {
  customer_name: '',
  customer_phone: '',
  customer_email: '',
  shipping_address_line1: '',
  shipping_address_line2: '',
  shipping_division: 'Dhaka',
  shipping_city: '',
  shipping_district: 'Dhaka',
  shipping_post_office: '',
  shipping_postal_code: '',
};

function lineKey(item) {
  return item.variant_id ? `${item.product_id}_${item.variant_id}` : item.product_id;
}

function availableStock(item) {
  return Number(item.warehouse_stock || 0) + Number(item.dealer_stock || 0);
}

export default function NewOrderPage() {
  const router = useRouter();
  const [customer, setCustomer] = useState(emptyCustomer);
  const [lines, setLines] = useState([]);
  const { data: storeSettings } = useGetStoreSettingsQuery();
  const [typedCharge, setTypedCharge] = useState(null);
  const insideDhaka = customer.shipping_district.trim().toLowerCase() === 'dhaka';
  const zoneCharge = insideDhaka
    ? storeSettings?.delivery_charge_inside_dhaka ?? 70
    : storeSettings?.delivery_charge_outside_dhaka ?? 125;
  const deliveryCharge = typedCharge ?? String(Number(zoneCharge));
  const [discount, setDiscount] = useState('0');
  const [paymentMethod, setPaymentMethod] = useState('cod');
  const [orderStatus, setOrderStatus] = useState('confirmed');
  const [paymentStatus, setPaymentStatus] = useState('pending');
  const [notes, setNotes] = useState('');
  const [search, setSearch] = useState('');
  const [variantPicker, setVariantPicker] = useState(null);

  const { data: inventory, isLoading: inventoryLoading } = useGetInventoryItemsQuery({});
  const [createExternalOrder, { isLoading: saving }] = useCreateExternalOrderMutation();

  const products = inventory?.items || [];
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return products.slice(0, 40);
    return products.filter((product) => {
      const hay = `${product.name} ${product.sku || ''} ${product.category || ''}`.toLowerCase();
      return hay.includes(q);
    }).slice(0, 40);
  }, [products, search]);

  const subtotal = lines.reduce((sum, line) => sum + (Number(line.unit_price) || 0) * line.quantity, 0);
  const total = Math.max(0, subtotal + (Number(deliveryCharge) || 0) - (Number(discount) || 0));

  const addProduct = (product, variant = null) => {
    const entry = {
      product_id: product.id,
      variant_id: variant?.id || null,
      name: product.name,
      variant_label: variant
        ? [variant.size, variant.color].filter(Boolean).join(' / ') || variant.sku
        : '',
      sku: variant?.sku || product.sku,
      unit_price: String(variant?.price ?? product.price ?? 0),
      catalog_price: Number(variant?.price ?? product.price ?? 0),
      quantity: 1,
      warehouse_stock: Number(variant?.warehouse_stock ?? product.warehouse_stock ?? 0),
      dealer_stock: Number(variant?.dealer_stock ?? product.dealer_stock ?? 0),
      primary_image: product.primary_image,
    };
    const key = lineKey(entry);
    const existing = lines.findIndex((line) => lineKey(line) === key);
    if (existing >= 0) {
      const next = [...lines];
      next[existing] = { ...next[existing], quantity: next[existing].quantity + 1 };
      setLines(next);
    } else {
      setLines([...lines, entry]);
    }
    setVariantPicker(null);
    setSearch('');
    toast.success(`${entry.name}${entry.variant_label ? ` (${entry.variant_label})` : ''} added`);
  };

  const handlePickProduct = (product) => {
    if (product.has_variants && product.variants?.length) {
      setVariantPicker(product);
      return;
    }
    addProduct(product);
  };

  const updateLine = (index, patch) => {
    setLines((current) => current.map((line, i) => (i === index ? { ...line, ...patch } : line)));
  };

  const removeLine = (index) => {
    setLines((current) => current.filter((_, i) => i !== index));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!customer.customer_name.trim() || !customer.customer_phone.trim()) {
      toast.error('Customer name and phone are required');
      return;
    }
    if (
      !customer.shipping_address_line1.trim()
      || !customer.shipping_division.trim()
      || !customer.shipping_district.trim()
      || !customer.shipping_post_office.trim()
      || !customer.shipping_city.trim()
    ) {
      toast.error('Enter a full delivery address (division, district, post office, city)');
      return;
    }
    if (lines.length === 0) {
      toast.error('Add at least one product');
      return;
    }
    for (const line of lines) {
      if (!(Number(line.unit_price) >= 0)) {
        toast.error(`Enter a selling price for ${line.name}`);
        return;
      }
      if (availableStock(line) < line.quantity) {
        toast.error(`Not enough stock for ${line.name}`);
        return;
      }
    }

    try {
      const result = await createExternalOrder({
        ...customer,
        customer_email: customer.customer_email || '',
        items: lines.map((line) => ({
          product_id: line.product_id,
          variant_id: line.variant_id,
          quantity: line.quantity,
          unit_price: line.unit_price,
        })),
        delivery_charge: deliveryCharge || 0,
        discount: discount || 0,
        payment_method: paymentMethod,
        order_status: orderStatus,
        payment_status: paymentStatus,
        notes,
      }).unwrap();
      toast.success(`Order ${result.order.order_number} created`);
      router.push(`/orders/${result.order.id}`);
    } catch (error) {
      const data = error?.data;
      const message = data?.detail
        || (Array.isArray(data?.items) ? data.items[0] : null)
        || Object.values(data || {}).flat?.()?.[0]
        || 'Could not create the order';
      toast.error(typeof message === 'string' ? message : 'Could not create the order');
    }
  };

  return (
    <AdminLayout title="Add Order">
      <div className="mb-6">
        <Link href="/orders" className="inline-flex items-center gap-1 text-sm text-primary-600 mb-2">
          <ArrowLeft className="w-4 h-4" />
          Back to Orders
        </Link>
        <h1 className="text-2xl font-semibold text-gray-900">Add Order</h1>
        <p className="text-sm text-gray-500 mt-1">
          Create an order for phone, Facebook, or walk-in sales. Stock is deducted normally from available inventory.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 space-y-6">
          <section className="card p-5 space-y-4">
            <h2 className="font-semibold text-gray-900">Customer & delivery</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Customer name" required>
                <input
                  className="input"
                  required
                  value={customer.customer_name}
                  onChange={(e) => setCustomer({ ...customer, customer_name: e.target.value })}
                />
              </Field>
              <Field label="Phone" required>
                <input
                  className="input"
                  required
                  value={customer.customer_phone}
                  onChange={(e) => setCustomer({ ...customer, customer_phone: e.target.value })}
                />
              </Field>
              <Field label="Email" className="sm:col-span-2">
                <input
                  type="email"
                  className="input"
                  value={customer.customer_email}
                  onChange={(e) => setCustomer({ ...customer, customer_email: e.target.value })}
                />
              </Field>
              <Field label="Address line 1" required className="sm:col-span-2">
                <input
                  className="input"
                  required
                  value={customer.shipping_address_line1}
                  onChange={(e) => setCustomer({ ...customer, shipping_address_line1: e.target.value })}
                />
              </Field>
              <Field label="Address line 2" className="sm:col-span-2">
                <input
                  className="input"
                  value={customer.shipping_address_line2}
                  onChange={(e) => setCustomer({ ...customer, shipping_address_line2: e.target.value })}
                />
              </Field>
              <BdAddressFields
                Field={Field}
                value={{
                  division: customer.shipping_division,
                  district: customer.shipping_district,
                  post_office: customer.shipping_post_office,
                  postal_code: customer.shipping_postal_code,
                  city: customer.shipping_city,
                }}
                onChange={(next) => setCustomer({
                  ...customer,
                  shipping_division: next.division || '',
                  shipping_district: next.district || '',
                  shipping_post_office: next.post_office || '',
                  shipping_postal_code: next.postal_code || '',
                  shipping_city: next.city || '',
                })}
              />
            </div>
          </section>

          <section className="card p-5 space-y-4">
            <h2 className="font-semibold text-gray-900">Products</h2>

            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                className="input pl-9"
                placeholder="Search products by name or SKU"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>

            <div className="max-h-56 overflow-y-auto divide-y border rounded-lg">
              {inventoryLoading ? (
                <p className="p-4 text-sm text-gray-500">Loading catalog…</p>
              ) : filtered.length === 0 ? (
                <p className="p-4 text-sm text-gray-500">No products match.</p>
              ) : filtered.map((product) => (
                <button
                  key={product.id}
                  type="button"
                  onClick={() => handlePickProduct(product)}
                  className="w-full text-left px-3 py-2.5 hover:bg-gray-50 flex items-center gap-3"
                >
                  <div className="w-10 h-10 rounded bg-gray-100 overflow-hidden flex-shrink-0">
                    {product.primary_image ? (
                      <img src={getMediaUrl(product.primary_image)} alt="" className="w-full h-full object-cover" />
                    ) : (
                      <Package className="w-5 h-5 m-2.5 text-gray-400" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-900 truncate">{product.name}</p>
                    <p className="text-xs text-gray-500">
                      ৳{Number(product.price).toLocaleString()} · Stock{' '}
                      {(Number(product.warehouse_stock || 0) + Number(product.dealer_stock || 0))}
                      {product.has_variants ? ' · has variants' : ''}
                    </p>
                  </div>
                  <Plus className="w-4 h-4 text-primary-600" />
                </button>
              ))}
            </div>

            <div className="overflow-x-auto border rounded-lg">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    {['Product', 'Selling price', 'Qty', 'Stock', ''].map((heading) => (
                      <th key={heading || 'x'} className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">{heading}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {lines.length === 0 ? (
                    <tr>
                      <td colSpan="5" className="px-3 py-8 text-center text-sm text-gray-500">
                        No products yet. Search and add items above.
                      </td>
                    </tr>
                  ) : lines.map((line, index) => (
                    <tr key={lineKey(line)}>
                      <td className="px-3 py-3 text-sm">
                        <p className="font-medium text-gray-900">{line.name}</p>
                        {line.variant_label ? <p className="text-xs text-gray-500">{line.variant_label}</p> : null}
                        <p className="text-xs text-gray-400">Listed ৳{Number(line.catalog_price).toLocaleString()}</p>
                      </td>
                      <td className="px-3 py-3">
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          className="input w-28"
                          value={line.unit_price}
                          onChange={(e) => updateLine(index, { unit_price: e.target.value })}
                        />
                      </td>
                      <td className="px-3 py-3">
                        <input
                          type="number"
                          min="1"
                          className="input w-20"
                          value={line.quantity}
                          onChange={(e) => updateLine(index, { quantity: Math.max(1, parseInt(e.target.value, 10) || 1) })}
                        />
                      </td>
                      <td className="px-3 py-3 text-sm">
                        <span className={availableStock(line) < line.quantity ? 'text-red-600 font-medium' : 'text-gray-700'}>
                          {availableStock(line)}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-right">
                        <button type="button" onClick={() => removeLine(index)} className="text-red-600 p-1" aria-label="Remove">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <div className="space-y-6">
          <section className="card p-5 space-y-4">
            <h2 className="font-semibold text-gray-900">Order settings</h2>
            <Field label="Order status">
              <select className="input" value={orderStatus} onChange={(e) => setOrderStatus(e.target.value)}>
                <option value="pending">Pending</option>
                <option value="confirmed">Confirmed</option>
                <option value="processing">Processing</option>
                <option value="shipped">Shipped</option>
                <option value="out_for_delivery">Out for delivery</option>
                <option value="delivered">Delivered</option>
              </select>
            </Field>
            <Field label="Payment status">
              <select className="input" value={paymentStatus} onChange={(e) => setPaymentStatus(e.target.value)}>
                <option value="pending">Pending</option>
                <option value="paid">Paid</option>
                <option value="failed">Failed</option>
              </select>
            </Field>
            <Field label="Payment method">
              <select className="input" value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
                <option value="cod">Cash on delivery</option>
                <option value="cash">Cash</option>
                <option value="card">Card</option>
                <option value="mobile_banking">Mobile banking</option>
                <option value="other">Other</option>
              </select>
            </Field>
            <Field label="Delivery charge">
              <input
                type="number"
                min="0"
                step="0.01"
                className="input"
                value={deliveryCharge}
                onChange={(e) => setTypedCharge(e.target.value)}
              />
            </Field>
            <Field label="Discount">
              <input
                type="number"
                min="0"
                step="0.01"
                className="input"
                value={discount}
                onChange={(e) => setDiscount(e.target.value)}
              />
            </Field>
            <Field label="Notes">
              <textarea
                className="input"
                rows={3}
                placeholder="Channel, conversation link, special instructions…"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </Field>
          </section>

          <section className="card p-5 space-y-3">
            <h2 className="font-semibold text-gray-900">Summary</h2>
            <Row label="Subtotal" value={`৳${subtotal.toLocaleString()}`} />
            <Row label="Delivery" value={`৳${Number(deliveryCharge || 0).toLocaleString()}`} />
            <Row label="Discount" value={`−৳${Number(discount || 0).toLocaleString()}`} />
            <div className="border-t pt-3 flex justify-between font-semibold text-gray-900">
              <span>Total</span>
              <span>৳{total.toLocaleString()}</span>
            </div>
            <p className="text-xs text-gray-500">
              {['confirmed', 'processing', 'shipped', 'out_for_delivery', 'delivered'].includes(orderStatus)
                ? 'Stock will be deducted from available inventory when you save.'
                : 'Stock stays until the order is confirmed.'}
            </p>
            <button type="submit" disabled={saving} className="btn btn-primary w-full">
              {saving ? 'Creating…' : 'Create order'}
            </button>
          </section>
        </div>
      </form>

      {variantPicker && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-end sm:items-center justify-center p-4">
          <div className="bg-white rounded-xl w-full max-w-md max-h-[80vh] overflow-y-auto">
            <div className="p-4 border-b flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">{variantPicker.name}</h3>
              <button type="button" onClick={() => setVariantPicker(null)} className="p-2 hover:bg-gray-100 rounded-lg" aria-label="Close">
                <X className="w-5 h-5" />
              </button>
            </div>
            <ul className="divide-y">
              {(variantPicker.variants || []).map((variant) => (
                <li key={variant.id}>
                  <button
                    type="button"
                    onClick={() => addProduct(variantPicker, variant)}
                    className="w-full text-left px-4 py-3 hover:bg-gray-50"
                  >
                    <p className="text-sm font-medium">
                      {[variant.size, variant.color].filter(Boolean).join(' / ') || variant.sku || 'Variant'}
                    </p>
                    <p className="text-xs text-gray-500">
                      ৳{Number(variant.price).toLocaleString()} · Stock{' '}
                      {Number(variant.warehouse_stock || 0) + Number(variant.dealer_stock || 0)}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}

function Field({ label, required, className = '', children }) {
  return (
    <label className={`block ${className}`}>
      <span className="block text-sm font-medium text-gray-700 mb-1">
        {label}{required ? ' *' : ''}
      </span>
      {children}
    </label>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between text-sm text-gray-700">
      <span>{label}</span>
      <span>{value}</span>
    </div>
  );
}
