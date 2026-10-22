import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Barcode, Search, Plus, Minus, Trash2, Printer, X,
  Package, ChevronDown, ChevronUp, Settings2
} from 'lucide-react';
import toast from 'react-hot-toast';
import JsBarcode from 'jsbarcode';
import AdminLayout from '@/components/layout/AdminLayout';
import { useGetProductsQuery } from '@/store/api/productsApi';

// Label dimensions in mm
const LABEL_WIDTH_MM = 38;
const LABEL_HEIGHT_MM = 25;

export default function BarcodeLabelPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [labelQueue, setLabelQueue] = useState([]);
  const [showSettings, setShowSettings] = useState(false);
  const [labelSettings, setLabelSettings] = useState({
    showPrice: true,
    showSKU: true,
    showName: true,
    fontSize: 'small',
    barcodeFormat: 'CODE128',
  });

  const printRef = useRef();
  const { data: productsData, isLoading } = useGetProductsQuery({ search: searchQuery, page_size: 50 });
  const products = productsData?.results || productsData || [];

  // Add product/variant to label queue
  const addToQueue = (product, variant = null) => {
    const key = variant ? `${product.id}_${variant.id}` : product.id;
    const existing = labelQueue.find(item => item.key === key);

    if (existing) {
      setLabelQueue(prev => prev.map(item =>
        item.key === key ? { ...item, quantity: item.quantity + 1 } : item
      ));
    } else {
      setLabelQueue(prev => [...prev, {
        key,
        product_id: product.id,
        variant_id: variant?.id || null,
        name: product.name,
        variant_label: variant ? `${variant.size || ''} ${variant.color || ''}`.trim() : null,
        sku: variant?.sku || product.sku,
        barcode: variant?.barcode || product.barcode || variant?.sku || product.sku,
        price: variant?.price || product.price,
        quantity: 1,
      }]);
    }
    toast.success('Added to print queue');
  };

  const updateQuantity = (key, change) => {
    setLabelQueue(prev => prev.map(item => {
      if (item.key === key) {
        const newQty = Math.max(0, item.quantity + change);
        return { ...item, quantity: newQty };
      }
      return item;
    }).filter(item => item.quantity > 0));
  };

  const removeFromQueue = (key) => {
    setLabelQueue(prev => prev.filter(item => item.key !== key));
  };

  const totalLabels = labelQueue.reduce((sum, item) => sum + item.quantity, 0);

  // Barcode options for preview (SVG - screen display)
  const previewBarcodeOpts = useCallback((format) => ({
    format,
    width: 1.5,
    height: 30,
    displayValue: true,
    fontSize: 7,
    margin: 0,
    textMargin: 1,
    font: 'monospace',
  }), []);

  // Barcode options for print (Canvas - thermal printer optimized)
  const printBarcodeOpts = useCallback((format) => ({
    format,
    width: 2,
    height: 50,
    displayValue: true,
    fontSize: 12,
    margin: 0,
    textMargin: 2,
    font: 'monospace',
    fontOptions: 'bold',
    background: '#ffffff',
    lineColor: '#000000',
  }), []);

  // Generate preview barcodes (SVG for screen)
  const generatePreviewBarcodes = useCallback(() => {
    const previewArea = document.querySelector('.label-preview-area');
    if (!previewArea) return;
    const svgElements = previewArea.querySelectorAll('.barcode-preview');
    svgElements.forEach(el => {
      const value = el.getAttribute('data-value');
      if (value) {
        try {
          JsBarcode(el, value, previewBarcodeOpts(labelSettings.barcodeFormat));
        } catch {
          try { JsBarcode(el, value, previewBarcodeOpts('CODE128')); } catch { }
        }
      }
    });
  }, [labelSettings.barcodeFormat, previewBarcodeOpts]);

  // Generate print barcodes (Canvas for thermal - pixel-perfect, no anti-aliasing)
  const generatePrintBarcodes = useCallback(() => {
    if (!printRef.current) return;
    const canvasElements = printRef.current.querySelectorAll('.barcode-print');
    canvasElements.forEach(el => {
      const value = el.getAttribute('data-value');
      if (value) {
        try {
          JsBarcode(el, value, printBarcodeOpts(labelSettings.barcodeFormat));
          // Disable image smoothing for crisp thermal output
          const ctx = el.getContext('2d');
          if (ctx) {
            ctx.imageSmoothingEnabled = false;
            ctx.mozImageSmoothingEnabled = false;
            ctx.webkitImageSmoothingEnabled = false;
            ctx.msImageSmoothingEnabled = false;
          }
        } catch {
          try {
            JsBarcode(el, value, printBarcodeOpts('CODE128'));
          } catch { }
        }
      }
    });
  }, [labelSettings.barcodeFormat, printBarcodeOpts]);

  useEffect(() => {
    generatePreviewBarcodes();
    generatePrintBarcodes();
  }, [labelQueue, labelSettings, generatePreviewBarcodes, generatePrintBarcodes]);

  const handlePrint = () => {
    if (labelQueue.length === 0) {
      toast.error('Add products to print queue first');
      return;
    }
    generatePrintBarcodes();
    setTimeout(() => {
      window.print();
    }, 500);
  };

  // Expand labels: for each queue item, repeat by quantity
  const expandedLabels = labelQueue.flatMap(item =>
    Array.from({ length: item.quantity }, (_, i) => ({ ...item, index: i }))
  );

  return (
    <AdminLayout title="Barcode Label Printer">
      {/* Print-only styles - optimized for Rongta RP400 label printer */}
      <style jsx global>{`
        @media print {
          @page {
            size: 38mm 25mm;
            margin: 0;
          }
          html, body {
            margin: 0 !important;
            padding: 0 !important;
            width: 38mm !important;
            height: 25mm !important;
          }
          body * {
            visibility: hidden !important;
          }
          #barcode-print-area,
          #barcode-print-area * {
            visibility: visible !important;
          }
          #barcode-print-area {
            position: fixed !important;
            left: 0 !important;
            top: 0 !important;
            width: 38mm !important;
            margin: 0 !important;
            padding: 0 !important;
          }
          #barcode-print-area *,
          #barcode-print-area {
            -webkit-font-smoothing: none;
            -moz-osx-font-smoothing: unset;
            text-rendering: geometricPrecision;
            print-color-adjust: exact;
            -webkit-print-color-adjust: exact;
          }
          .barcode-label {
            width: 38mm !important;
            height: 25mm !important;
            page-break-after: always;
            break-after: page;
            overflow: hidden;
            box-sizing: border-box;
          }
          .barcode-label:last-child {
            page-break-after: avoid;
            break-after: avoid;
          }
          .barcode-print {
            image-rendering: pixelated !important;
            image-rendering: -moz-crisp-edges !important;
            -ms-interpolation-mode: nearest-neighbor !important;
          }
        }
      `}</style>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Left: Product Search & Selection */}
        <div className="lg:col-span-2 space-y-4">
          {/* Search */}
          <div className="card p-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search products by name, SKU, or barcode..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input pl-10 text-lg"
              />
            </div>
          </div>

          {/* Product List */}
          <div className="card">
            <div className="p-4 border-b bg-gray-50">
              <h2 className="font-semibold text-gray-900 flex items-center gap-2">
                <Package className="w-5 h-5" />
                Products
              </h2>
            </div>
            <div className="max-h-[60vh] overflow-y-auto divide-y">
              {isLoading ? (
                <div className="p-8 text-center text-gray-500">Loading products...</div>
              ) : products.length === 0 ? (
                <div className="p-8 text-center text-gray-500">No products found</div>
              ) : (
                products.map(product => (
                  <ProductRow
                    key={product.id}
                    product={product}
                    onAdd={addToQueue}
                  />
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right: Print Queue & Settings */}
        <div className="space-y-4">
          {/* Settings Toggle */}
          <div className="card">
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="w-full p-4 flex items-center justify-between text-left"
            >
              <span className="font-semibold text-gray-900 flex items-center gap-2">
                <Settings2 className="w-5 h-5" />
                Label Settings
              </span>
              {showSettings ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
            </button>
            {showSettings && (
              <div className="p-4 pt-0 space-y-3">
                <p className="text-xs text-gray-500">Label size: {LABEL_WIDTH_MM}mm x {LABEL_HEIGHT_MM}mm</p>

                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={labelSettings.showName}
                    onChange={(e) => setLabelSettings(s => ({ ...s, showName: e.target.checked }))}
                    className="rounded"
                  />
                  <span className="text-sm">Show product name</span>
                </label>

                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={labelSettings.showPrice}
                    onChange={(e) => setLabelSettings(s => ({ ...s, showPrice: e.target.checked }))}
                    className="rounded"
                  />
                  <span className="text-sm">Show price</span>
                </label>

                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={labelSettings.showSKU}
                    onChange={(e) => setLabelSettings(s => ({ ...s, showSKU: e.target.checked }))}
                    className="rounded"
                  />
                  <span className="text-sm">Show SKU</span>
                </label>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Barcode Format</label>
                  <select
                    value={labelSettings.barcodeFormat}
                    onChange={(e) => setLabelSettings(s => ({ ...s, barcodeFormat: e.target.value }))}
                    className="input text-sm"
                  >
                    <option value="CODE128">CODE128 (Default)</option>
                    <option value="EAN13">EAN-13</option>
                    <option value="EAN8">EAN-8</option>
                    <option value="UPC">UPC</option>
                    <option value="CODE39">CODE39</option>
                  </select>
                </div>

                <p className="text-xs text-gray-400 mt-2 border-t pt-2">
                  Each label prints as a separate page (38x25mm).
                  Set your printer paper size to 38x25mm.
                </p>
              </div>
            )}
          </div>

          {/* Print Queue */}
          <div className="card">
            <div className="p-4 border-b bg-gray-50 flex items-center justify-between">
              <h2 className="font-semibold text-gray-900 flex items-center gap-2">
                <Printer className="w-5 h-5" />
                Print Queue ({totalLabels} labels)
              </h2>
              {labelQueue.length > 0 && (
                <button
                  onClick={() => setLabelQueue([])}
                  className="text-xs text-red-500 hover:text-red-700"
                >
                  Clear All
                </button>
              )}
            </div>
            <div className="max-h-[40vh] overflow-y-auto divide-y">
              {labelQueue.length === 0 ? (
                <div className="p-8 text-center text-gray-400">
                  <Barcode className="w-10 h-10 mx-auto mb-2" />
                  <p className="text-sm">Add products to generate labels</p>
                </div>
              ) : (
                labelQueue.map(item => (
                  <div key={item.key} className="p-3 flex items-center gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{item.name}</p>
                      {item.variant_label && (
                        <p className="text-xs text-primary-600">{item.variant_label}</p>
                      )}
                      <p className="text-xs text-gray-500">
                        {item.barcode} &middot; ৳{parseFloat(item.price).toLocaleString()}
                      </p>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => updateQuantity(item.key, -1)}
                        className="p-1 bg-gray-100 rounded hover:bg-gray-200"
                      >
                        <Minus className="w-3 h-3" />
                      </button>
                      <span className="w-8 text-center text-sm font-medium">{item.quantity}</span>
                      <button
                        onClick={() => updateQuantity(item.key, 1)}
                        className="p-1 bg-gray-100 rounded hover:bg-gray-200"
                      >
                        <Plus className="w-3 h-3" />
                      </button>
                    </div>
                    <button
                      onClick={() => removeFromQueue(item.key)}
                      className="p-1 text-red-400 hover:text-red-600"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))
              )}
            </div>
            {labelQueue.length > 0 && (
              <div className="p-4 border-t">
                <button
                  onClick={handlePrint}
                  className="w-full btn btn-primary py-3 flex items-center justify-center gap-2"
                >
                  <Printer className="w-5 h-5" />
                  Print {totalLabels} Label{totalLabels !== 1 ? 's' : ''}
                </button>
              </div>
            )}
          </div>

          {/* Preview */}
          {labelQueue.length > 0 && (
            <div className="card p-4 label-preview-area">
              <h3 className="font-semibold text-gray-900 mb-3">Label Preview</h3>
              <div className="bg-gray-100 rounded-lg p-3 flex items-center justify-center">
                <div
                  style={{
                    width: `${LABEL_WIDTH_MM}mm`,
                    height: `${LABEL_HEIGHT_MM}mm`,
                    border: '1px dashed #ccc',
                    background: 'white',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '1mm',
                    overflow: 'hidden',
                  }}
                >
                  {labelSettings.showName && (
                    <div style={{ fontSize: '6px', fontWeight: 'bold', textAlign: 'center', lineHeight: 1.1, maxWidth: '100%', overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>
                      {labelQueue[0]?.name}
                    </div>
                  )}
                  {labelQueue[0]?.variant_label && (
                    <div style={{ fontSize: '5px', color: '#666', marginTop: '0.5mm' }}>
                      {labelQueue[0].variant_label}
                    </div>
                  )}
                  <svg
                    className="barcode-preview"
                    data-value={labelQueue[0]?.barcode}
                    style={{ maxWidth: '34mm', marginTop: '0.5mm', shapeRendering: 'crispEdges' }}
                  />
                  <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', marginTop: '0.5mm' }}>
                    {labelSettings.showSKU && (
                      <span style={{ fontSize: '5px', color: '#666' }}>{labelQueue[0]?.sku}</span>
                    )}
                    {labelSettings.showPrice && (
                      <span style={{ fontSize: '6px', fontWeight: 'bold' }}>৳{parseFloat(labelQueue[0]?.price).toLocaleString()}</span>
                    )}
                  </div>
                </div>
              </div>
              <p className="text-xs text-gray-500 text-center mt-2">
                Actual size: {LABEL_WIDTH_MM}mm x {LABEL_HEIGHT_MM}mm
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Hidden Print Area - one label per page for label printer */}
      <div id="barcode-print-area" ref={printRef} style={{ position: 'absolute', left: '-9999px', top: 0 }}>
        {expandedLabels.map((item, idx) => (
          <div
            key={`${item.key}-${item.index}`}
            className="barcode-label"
            style={{
              width: `${LABEL_WIDTH_MM}mm`,
              height: `${LABEL_HEIGHT_MM}mm`,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '1mm 1.5mm',
              overflow: 'hidden',
              boxSizing: 'border-box',
              pageBreakAfter: 'always',
            }}
          >
            {labelSettings.showName && (
              <div style={{ fontSize: '7px', fontWeight: '900', textAlign: 'center', lineHeight: 1.1, maxWidth: '100%', overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis', fontFamily: 'Arial, Helvetica, sans-serif', color: '#000' }}>
                {item.name}
              </div>
            )}
            {item.variant_label && (
              <div style={{ fontSize: '6px', fontWeight: '700', color: '#000', fontFamily: 'Arial, Helvetica, sans-serif' }}>
                {item.variant_label}
              </div>
            )}
            <canvas
              className="barcode-print"
              data-value={item.barcode}
              style={{ maxWidth: '35mm', marginTop: '0.5mm', imageRendering: 'pixelated' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', paddingLeft: '0.5mm', paddingRight: '0.5mm', marginTop: '0.5mm' }}>
              {labelSettings.showSKU && (
                <span style={{ fontSize: '6px', fontWeight: '700', color: '#000', fontFamily: 'monospace' }}>{item.sku}</span>
              )}
              {labelSettings.showPrice && (
                <span style={{ fontSize: '7px', fontWeight: '900', color: '#000', fontFamily: 'Arial, Helvetica, sans-serif' }}>{parseFloat(item.price).toLocaleString()} Tk</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </AdminLayout>
  );
}

// Product row component with variant expansion
function ProductRow({ product, onAdd }) {
  const [expanded, setExpanded] = useState(false);
  const hasVariants = product.variants && product.variants.length > 0;

  return (
    <div>
      <div className="flex items-center gap-3 p-3 hover:bg-gray-50">
        <div className="flex-1 min-w-0">
          <p className="font-medium text-gray-900 truncate">{product.name}</p>
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <span>SKU: {product.sku}</span>
            {product.barcode && <span>Barcode: {product.barcode}</span>}
            <span>৳{parseFloat(product.price).toLocaleString()}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {hasVariants ? (
            <button
              onClick={() => setExpanded(!expanded)}
              className="btn btn-secondary text-xs py-1.5 px-3 flex items-center gap-1"
            >
              {product.variants.length} Variants
              {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
          ) : (
            <button
              onClick={() => onAdd(product)}
              className="btn btn-primary text-xs py-1.5 px-3 flex items-center gap-1"
            >
              <Plus className="w-3 h-3" /> Add Label
            </button>
          )}
        </div>
      </div>
      {expanded && hasVariants && (
        <div className="bg-gray-50 px-4 pb-2">
          {product.variants.map(variant => (
            <div key={variant.id} className="flex items-center gap-3 py-2 px-3 bg-white rounded-lg mb-1">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800">
                  {`${variant.size || ''} ${variant.color || ''}`.trim() || 'Default'}
                </p>
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <span>SKU: {variant.sku}</span>
                  {variant.barcode && <span>Barcode: {variant.barcode}</span>}
                  <span>৳{parseFloat(variant.price || product.price).toLocaleString()}</span>
                  <span>Stock: {variant.stock_quantity}</span>
                </div>
              </div>
              <button
                onClick={() => onAdd(product, variant)}
                className="btn btn-primary text-xs py-1.5 px-3 flex items-center gap-1"
              >
                <Plus className="w-3 h-3" /> Add
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
