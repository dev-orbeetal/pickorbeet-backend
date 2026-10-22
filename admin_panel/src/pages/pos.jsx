import { useState, useRef, useEffect } from 'react';
import {
  Barcode, Search, Plus, Minus, Trash2, ShoppingBag,
  Printer, CheckCircle, User, Phone, X
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useReactToPrint } from 'react-to-print';
import AdminLayout from '@/components/layout/AdminLayout';
import { useLazySearchBarcodeQuery, useLazyGetProductsQuery } from '@/store/api/productsApi';
import { useCreateInShopOrderMutation } from '@/store/api/ordersApi';
import { getMediaUrl } from '@/lib/utils';

export default function POSPage() {
  const [cart, setCart] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [customer, setCustomer] = useState({ name: '', phone: '', email: '' });
  const [discount, setDiscount] = useState(0);
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [completedOrder, setCompletedOrder] = useState(null);
  const [variantPicker, setVariantPicker] = useState(null);
  const printRef = useRef();
  const barcodeInputRef = useRef();

  const [searchBarcode] = useLazySearchBarcodeQuery();
  const [searchProducts] = useLazyGetProductsQuery();
  const [createInShopOrder, { isLoading: processing }] = useCreateInShopOrderMutation();

  useEffect(() => {
    barcodeInputRef.current?.focus();
  }, []);

  const handleBarcodeSearch = async (barcode) => {
    if (!barcode.trim()) return;

    try {
      const response = await searchBarcode(barcode).unwrap();

      if (response.pick_variant && response.variants) {
        // Product has variants — show variant picker
        setVariantPicker(response);
        setSearchQuery('');
        return;
      }

      // Show in suggestions instead of directly adding to cart
      setSearchResults([response]);
      setSearchQuery('');
    } catch (error) {
      // Fallback to product name search
      handleProductSearch();
    }
  };

  const handleVariantSelect = (variant) => {
    if (!variantPicker) return;
    addToCart({
      id: variantPicker.id,
      variant_id: variant.id,
      name: variantPicker.name,
      variant_label: variant.label,
      sku: variant.sku,
      barcode: variant.barcode,
      price: variant.price,
      stock_quantity: variant.stock_quantity,
      primary_image: variantPicker.primary_image,
      has_variants: true,
    });
    setVariantPicker(null);
  };

  const handleProductSearch = async () => {
    if (!searchQuery.trim()) return;

    try {
      const response = await searchProducts({ search: searchQuery }).unwrap();
      setSearchResults(response.results || response);
    } catch (error) {
      toast.error('Search failed');
    }
  };

  // Cart key: use variant_id if present, otherwise product id
  const getCartKey = (item) => item.variant_id ? `${item.id}_${item.variant_id}` : item.id;

  const addToCart = (product) => {
    const key = getCartKey(product);
    const existingIndex = cart.findIndex(item => getCartKey(item) === key);

    if (existingIndex > -1) {
      const newCart = [...cart];
      newCart[existingIndex].quantity += 1;
      setCart(newCart);
    } else {
      setCart([...cart, {
        ...product,
        quantity: 1,
        unit_price: parseFloat(product.price)
      }]);
    }

    setSearchResults([]);
    setSearchQuery('');
    const label = product.variant_label ? `${product.name} (${product.variant_label})` : product.name;
    toast.success(`${label} added`);
  };

  const updateQuantity = (index, change) => {
    const newCart = [...cart];
    newCart[index].quantity += change;

    if (newCart[index].quantity <= 0) {
      newCart.splice(index, 1);
    }

    setCart(newCart);
  };

  const removeItem = (index) => {
    const newCart = [...cart];
    newCart.splice(index, 1);
    setCart(newCart);
  };

  const subtotal = cart.reduce((sum, item) => sum + (item.unit_price * item.quantity), 0);
  const total = subtotal - discount;

  const handleCheckout = async () => {
    if (cart.length === 0) {
      toast.error('Cart is empty');
      return;
    }

    try {
      const orderData = {
        customer_name: customer.name || 'Walk-in Customer',
        customer_phone: customer.phone,
        customer_email: customer.email,
        items: cart.map(item => ({
          product_id: item.id,
          variant_id: item.variant_id || null,
          quantity: item.quantity,
        })),
        discount,
        payment_method: paymentMethod,
      };

      const response = await createInShopOrder(orderData).unwrap();
      setCompletedOrder(response.order);
      toast.success('Order completed!');
    } catch (error) {
      toast.error(error?.data?.error || 'Checkout failed');
    }
  };

  const handlePrint = useReactToPrint({
    content: () => printRef.current,
    onAfterPrint: () => {
      setCart([]);
      setCustomer({ name: '', phone: '', email: '' });
      setDiscount(0);
      setCompletedOrder(null);
    },
  });

  const resetPOS = () => {
    setCart([]);
    setCustomer({ name: '', phone: '', email: '' });
    setDiscount(0);
    setCompletedOrder(null);
    barcodeInputRef.current?.focus();
  };

  return (
    <AdminLayout title="POS - In-Shop Order">
      <div className="grid lg:grid-cols-3 gap-6 h-[calc(100vh-140px)]">
        {/* Product Search */}
        <div className="lg:col-span-2 flex flex-col">
          {/* Barcode Scanner Input */}
          <div className="card p-4 mb-4">
            <div className="flex gap-4">
              <div className="flex-1 relative">
                <Barcode className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  ref={barcodeInputRef}
                  type="text"
                  placeholder="Scan barcode or enter product code..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter') {
                      handleBarcodeSearch(searchQuery);
                    }
                  }}
                  className="input pl-10 text-lg"
                  autoFocus
                />
              </div>
              <button onClick={handleProductSearch} className="btn btn-primary">
                <Search className="w-5 h-5" />
              </button>
            </div>

            {/* Search Results */}
            {searchResults.length > 0 && (
              <div className="mt-4 max-h-64 overflow-y-auto border rounded-lg">
                {searchResults.map((product) => (
                  <button
                    key={product.id}
                    onClick={() => addToCart(product)}
                    className="w-full flex items-center gap-4 p-3 hover:bg-gray-50 border-b last:border-0 text-left"
                  >
                    {product.primary_image ? (
                      <img src={getMediaUrl(product.primary_image)} alt={product.name} className="w-12 h-12 rounded object-cover" />
                    ) : (
                      <div className="w-12 h-12 bg-gray-100 rounded" />
                    )}
                    <div className="flex-1">
                      <p className="font-medium">{product.name}</p>
                      <p className="text-sm text-gray-500">SKU: {product.sku}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold text-primary-600">
                        ৳{parseFloat(product.price).toLocaleString()}
                      </p>
                      <p className="text-xs text-gray-500">Stock: {product.stock_quantity}</p>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Cart Items */}
          <div className="card flex-1 overflow-hidden flex flex-col">
            <div className="p-4 border-b bg-gray-50">
              <h2 className="font-semibold text-gray-900">Cart ({cart.length} items)</h2>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              {cart.length === 0 ? (
                <div className="h-full flex items-center justify-center text-gray-400">
                  <div className="text-center">
                    <ShoppingBag className="w-12 h-12 mx-auto mb-2" />
                    <p>Scan products to add</p>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  {cart.map((item, index) => (
                    <div key={getCartKey(item)} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                      {item.primary_image ? (
                        <img src={getMediaUrl(item.primary_image)} alt={item.name} className="w-12 h-12 rounded object-cover flex-shrink-0" />
                      ) : (
                        <div className="w-12 h-12 bg-gray-200 rounded flex-shrink-0" />
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm truncate">{item.name}</p>
                        {item.variant_label && (
                          <p className="text-xs text-primary-600 font-medium">{item.variant_label}</p>
                        )}
                        <p className="text-sm text-gray-500">৳{item.unit_price.toLocaleString()}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => updateQuantity(index, -1)}
                          className="p-1 bg-gray-200 rounded hover:bg-gray-300"
                        >
                          <Minus className="w-4 h-4" />
                        </button>
                        <span className="w-8 text-center font-medium">{item.quantity}</span>
                        <button
                          onClick={() => updateQuantity(index, 1)}
                          className="p-1 bg-gray-200 rounded hover:bg-gray-300"
                        >
                          <Plus className="w-4 h-4" />
                        </button>
                      </div>
                      <div className="text-right w-24">
                        <p className="font-semibold">৳{(item.unit_price * item.quantity).toLocaleString()}</p>
                      </div>
                      <button
                        onClick={() => removeItem(index)}
                        className="p-1 text-red-500 hover:bg-red-50 rounded"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Checkout Panel */}
        <div className="card flex flex-col">
          <div className="p-4 border-b bg-gray-50">
            <h2 className="font-semibold text-gray-900">Checkout</h2>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Customer Info */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Customer Name</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  value={customer.name}
                  onChange={(e) => setCustomer({ ...customer, name: e.target.value })}
                  className="input pl-10"
                  placeholder="Optional"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
              <div className="relative">
                <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="tel"
                  value={customer.phone}
                  onChange={(e) => setCustomer({ ...customer, phone: e.target.value })}
                  className="input pl-10"
                  placeholder="Optional"
                />
              </div>
            </div>

            {/* Payment Method */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Payment Method</label>
              <div className="grid grid-cols-3 gap-2">
                {['cash', 'card', 'mobile_banking'].map((method) => (
                  <button
                    key={method}
                    onClick={() => setPaymentMethod(method)}
                    className={`py-2 px-3 text-sm rounded-lg border transition-colors ${paymentMethod === method
                      ? 'bg-primary-600 text-white border-primary-600'
                      : 'bg-white text-gray-700 hover:border-primary-600'
                      }`}
                  >
                    {method.replace('_', ' ')}
                  </button>
                ))}
              </div>
            </div>

            {/* Discount */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Discount</label>
              <input
                type="number"
                value={discount}
                onChange={(e) => setDiscount(parseFloat(e.target.value) || 0)}
                className="input"
                min="0"
              />
            </div>
          </div>

          {/* Summary */}
          <div className="p-4 border-t bg-gray-50 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">Subtotal</span>
              <span>৳{subtotal.toLocaleString()}</span>
            </div>
            {discount > 0 && (
              <div className="flex justify-between text-sm text-green-600">
                <span>Discount</span>
                <span>-৳{discount.toLocaleString()}</span>
              </div>
            )}
            <div className="flex justify-between text-xl font-bold pt-2 border-t">
              <span>Total</span>
              <span className="text-primary-600">৳{total.toLocaleString()}</span>
            </div>
          </div>

          {/* Actions */}
          <div className="p-4 border-t space-y-2">
            {completedOrder ? (
              <>
                <div className="text-center py-4 text-green-600">
                  <CheckCircle className="w-12 h-12 mx-auto mb-2" />
                  <p className="font-semibold">Order Complete!</p>
                  <p className="text-sm text-gray-500">{completedOrder.order_number}</p>
                </div>
                <button onClick={handlePrint} className="w-full btn btn-primary">
                  <Printer className="w-4 h-4 mr-2" />
                  Print Receipt
                </button>
                <button onClick={resetPOS} className="w-full btn btn-secondary">
                  New Order
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={handleCheckout}
                  disabled={cart.length === 0 || processing}
                  className="w-full btn btn-primary py-3 text-lg"
                >
                  {processing ? 'Processing...' : `Complete Sale (৳${total.toLocaleString()})`}
                </button>
                <button onClick={resetPOS} className="w-full btn btn-secondary">
                  Clear
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* POS Receipt Print Template - Optimized for Rongta RP80 (80mm thermal) */}
      <div className="hidden">
        <style>{`
          @media print {
            @page { size: 80mm auto; margin: 0; }
            body { margin: 0; padding: 0; }
            .no-print { display: none !important; }
          }
          .receipt-thermal,
          .receipt-thermal * {
            -webkit-font-smoothing: none;
            -moz-osx-font-smoothing: unset;
            text-rendering: geometricPrecision;
            print-color-adjust: exact;
            -webkit-print-color-adjust: exact;
          }
          .receipt-thermal {
            width: 72mm;
            padding: 3mm;
            font-family: 'Courier New', 'Lucida Console', monospace;
            font-size: 12px;
            font-weight: 700;
            line-height: 1.3;
            color: #000;
            letter-spacing: 0;
          }
          .receipt-thermal .receipt-header { text-align: center; margin-bottom: 3mm; }
          .receipt-thermal .receipt-header h1 { font-size: 20px; font-weight: 900; margin: 0; letter-spacing: 1px; }
          .receipt-thermal .receipt-header p { margin: 1px 0; font-size: 11px; font-weight: 700; color: #000; }
          .receipt-thermal .receipt-divider { border-top: 1px dashed #000; margin: 2mm 0; }
          .receipt-thermal .receipt-info { font-size: 11px; font-weight: 700; }
          .receipt-thermal .receipt-info p { margin: 1px 0; color: #000; }
          .receipt-thermal table { width: 100%; border-collapse: collapse; }
          .receipt-thermal table th { font-size: 11px; font-weight: 900; padding: 1mm 0; border-bottom: 1px solid #000; color: #000; }
          .receipt-thermal table td { font-size: 11px; font-weight: 700; padding: 1mm 0; vertical-align: top; color: #000; }
          .receipt-thermal .item-variant { font-size: 10px; font-weight: 700; color: #000; padding-left: 2mm; }
          .receipt-thermal .item-unit { font-size: 10px; font-weight: 700; color: #000; }
          .receipt-thermal .totals-row { display: flex; justify-content: space-between; font-size: 12px; font-weight: 700; color: #000; }
          .receipt-thermal .totals-row.grand { font-size: 16px; font-weight: 900; margin-top: 1mm; }
          .receipt-thermal .receipt-footer { text-align: center; margin-top: 3mm; font-size: 11px; font-weight: 700; color: #000; }
          .receipt-thermal .receipt-footer p { margin: 1px 0; }
        `}</style>
        <div ref={printRef} className="receipt-thermal">
          <div className="receipt-header">
            <h1>PickOrbeet</h1>
            <p>Premium Clothing Store</p>
            <p>Dhaka, Bangladesh</p>
            <p>Tel: +880 1234-567890</p>
          </div>

          <div className="receipt-divider" />
          <div className="receipt-info">
            <p>Order: {completedOrder?.order_number}</p>
            <p>Date: {new Date().toLocaleString('en-BD')}</p>
            <p>Cashier: {completedOrder?.processed_by || 'Staff'}</p>
            {customer.name && <p>Customer: {customer.name}</p>}
            {customer.phone && <p>Phone: {customer.phone}</p>}
          </div>
          <div className="receipt-divider" />

          <table>
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>Item</th>
                <th style={{ textAlign: 'center', width: '30px' }}>Qty</th>
                <th style={{ textAlign: 'right' }}>Amount</th>
              </tr>
            </thead>
            <tbody>
              {cart.map((item, index) => (
                <tr key={index}>
                  <td>
                    {item.name}
                    {item.variant_label && (
                      <div className="item-variant">({item.variant_label})</div>
                    )}
                    <div className="item-unit">
                      @{item.unit_price.toLocaleString()} Tk
                    </div>
                  </td>
                  <td style={{ textAlign: 'center' }}>{item.quantity}</td>
                  <td style={{ textAlign: 'right' }}>{(item.unit_price * item.quantity).toLocaleString()} Tk</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="receipt-divider" />
          <div className="totals-row">
            <span>Subtotal ({cart.reduce((s, i) => s + i.quantity, 0)} items):</span>
            <span>{subtotal.toLocaleString()} Tk</span>
          </div>
          {discount > 0 && (
            <div className="totals-row">
              <span>Discount:</span>
              <span>-{discount.toLocaleString()} Tk</span>
            </div>
          )}
          <div className="receipt-divider" />
          <div className="totals-row grand">
            <span>TOTAL:</span>
            <span>{total.toLocaleString()} Tk</span>
          </div>
          <div className="totals-row" style={{ marginTop: '1mm' }}>
            <span>Payment:</span>
            <span style={{ textTransform: 'uppercase' }}>{paymentMethod.replace('_', ' ')}</span>
          </div>

          <div className="receipt-divider" />
          <div className="receipt-footer">
            <p>Thank you for shopping!</p>
            <p>Exchange within 3 days with receipt</p>
            <p style={{ marginTop: '2mm' }}>www.PickOrbeet.com</p>
          </div>
        </div>
      </div>

      {/* Variant Picker Modal */}
      {variantPicker && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
            <div className="p-5 border-b flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Select Variant</h2>
                <p className="text-sm text-gray-500 mt-0.5">{variantPicker.name}</p>
              </div>
              <button
                onClick={() => setVariantPicker(null)}
                className="p-2 hover:bg-gray-100 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 max-h-80 overflow-y-auto space-y-2">
              {variantPicker.variants.map((v) => (
                <button
                  key={v.id}
                  onClick={() => handleVariantSelect(v)}
                  disabled={v.stock_quantity === 0}
                  className={`w-full flex items-center justify-between p-4 rounded-xl border-2 transition-all text-left ${v.stock_quantity === 0
                    ? 'border-gray-100 bg-gray-50 opacity-50 cursor-not-allowed'
                    : 'border-gray-200 hover:border-primary-500 hover:bg-primary-50'
                    }`}
                >
                  <div>
                    <p className="font-medium text-gray-900">
                      {v.label || 'Default'}
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      SKU: {v.sku}
                      {v.barcode && ` • Barcode: ${v.barcode}`}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold text-primary-600">
                      ৳{parseFloat(v.price).toLocaleString()}
                    </p>
                    <p className={`text-xs ${v.stock_quantity === 0 ? 'text-red-500' : 'text-gray-500'}`}>
                      {v.stock_quantity === 0 ? 'Out of stock' : `Stock: ${v.stock_quantity}`}
                    </p>
                  </div>
                </button>
              ))}
            </div>
            <div className="p-4 border-t">
              <button
                onClick={() => setVariantPicker(null)}
                className="w-full btn btn-secondary"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}
