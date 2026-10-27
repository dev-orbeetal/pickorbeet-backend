import { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/router';
import {
  Save, ArrowLeft, Plus, Trash2, Upload, RefreshCw,
  Barcode, Printer, Image as ImageIcon, X, Copy, Check
} from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import { useGetCategoriesQuery } from '@/store/api/categoriesApi';
import {
  useGetProductQuery,
  useUpdateProductMutation,
  useUploadProductImageMutation,
  useDeleteProductImageMutation,
  useCreateVariantMutation,
  useUpdateVariantMutation,
  useDeleteVariantMutation
} from '@/store/api/productsApi';
import JsBarcode from 'jsbarcode';
import { getMediaUrl, routeId } from '@/lib/utils';
import SpecificationFields, { cleanSpecifications } from '@/components/products/SpecificationFields';

export default function EditProductPage() {
  const router = useRouter();
  const id = routeId(router);
  const barcodeRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const { data: product, isLoading: productLoading, refetch } = useGetProductQuery(id, { skip: !id });
  const { data: categoriesData } = useGetCategoriesQuery();
  const [updateProduct] = useUpdateProductMutation();
  const [uploadProductImage] = useUploadProductImageMutation();
  const [deleteProductImage] = useDeleteProductImageMutation();
  const [createVariant] = useCreateVariantMutation();
  const [updateVariant] = useUpdateVariantMutation();
  const [deleteVariant] = useDeleteVariantMutation();

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
  });

  const [variants, setVariants] = useState([]);
  const [newImages, setNewImages] = useState([]);
  const [existingImages, setExistingImages] = useState([]);
  const [subcategories, setSubcategories] = useState([]);
  const [specifications, setSpecifications] = useState([]);

  // Load product data when available
  useEffect(() => {
    if (product) {
      setFormData({
        name: product.name || '',
        description: product.description || '',
        sku: product.sku || '',
        barcode: product.barcode || '',
        category: product.category?.id || product.category || '',
        subcategory: product.subcategory?.id || product.subcategory || '',
        price: product.price || '',
        compare_price: product.compare_price || '',
        cost_price: product.cost_price || '',
        stock_quantity: product.stock_quantity || 0,
        low_stock_threshold: product.low_stock_threshold || 10,
        weight: product.weight || '',
        is_active: product.is_active ?? true,
        is_featured: product.is_featured ?? false,
      });

      // Load existing images
      if (product.images) {
        setExistingImages(product.images.map(img => ({
          ...img,
          url: getMediaUrl(img.image)
        })));
      }

      // Load existing variants
      if (product.variants) {
        setVariants(product.variants.map(v => ({
          ...v,
          isExisting: true,
        })));
      }

      setSpecifications(
        (product.specifications || []).map((row) => ({
          name: row.name || '',
          value: row.value || '',
        })),
      );

      // Set subcategories if category is selected
      if (product.category) {
        const categoryId = product.category?.id || product.category;
        const category = categories.find(c => c.id === categoryId);
        setSubcategories(category?.subcategories || []);
      }
    }
  }, [product, categories]);

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

  // Variant management
  const addVariant = () => {
    const newVariant = {
      id: `new-${Date.now()}`,
      sku: '',
      barcode: '',
      size: '',
      color: '',
      price: formData.price || '',
      stock_quantity: 0,
      low_stock_threshold: 10,
      is_active: true,
      isNew: true,
    };
    const timestamp = Date.now().toString().slice(-10);
    const random = Math.floor(Math.random() * 100).toString().padStart(2, '0');
    newVariant.barcode = `ZZV${timestamp}${random}`;
    setVariants([...variants, newVariant]);
  };

  const updateVariantData = (id, field, value) => {
    setVariants(variants.map(v =>
      v.id === id ? { ...v, [field]: value, isModified: !v.isNew } : v
    ));
  };

  const removeVariantHandler = async (variant) => {
    if (variant.isExisting && !variant.isNew) {
      try {
        await deleteVariant({ productId: id, variantId: variant.id }).unwrap();
        toast.success('Variant deleted');
      } catch (error) {
        toast.error('Failed to delete variant');
        return;
      }
    }
    setVariants(variants.filter(v => v.id !== variant.id));
  };

  // Image handling
  const handleImageUpload = (e) => {
    const files = Array.from(e.target.files);
    files.forEach(file => {
      const reader = new FileReader();
      reader.onloadend = () => {
        setNewImages(prev => [...prev, {
          id: Date.now() + Math.random(),
          file,
          preview: reader.result,
          is_primary: existingImages.length === 0 && newImages.length === 0,
        }]);
      };
      reader.readAsDataURL(file);
    });
  };

  const removeNewImage = (id) => {
    setNewImages(newImages.filter(img => img.id !== id));
  };

  const removeExistingImage = async (imageId) => {
    try {
      await deleteProductImage(imageId).unwrap();
      setExistingImages(existingImages.filter(img => img.id !== imageId));
      toast.success('Image deleted');
    } catch (error) {
      toast.error('Failed to delete image');
    }
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

    setLoading(true);
    try {
      // Update product
      const productData = {
        id,
        name: formData.name,
        description: formData.description,
        sku: formData.sku || null,
        barcode: formData.barcode,
        category: formData.category,
        subcategory: formData.subcategory || null,
        price: parseFloat(formData.price),
        compare_price: formData.compare_price ? parseFloat(formData.compare_price) : null,
        cost_price: formData.cost_price ? parseFloat(formData.cost_price) : null,
        stock_quantity: parseInt(formData.stock_quantity),
        low_stock_threshold: parseInt(formData.low_stock_threshold),
        weight: formData.weight ? parseFloat(formData.weight) : null,
        is_active: formData.is_active,
        is_featured: formData.is_featured,
        specifications: specResult.specifications,
      };

      await updateProduct(productData).unwrap();

      // Upload new images
      if (newImages.length > 0) {
        for (const img of newImages) {
          const imageData = new FormData();
          imageData.append('image', img.file);
          imageData.append('is_primary', img.is_primary ? 'true' : 'false');
          try {
            await uploadProductImage({ productId: id, imageData }).unwrap();
          } catch (imgError) {
            console.error('Image upload error:', imgError);
            toast.error('Failed to upload an image');
          }
        }
      }

      // Handle variants
      for (const variant of variants) {
        if (variant.isNew) {
          try {
            await createVariant({
              productId: id,
              sku: variant.sku,
              barcode: variant.barcode,
              size: variant.size,
              color: variant.color,
              price: variant.price ? parseFloat(variant.price) : null,
              stock_quantity: parseInt(variant.stock_quantity),
              low_stock_threshold: parseInt(variant.low_stock_threshold ?? 10),
              is_active: variant.is_active,
            }).unwrap();
          } catch (varError) {
            console.error('Variant creation error:', varError);
          }
        } else if (variant.isModified) {
          try {
            await updateVariant({
              productId: id,
              variantId: variant.id,
              sku: variant.sku,
              barcode: variant.barcode,
              size: variant.size,
              color: variant.color,
              price: variant.price ? parseFloat(variant.price) : null,
              stock_quantity: parseInt(variant.stock_quantity),
              low_stock_threshold: parseInt(variant.low_stock_threshold ?? 10),
              is_active: variant.is_active,
            }).unwrap();
          } catch (varError) {
            console.error('Variant update error:', varError);
          }
        }
      }

      toast.success('Product updated successfully!');
      refetch();
      setNewImages([]);
    } catch (error) {
      console.error('Failed to update product:', error);
      toast.error(error?.data?.detail || 'Failed to update product');
    } finally {
      setLoading(false);
    }
  };

  const sizes = ['XS', 'S', 'M', 'L', 'XL', 'XXL', '3XL', '28', '30', '32', '34', '36', '38', '40', '42'];
  const colors = [
    'Black', 'White', 'Red', 'Blue', 'Green', 'Yellow', 'Orange', 'Purple',
    'Pink', 'Brown', 'Gray', 'Navy', 'Beige', 'Maroon', 'Olive'
  ];

  if (productLoading) {
    return (
      <AdminLayout title="Edit Product">
        <div className="flex items-center justify-center min-h-[400px]">
          <RefreshCw className="w-8 h-8 animate-spin text-primary-600" />
        </div>
      </AdminLayout>
    );
  }

  if (!product) {
    return (
      <AdminLayout title="Edit Product">
        <div className="text-center py-16">
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Product not found</h2>
          <p className="text-gray-500 mb-4">The product you're looking for doesn't exist.</p>
          <button onClick={() => router.push('/products')} className="btn btn-primary">
            Back to Products
          </button>
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout title={`Edit: ${product.name}`}>
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
            <h1 className="text-2xl font-semibold text-gray-900">Edit Product</h1>
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
              Save Changes
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
                      SKU <span className="text-gray-400 text-xs">(Optional)</span>
                    </label>
                    <input
                      type="text"
                      name="sku"
                      value={formData.sku}
                      onChange={handleInputChange}
                      className="input"
                      placeholder="Enter SKU"
                    />
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
                  Product Barcode
                </h2>
                <div className="flex items-center gap-2">
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
            {variants.length === 0 && (
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

            {/* Variants */}
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">Product Variants</h2>
                <button
                  type="button"
                  onClick={addVariant}
                  className="btn btn-secondary text-sm"
                >
                  <Plus className="w-4 h-4 mr-1" />
                  Add Variant
                </button>
              </div>

              {variants.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <p>No variants. Add variants for different sizes, colors, etc.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {variants.map((variant, index) => (
                    <div key={variant.id} className="border rounded-lg p-4 bg-gray-50">
                      <div className="flex items-center justify-between mb-3">
                        <span className="font-medium text-sm">
                          Variant #{index + 1}
                          {variant.isNew && <span className="ml-2 text-xs text-green-600">(New)</span>}
                        </span>
                        <button
                          type="button"
                          onClick={() => removeVariantHandler(variant)}
                          className="text-red-500 hover:text-red-700"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>

                      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Size</label>
                          <select
                            value={variant.size || ''}
                            onChange={(e) => updateVariantData(variant.id, 'size', e.target.value)}
                            className="input text-sm"
                          >
                            <option value="">Select size</option>
                            {sizes.map(size => (
                              <option key={size} value={size}>{size}</option>
                            ))}
                          </select>
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Color</label>
                          <select
                            value={variant.color || ''}
                            onChange={(e) => updateVariantData(variant.id, 'color', e.target.value)}
                            className="input text-sm"
                          >
                            <option value="">Select color</option>
                            {colors.map(color => (
                              <option key={color} value={color}>{color}</option>
                            ))}
                          </select>
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Price (৳)</label>
                          <input
                            type="number"
                            value={variant.price || ''}
                            onChange={(e) => updateVariantData(variant.id, 'price', e.target.value)}
                            className="input text-sm"
                            placeholder="Same as product"
                            step="0.01"
                            min="0"
                          />
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Stock</label>
                          <input
                            type="number"
                            value={variant.stock_quantity || 0}
                            onChange={(e) => updateVariantData(variant.id, 'stock_quantity', e.target.value)}
                            className="input text-sm"
                            min="0"
                          />
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Low Stock Alert</label>
                          <input
                            type="number"
                            value={variant.low_stock_threshold ?? 10}
                            onChange={(e) => updateVariantData(variant.id, 'low_stock_threshold', e.target.value)}
                            className="input text-sm"
                            min="0"
                          />
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-3 mt-3">
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Variant SKU</label>
                          <input
                            type="text"
                            value={variant.sku || ''}
                            onChange={(e) => updateVariantData(variant.id, 'sku', e.target.value)}
                            className="input text-sm"
                            placeholder="e.g., TSH-BLK-M"
                          />
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Variant Barcode</label>
                          <div className="flex gap-2">
                            <input
                              type="text"
                              value={variant.barcode || ''}
                              onChange={(e) => updateVariantData(variant.id, 'barcode', e.target.value)}
                              className="input text-sm flex-1 font-mono"
                              readOnly
                            />
                            <button
                              type="button"
                              onClick={() => {
                                const timestamp = Date.now().toString().slice(-10);
                                const random = Math.floor(Math.random() * 100).toString().padStart(2, '0');
                                const barcode = `ZZV-${timestamp}${random}`;
                                updateVariantData(variant.id, 'barcode', barcode);
                              }}
                              className="btn btn-secondary px-2"
                              title="Regenerate barcode"
                            >
                              <RefreshCw className="w-4 h-4" />
                            </button>
                            {variant.barcode && (
                              <button
                                type="button"
                                onClick={() => {
                                  const vName = `${formData.name} - ${variant.size || ''} ${variant.color || ''}`.trim();
                                  const vPrice = variant.price || formData.price;
                                  const pw = window.open('', '_blank');
                                  pw.document.write(`<!DOCTYPE html><html><head><title>Variant Barcode</title>
                                    <style>body{font-family:Arial;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:20px}
                                    .bc{text-align:center;padding:20px;border:2px dashed #ccc;border-radius:8px}
                                    .name{font-size:16px;font-weight:bold;margin-bottom:8px}.price{font-size:20px;font-weight:bold;color:#059669;margin-top:8px}
                                    .sku{font-size:11px;color:#666;margin-top:4px}
                                    @media print{body{padding:0}.bc{border:none}}</style></head>
                                    <body><div class="bc"><div class="name">${vName}</div><svg id="bc"></svg>
                                    ${vPrice ? `<div class="price">৳${vPrice}</div>` : ''}
                                    ${variant.sku ? `<div class="sku">SKU: ${variant.sku}</div>` : ''}
                                    </div><script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>
                                    <script>JsBarcode("#bc","${variant.barcode}",{format:"CODE128",width:2,height:80,displayValue:true,fontSize:14,margin:10});
                                    setTimeout(()=>window.print(),500)</script></body></html>`);
                                  pw.document.close();
                                }}
                                className="btn btn-secondary px-2"
                                title="Print variant barcode"
                              >
                                <Printer className="w-4 h-4" />
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Images */}
            <div className="card">
              <h2 className="text-lg font-semibold mb-4">Product Images</h2>

              {/* Existing Images */}
              {existingImages.length > 0 && (
                <div className="mb-4">
                  <p className="text-sm text-gray-600 mb-2">Current Images</p>
                  <div className="grid grid-cols-4 gap-4">
                    {existingImages.map((img) => (
                      <div key={img.id} className="relative group">
                        <img
                          src={img.url}
                          alt="Product"
                          className={`w-full aspect-square object-cover rounded-lg border-2 ${img.is_primary ? 'border-primary-500' : 'border-transparent'}`}
                        />
                        <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg flex items-center justify-center">
                          <button
                            type="button"
                            onClick={() => removeExistingImage(img.id)}
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
                </div>
              )}

              {/* Upload New Images */}
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
                  <span className="text-gray-600 font-medium">Click to upload new images</span>
                  <span className="text-gray-400 text-sm mt-1">PNG, JPG up to 5MB each</span>
                </label>
              </div>

              {/* New Images Preview */}
              {newImages.length > 0 && (
                <div className="mt-4">
                  <p className="text-sm text-gray-600 mb-2">New Images to Upload</p>
                  <div className="grid grid-cols-4 gap-4">
                    {newImages.map((img) => (
                      <div key={img.id} className="relative group">
                        <img
                          src={img.preview}
                          alt="Product"
                          className="w-full aspect-square object-cover rounded-lg border-2 border-green-300"
                        />
                        <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg flex items-center justify-center">
                          <button
                            type="button"
                            onClick={() => removeNewImage(img.id)}
                            className="p-2 bg-red-500 text-white rounded-full"
                            title="Remove"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                        <span className="absolute top-2 left-2 bg-green-500 text-white text-xs px-2 py-1 rounded">
                          New
                        </span>
                      </div>
                    ))}
                  </div>
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
          </div>
        </div>
      </form>
    </AdminLayout>
  );
}

export async function getStaticPaths() {
  return { paths: [{ params: { id: '_' } }], fallback: false };
}

export async function getStaticProps() {
  return { props: {} };
}
