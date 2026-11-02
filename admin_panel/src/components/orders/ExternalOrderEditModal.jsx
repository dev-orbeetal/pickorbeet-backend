import { useEffect, useMemo, useState } from 'react';
import { Plus, Search, Trash2, X, Package } from 'lucide-react';
import toast from 'react-hot-toast';
import BdAddressFields from '@/components/BdAddressFields';
import { useGetInventoryItemsQuery } from '@/store/api/productsApi';
import { useUpdateExternalOrderMutation } from '@/store/api/ordersApi';
import { getMediaUrl } from '@/lib/utils';

function lineKey(line) {
  return line.variant_id ? `${line.product_id}_${line.variant_id}` : String(line.product_id);
}

export default function ExternalOrderEditModal({ order, open, onClose }) {
  const [form, setForm] = useState(null);
  const [search, setSearch] = useState('');
  const [variantPicker, setVariantPicker] = useState(null);
  const { data: inventory } = useGetInventoryItemsQuery({}, { skip: !open });
  const [updateExternalOrder, { isLoading: saving }] = useUpdateExternalOrderMutation();

  useEffect(() => {
    if (!open || !order) return;
    setForm({
      customer_name: order.customer_name || order.guest_name || order.shipping_name || '',
      customer_phone: order.customer_phone || order.guest_phone || order.shipping_phone || '',
      customer_email: order.customer_email || order.guest_email || '',
      shipping_address_line1: order.shipping_address_line1 || '',
      shipping_address_line2: order.shipping_address_line2 || '',
      shipping_division: order.shipping_division || '',
      shipping_city: order.shipping_city || '',
      shipping_district: order.shipping_district || '',
      shipping_post_office: order.shipping_post_office || '',
      shipping_postal_code: order.shipping_postal_code || '',
      stock_location: '',
      delivery_charge: String(order.delivery_charge ?? 0),
      discount: String(order.discount ?? 0),
      payment_method: order.payment_method || 'cod',
      payment_status: order.payment_status || 'pending',
      notes: order.notes || '',
      items: (order.items || []).map((item) => ({
        product_id: item.product,
        variant_id: item.variant || null,
        name: item.product_name,
        variant_label: [item.size, item.color].filter(Boolean).join(' / '),
        quantity: item.quantity,
        unit_price: String(item.unit_price),
      })),
    });
    setSearch('');
    setVariantPicker(null);
  }, [open, order]);

  const products = inventory?.items || [];
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return products.slice(0, 30);
    return products.filter((product) => {
      const hay = `${product.name} ${product.sku || ''}`.toLowerCase();
      return hay.includes(q);
    }).slice(0, 30);
  }, [products, search]);

  if (!open || !form) return null;

  const subtotal = form.items.reduce(
    (sum, line) => sum + (Number(line.unit_price) || 0) * (Number(line.quantity) || 0),
    0,
  );
  const total = Math.max(0, subtotal + (Number(form.delivery_charge) || 0) - (Number(form.discount) || 0));

  const addProduct = (product, variant = null) => {
    const entry = {
      product_id: product.id,
      variant_id: variant?.id || null,
      name: product.name,
      variant_label: variant
        ? [variant.size, variant.color].filter(Boolean).join(' / ') || variant.sku
        : '',
      quantity: 1,
      unit_price: String(variant?.price ?? product.price ?? 0),
    };
    const key = lineKey(entry);
    const existing = form.items.findIndex((line) => lineKey(line) === key);
    if (existing >= 0) {
      const next = [...form.items];
      next[existing] = { ...next[existing], quantity: next[existing].quantity + 1 };
      setForm({ ...form, items: next });
    } else {
      setForm({ ...form, items: [...form.items, entry] });
    }
    setVariantPicker(null);
    setSearch('');
  };

  const handlePick = (product) => {
    if (product.has_variants && product.variants?.length) {
      setVariantPicker(product);
      return;
    }
    addProduct(product);
  };

  const updateLine = (index, patch) => {
    setForm({
      ...form,
      items: form.items.map((line, i) => (i === index ? { ...line, ...patch } : line)),
    });
  };

  const removeLine = (index) => {
    setForm({ ...form, items: form.items.filter((_, i) => i !== index) });
  };

  const save = async (event) => {
    event.preventDefault();
    if (!form.customer_name.trim() || !form.customer_phone.trim()) {
      toast.error('Customer name and phone are required');
      return;
    }
    if (
      !form.shipping_address_line1.trim()
      || !form.shipping_division.trim()
      || !form.shipping_district.trim()
      || !form.shipping_post_office.trim()
      || !form.shipping_city.trim()
    ) {
      toast.error('Enter a full delivery address (division, district, post office, city)');
      return;
    }
    if (form.items.length === 0) {
      toast.error('Add at least one product');
      return;
    }
    try {
      await updateExternalOrder({
        id: order.id,
        customer_name: form.customer_name.trim(),
        customer_phone: form.customer_phone.trim(),
        customer_email: form.customer_email || '',
        shipping_address_line1: form.shipping_address_line1.trim(),
        shipping_address_line2: form.shipping_address_line2 || '',
        shipping_division: form.shipping_division.trim(),
        shipping_city: form.shipping_city.trim(),
        shipping_district: form.shipping_district.trim(),
        shipping_post_office: form.shipping_post_office.trim(),
        shipping_postal_code: form.shipping_postal_code || '',
        stock_location: '',
        delivery_charge: form.delivery_charge || 0,
        discount: form.discount || 0,
        payment_method: form.payment_method,
        payment_status: form.payment_status,
        notes: form.notes || '',
        items: form.items.map((line) => ({
          product_id: line.product_id,
          variant_id: line.variant_id,
          quantity: Number(line.quantity),
          unit_price: line.unit_price,
        })),
      }).unwrap();
      toast.success('Order updated');
      onClose();
    } catch (error) {
      toast.error(error?.data?.detail || 'Could not update the order');
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-end sm:items-center justify-center p-4">
      <form onSubmit={save} className="bg-white rounded-xl w-full max-w-3xl max-h-[92vh] overflow-y-auto">
        <div className="p-5 border-b flex items-center justify-between sticky top-0 bg-white z-10">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Edit external order</h2>
            <p className="text-sm text-gray-500">{order.order_number}</p>
          </div>
          <button type="button" onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg" aria-label="Close">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-6">
          <section className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Customer name" required>
              <input className="input" required value={form.customer_name} onChange={(e) => setForm({ ...form, customer_name: e.target.value })} />
            </Field>
            <Field label="Phone" required>
              <input className="input" required value={form.customer_phone} onChange={(e) => setForm({ ...form, customer_phone: e.target.value })} />
            </Field>
            <Field label="Email">
              <input type="email" className="input" value={form.customer_email} onChange={(e) => setForm({ ...form, customer_email: e.target.value })} />
            </Field>
            <Field label="Address line 1" required className="sm:col-span-2">
              <input className="input" required value={form.shipping_address_line1} onChange={(e) => setForm({ ...form, shipping_address_line1: e.target.value })} />
            </Field>
            <Field label="Address line 2" className="sm:col-span-2">
              <input className="input" value={form.shipping_address_line2} onChange={(e) => setForm({ ...form, shipping_address_line2: e.target.value })} />
            </Field>
            <BdAddressFields
              Field={Field}
              value={{
                division: form.shipping_division,
                district: form.shipping_district,
                post_office: form.shipping_post_office,
                postal_code: form.shipping_postal_code,
                city: form.shipping_city,
              }}
              onChange={(next) => setForm({
                ...form,
                shipping_division: next.division || '',
                shipping_district: next.district || '',
                shipping_post_office: next.post_office || '',
                shipping_postal_code: next.postal_code || '',
                shipping_city: next.city || '',
              })}
            />
            <Field label="Delivery charge">
              <input type="number" min="0" step="0.01" className="input" value={form.delivery_charge} onChange={(e) => setForm({ ...form, delivery_charge: e.target.value })} />
            </Field>
            <Field label="Discount">
              <input type="number" min="0" step="0.01" className="input" value={form.discount} onChange={(e) => setForm({ ...form, discount: e.target.value })} />
            </Field>
            <Field label="Payment method">
              <select className="input" value={form.payment_method} onChange={(e) => setForm({ ...form, payment_method: e.target.value })}>
                <option value="cod">Cash on delivery</option>
                <option value="cash">Cash</option>
                <option value="card">Card</option>
                <option value="mobile_banking">Mobile banking</option>
                <option value="other">Other</option>
              </select>
            </Field>
            <Field label="Payment status">
              <select className="input" value={form.payment_status} onChange={(e) => setForm({ ...form, payment_status: e.target.value })}>
                <option value="pending">Pending</option>
                <option value="paid">Paid</option>
                <option value="failed">Failed</option>
              </select>
            </Field>
            <Field label="Notes" className="sm:col-span-2">
              <textarea className="input" rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </Field>
          </section>

          <section className="space-y-3">
            <h3 className="font-semibold text-gray-900">Products</h3>
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                className="input pl-9"
                placeholder="Search to add a product"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            {search.trim() && (
              <div className="max-h-40 overflow-y-auto border rounded-lg divide-y">
                {filtered.map((product) => (
                  <button
                    key={product.id}
                    type="button"
                    onClick={() => handlePick(product)}
                    className="w-full text-left px-3 py-2 hover:bg-gray-50 flex items-center gap-3"
                  >
                    <div className="w-8 h-8 rounded bg-gray-100 overflow-hidden flex-shrink-0">
                      {product.primary_image ? (
                        <img src={getMediaUrl(product.primary_image)} alt="" className="w-full h-full object-cover" />
                      ) : (
                        <Package className="w-4 h-4 m-2 text-gray-400" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium truncate">{product.name}</p>
                      <p className="text-xs text-gray-500">৳{Number(product.price).toLocaleString()}</p>
                    </div>
                    <Plus className="w-4 h-4 text-primary-600" />
                  </button>
                ))}
              </div>
            )}

            <div className="overflow-x-auto border rounded-lg">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    {['Product', 'Price', 'Qty', ''].map((heading) => (
                      <th key={heading || 'x'} className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">{heading}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {form.items.map((line, index) => (
                    <tr key={lineKey(line)}>
                      <td className="px-3 py-2 text-sm">
                        <p className="font-medium">{line.name}</p>
                        {line.variant_label ? <p className="text-xs text-gray-500">{line.variant_label}</p> : null}
                      </td>
                      <td className="px-3 py-2">
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          className="input w-28"
                          value={line.unit_price}
                          onChange={(e) => updateLine(index, { unit_price: e.target.value })}
                        />
                      </td>
                      <td className="px-3 py-2">
                        <input
                          type="number"
                          min="1"
                          className="input w-20"
                          value={line.quantity}
                          onChange={(e) => updateLine(index, { quantity: Math.max(1, parseInt(e.target.value, 10) || 1) })}
                        />
                      </td>
                      <td className="px-3 py-2 text-right">
                        <button type="button" onClick={() => removeLine(index)} className="text-red-600 p-1" aria-label="Remove">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-sm text-gray-600">
              Subtotal ৳{subtotal.toLocaleString()} · Total ৳{total.toLocaleString()}
            </p>
          </section>
        </div>

        <div className="p-5 border-t flex justify-end gap-2 sticky bottom-0 bg-white">
          <button type="button" onClick={onClose} className="btn btn-secondary">Cancel</button>
          <button type="submit" disabled={saving} className="btn btn-primary">
            {saving ? 'Saving…' : 'Save changes'}
          </button>
        </div>
      </form>

      {variantPicker && (
        <div className="fixed inset-0 z-[60] bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl w-full max-w-md max-h-[70vh] overflow-y-auto">
            <div className="p-4 border-b flex items-center justify-between">
              <h3 className="font-semibold">{variantPicker.name}</h3>
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
                    {[variant.size, variant.color].filter(Boolean).join(' / ') || variant.sku || 'Variant'}
                    <span className="block text-xs text-gray-500">৳{Number(variant.price).toLocaleString()}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
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
