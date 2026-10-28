import { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/router';
import {
  Save, ArrowLeft, Upload, RefreshCw,
  Barcode, Printer, Image as ImageIcon, X, Copy, Check
} from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import { useGetCategoriesQuery } from '@/store/api/categoriesApi';
import {
  useCreateProductMutation,
  useUploadProductImageMutation,
  useSyncVariantSetupMutation,
  useGetStoreSettingsQuery
} from '@/store/api/productsApi';
import JsBarcode from 'jsbarcode';
import SpecificationFields, { cleanSpecifications } from '@/components/products/SpecificationFields';
import VariantOptions from '@/components/products/VariantOptions';

export default function NewProductPage() {
  const router = useRouter();
  const barcodeRef = useRef(null);
  const variantRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [hasVariants, setHasVariants] = useState(false);
  const [copied, setCopied] = useState(false);

  const { data: categoriesData } = useGetCategoriesQuery();
  const { data: storeSettings } = useGetStoreSettingsQuery();
  const [createProduct] = useCreateProductMutation();
  const [uploadProductImage] = useUploadProductImageMutation();
  const [syncVariantSetup] = useSyncVariantSetupMutation();

  const categories = Array.isArray(categoriesData?.results || categoriesData)
    ? (categoriesData?.results || categoriesData)
    : [];

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    sku: '',
    barcode: '',
    category: '',
    subcategory: '',
    price: '',
    compare_price: '',
    cost_price: '',
    stock_quantity: 0,
    low_stock_threshold: 10,
    weight: '',
    is_active: true,
    is_featured: false,
    is_official: false,
    warranty_period: '',
  });

  const [images, setImages] = useState([]);
  const [subcategories, setSubcategories] = useState([]);
  const [specifications, setSpecifications] = useState([]);

  useEffect(() => {
    // Generate initial barcode when settings are loaded
    if (storeSettings) {
      generateBarcode();
    }
  }, [storeSettings]);

  useEffect(() => {
    // Render barcode when barcode value changes
    if (formData.barcode && barcodeRef.current) {
      try {
        JsBarcode(barcodeRef.current, formData.barcode, {
          format: 'CODE128',
          width: 2,
          height: 80,
          displayValue: true,
          fontSize: 14,
          margin: 10,
          background: '#ffffff',
        });
      } catch (error) {
        console.error('Barcode generation error:', error);
      }
    }
  }, [formData.barcode]);

  // Generate unique barcode with prefix from store settings
  const generateBarcode = () => {
    const prefix = storeSettings?.barcode_prefix || 'ZZ';
    const timestamp = Date.now().toString().slice(-10);
    const random = Math.floor(Math.random() * 100).toString().padStart(2, '0');
    const barcode = `${prefix}-${timestamp}${random}`;
    setFormData(prev => ({ ...prev, barcode }));
  };

  // Generate SKU from product name
  const generateSKU = () => {
    if (!formData.name) {
      toast.error('Please enter product name first');
      return;
    }
    const words = formData.name.toUpperCase().split(' ');
    const prefix = words.map(w => w.charAt(0)).join('').slice(0, 3);
    const random = Math.floor(Math.random() * 10000).toString().padStart(4, '0');
    const sku = `${prefix}-${random}`;
    setFormData(prev => ({ ...prev, sku }));
  };

  const handleCategoryChange = (categoryId) => {
    setFormData(prev => ({ ...prev, category: categoryId, subcategory: '' }));
    const category = categories.find(c => c.id === categoryId);
    setSubcategories(category?.subcategories || []);
  };

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  // Image handling
  const handleImageUpload = (e) => {
    const files = Array.from(e.target.files);
    files.forEach(file => {
      const reader = new FileReader();
      reader.onloadend = () => {
        setImages(prev => [...prev, {
          id: Date.now() + Math.random(),
          file,
          preview: reader.result,
          is_primary: images.length === 0,
        }]);
      };
      reader.readAsDataURL(file);
    });
  };

  const removeImage = (id) => {
    setImages(images.filter(img => img.id !== id));
  };

  const setPrimaryImage = (id) => {
    setImages(images.map(img => ({
      ...img,
      is_primary: img.id === id
    })));
  };

  const copyBarcode = () => {
    navigator.clipboard.writeText(formData.barcode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    toast.success('Barcode copied to clipboard');
  };

  const printBarcode = () => {
    const printWindow = window.open('', '_blank');
    const barcodeHTML = `
      <!DOCTYPE html>
      <html>
        <head>
          <title>Barcode - ${formData.name || 'Product'}</title>
          <style>
            body { 
              font-family: Arial, sans-serif; 
              display: flex; 
              flex-direction: column;
              align-items: center; 
              justify-content: center; 
              min-height: 100vh;
              margin: 0;
              padding: 20px;
            }
            .barcode-container {
              text-align: center;
              padding: 20px;
              border: 2px dashed #ccc;
              border-radius: 8px;
            }
            .product-name { 
              font-size: 18px; 
              font-weight: bold; 
              margin-bottom: 10px; 
            }
            .price { 
              font-size: 24px; 
              font-weight: bold; 
              color: #059669;
              margin-top: 10px;
            }
            .sku { 
              font-size: 12px; 
              color: #666; 
              margin-top: 5px;
            }
            @media print {
              body { padding: 0; }
              .barcode-container { border: none; }
            }
          </style>
        </head>
        <body>
          <div class="barcode-container">
            <div class="product-name">${formData.name || 'Product Name'}</div>
            <svg id="barcode"></svg>
            ${formData.price ? `<div class="price">৳${formData.price}</div>` : ''}
            ${formData.sku ? `<div class="sku">SKU: ${formData.sku}</div>` : ''}
          </div>
          <script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>
          <script>
            JsBarcode("#barcode", "${formData.barcode}", {
              format: "CODE128",
              width: 2,
              height: 80,
              displayValue: true,
              fontSize: 14,
              margin: 10,
            });
            setTimeout(() => window.print(), 500);
          </script>
        </body>
      </html>
    `;
    printWindow.document.write(barcodeHTML);
    printWindow.document.close();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!formData.name || !formData.price || !formData.category) {
      toast.error('Please fill in all required fields');
      return;
    }

    const specResult = cleanSpecifications(specifications);
    if (specResult.error) {
      toast.error(specResult.error);
      return;
    }

    const setup = variantRef.current?.getSetup();
    if (setup?.error) {
      toast.error(setup.error);
      return;
    }

    setLoading(true);
    try {
      // Create product
      const productData = {
        ...formData,
        price: parseFloat(formData.price),
        compare_price: formData.compare_price ? parseFloat(formData.compare_price) : null,
        cost_price: formData.cost_price ? parseFloat(formData.cost_price) : null,
        stock_quantity: parseInt(formData.stock_quantity),
        low_stock_threshold: parseInt(formData.low_stock_threshold),
        weight: formData.weight ? parseFloat(formData.weight) : null,
        subcategory: formData.subcategory || null,
        specifications: specResult.specifications,
      };

      const response = await createProduct(productData).unwrap();
      const productId = response.id;

      // Upload images if any
      let imageErrors = 0;
      if (images.length > 0) {
        for (const img of images) {
          const imageData = new FormData();
          imageData.append('image', img.file);
          imageData.append('is_primary', img.is_primary ? 'true' : 'false');
          try {
            await uploadProductImage({ productId, imageData }).unwrap();
          } catch (imgError) {
            imageErrors++;
            console.error('Image upload error:', imgError);
          }
        }
      }

      let variantErrors = 0;
      if (setup?.payload) {
        try {
          await syncVariantSetup({ productId, ...setup.payload }).unwrap();
        } catch (varError) {
          variantErrors++;
          console.error('Variant setup error:', varError);
          toast.error(varError?.data?.detail || 'Could not save the variants');
        }
      }

      if (imageErrors > 0 || variantErrors > 0) {
        toast.success('Product created but some uploads failed. Please edit the product to retry.');
      } else {
        toast.success('Product created successfully!');
      }
      router.push('/products');
    } catch (error) {
      console.error('Failed to create product:', error);
      toast.error(error?.data?.detail || 'Failed to create product');
    } finally {
      setLoading(false);
    }
  };


  return (
    <AdminLayout title="Add New Product">
      <form onSubmit={handleSubmit}>
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={() => router.back()}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <h1 className="text-2xl font-semibold text-gray-900">Add New Product</h1>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => router.back()}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary"
            >
              {loading ? (
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Save className="w-4 h-4 mr-2" />
              )}
              Save Product
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Basic Information */}
            <div className="card">
              <h2 className="text-lg font-semibold mb-4">Basic Information</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Product Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    name="name"
                    value={formData.name}
                    onChange={handleInputChange}
                    className="input"
                    placeholder="Enter product name"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Description
                  </label>
                  <textarea
                    name="description"
                    value={formData.description}
                    onChange={handleInputChange}
                    rows={4}
                    className="input"
                    placeholder="Enter product description"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      SKU
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        name="sku"
                        value={formData.sku}
                        onChange={handleInputChange}
                        className="input flex-1"
                        placeholder="Enter SKU"
                      />
                      <button
                        type="button"
                        onClick={generateSKU}
                        className="btn btn-secondary px-3"
                        title="Auto-generate SKU"
                      >
                        <RefreshCw className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Weight (kg)
                    </label>
                    <input
                      type="number"
                      name="weight"
                      value={formData.weight}
                      onChange={handleInputChange}
                      className="input"
                      placeholder="0.5"
                      step="0.01"
                      min="0"
                    />
                  </div>
                </div>
              </div>
            </div>

            <SpecificationFields rows={specifications} onChange={setSpecifications} />

            {/* Barcode Section */}
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                  <Barcode className="w-5 h-5 text-primary-600" />
                  Auto-Generated Barcode
                </h2>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={generateBarcode}
                    className="btn btn-secondary text-sm"
                  >
                    <RefreshCw className="w-4 h-4 mr-1" />
                    Regenerate
                  </button>
                  <button
                    type="button"
                    onClick={printBarcode}
                    className="btn btn-secondary text-sm"
                  >
                    <Printer className="w-4 h-4 mr-1" />
                    Print
                  </button>
                </div>
              </div>

              <div className="bg-gray-50 rounded-xl p-6 text-center">
                <svg ref={barcodeRef} className="mx-auto"></svg>
                <div className="mt-4 flex items-center justify-center gap-2">
                  <code className="bg-white px-4 py-2 rounded-lg border text-lg font-mono">
                    {formData.barcode}
                  </code>
                  <button
                    type="button"
                    onClick={copyBarcode}
                    className="p-2 hover:bg-white rounded-lg transition-colors"
                    title="Copy barcode"
                  >
                    {copied ? (
                      <Check className="w-5 h-5 text-green-600" />
                    ) : (
                      <Copy className="w-5 h-5 text-gray-500" />
                    )}
                  </button>
                </div>
                <p className="text-sm text-gray-500 mt-3">
                  This barcode is automatically generated and unique. Customers can scan it to view product details.
                </p>
              </div>
            </div>

            {/* Pricing */}
            <div className="card">
              <h2 className="text-lg font-semibold mb-4">Pricing</h2>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Selling Price (৳) <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="number"
                    name="price"
                    value={formData.price}
                    onChange={handleInputChange}
                    className="input"
                    placeholder="0.00"
                    step="0.01"
                    min="0"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Compare Price (৳)
                  </label>
                  <input
                    type="number"
                    name="compare_price"
                    value={formData.compare_price}
                    onChange={handleInputChange}
                    className="input"
                    placeholder="0.00"
                    step="0.01"
                    min="0"
                  />
                  <p className="text-xs text-gray-500 mt-1">Original price for showing discount</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Cost Price (৳)
                  </label>
                  <input
                    type="number"
                    name="cost_price"
                    value={formData.cost_price}
                    onChange={handleInputChange}
                    className="input"
                    placeholder="0.00"
                    step="0.01"
                    min="0"
                  />
                  <p className="text-xs text-gray-500 mt-1">For profit calculation</p>
                </div>
              </div>
            </div>

            {/* Inventory — only show for products without variants */}
            {!hasVariants && (
              <div className="card">
                <h2 className="text-lg font-semibold mb-4">Inventory</h2>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Stock Quantity
                    </label>
                    <input
                      type="number"
                      name="stock_quantity"
                      value={formData.stock_quantity}
                      onChange={handleInputChange}
                      className="input"
                      min="0"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Low Stock Threshold
                    </label>
                    <input
                      type="number"
                      name="low_stock_threshold"
                      value={formData.low_stock_threshold}
                      onChange={handleInputChange}
                      className="input"
                      min="0"
                    />
                    <p className="text-xs text-gray-500 mt-1">Alert when stock falls below this</p>
                  </div>
                </div>
              </div>
            )}

            <VariantOptions
              ref={variantRef}
              productSku={formData.sku}
              barcodePrefix={storeSettings?.barcode_prefix || 'ZZ'}
              productName={formData.name}
              productPrice={formData.price}
              onCount={(count) => setHasVariants(count > 0)}
            />

            {/* Images */}
            <div className="card">
              <h2 className="text-lg font-semibold mb-4">Product Images</h2>

              <div className="border-2 border-dashed rounded-xl p-8 text-center bg-gray-50">
                <input
                  type="file"
                  id="images"
                  multiple
                  accept="image/*"
                  onChange={handleImageUpload}
                  className="hidden"
                />
                <label
                  htmlFor="images"
                  className="cursor-pointer flex flex-col items-center"
                >
                  <Upload className="w-12 h-12 text-gray-400 mb-3" />
                  <span className="text-gray-600 font-medium">Click to upload images</span>
                  <span className="text-gray-400 text-sm mt-1">PNG, JPG up to 5MB each</span>
                </label>
              </div>

              {images.length > 0 && (
                <div className="grid grid-cols-4 gap-4 mt-4">
                  {images.map((img) => (
                    <div key={img.id} className="relative group">
                      <img
                        src={img.preview}
                        alt="Product"
                        className={`w-full aspect-square object-cover rounded-lg border-2 ${img.is_primary ? 'border-primary-500' : 'border-transparent'
                          }`}
                      />
                      <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg flex items-center justify-center gap-2">
                        <button
                          type="button"
                          onClick={() => setPrimaryImage(img.id)}
                          className={`p-2 rounded-full ${img.is_primary ? 'bg-primary-500 text-white' : 'bg-white text-gray-700'}`}
                          title="Set as primary"
                        >
                          <ImageIcon className="w-4 h-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => removeImage(img.id)}
                          className="p-2 bg-red-500 text-white rounded-full"
                          title="Remove"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                      {img.is_primary && (
                        <span className="absolute top-2 left-2 bg-primary-500 text-white text-xs px-2 py-1 rounded">
                          Primary
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Status */}
            <div className="card">
              <h2 className="text-lg font-semibold mb-4">Status</h2>
              <div className="space-y-4">
                <label className="flex items-center justify-between cursor-pointer">
                  <span className="text-gray-700">Active</span>
                  <input
                    type="checkbox"
                    name="is_active"
                    checked={formData.is_active}
                    onChange={handleInputChange}
                    className="toggle"
                  />
                </label>
                <label className="flex items-center justify-between cursor-pointer">
                  <span className="text-gray-700">Featured</span>
                  <input
                    type="checkbox"
                    name="is_featured"
                    checked={formData.is_featured}
                    onChange={handleInputChange}
                    className="toggle"
                  />
                </label>
              </div>
            </div>

            <div className="card">
              <h2 className="text-lg font-semibold mb-1">Official & warranty</h2>
              <p className="text-sm text-gray-500 mb-4">Shown on the product page for the website and the app.</p>
              <div className="space-y-4">
                <label className="flex items-center justify-between gap-3 cursor-pointer">
                  <span>
                    <span className="block text-gray-700">Official product</span>
                    <span className="block text-xs text-gray-500">Adds the Official badge on the product photo.</span>
                  </span>
                  <input
                    type="checkbox"
                    name="is_official"
                    checked={formData.is_official}
                    onChange={handleInputChange}
                    className="toggle"
                  />
                </label>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="warranty_period">
                    Warranty period
                  </label>
                  <input
                    id="warranty_period"
                    type="text"
                    name="warranty_period"
                    value={formData.warranty_period}
                    onChange={handleInputChange}
                    maxLength={80}
                    placeholder="1 year"
                    className="input"
                  />
                  <p className="mt-1 text-xs text-gray-500">Leave empty when this product has no warranty.</p>
                </div>
              </div>
            </div>

            {/* Category */}
            <div className="card">
              <h2 className="text-lg font-semibold mb-4">Category</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Category <span className="text-red-500">*</span>
                  </label>
                  <select
                    name="category"
                    value={formData.category}
                    onChange={(e) => handleCategoryChange(e.target.value)}
                    className="input"
                    required
                  >
                    <option value="">Select category</option>
                    {Array.isArray(categories) && categories.map(cat => (
                      <option key={cat.id} value={cat.id}>{cat.name}</option>
                    ))}
                  </select>
                </div>

                {subcategories.length > 0 && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Subcategory
                    </label>
                    <select
                      name="subcategory"
                      value={formData.subcategory}
                      onChange={handleInputChange}
                      className="input"
                    >
                      <option value="">Select subcategory</option>
                      {subcategories.map(sub => (
                        <option key={sub.id} value={sub.id}>{sub.name}</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            </div>

            {/* Quick Info */}
            <div className="card bg-blue-50 border-blue-200">
              <h2 className="text-lg font-semibold mb-3 text-blue-900">Barcode Info</h2>
              <ul className="text-sm text-blue-800 space-y-2">
                <li>• Barcodes are auto-generated</li>
                <li>• Each product & variant gets unique barcode</li>
                <li>• Customers can scan to view product info</li>
                <li>• Use POS scanner for quick checkout</li>
                <li>• Print barcodes for physical labels</li>
              </ul>
            </div>
          </div>
        </div>
      </form>
    </AdminLayout>
  );
}
