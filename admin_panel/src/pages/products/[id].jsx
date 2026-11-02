import { useEffect, useState, useRef } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import {
  Save, ArrowLeft, Upload, RefreshCw,
  Barcode, Printer, Image as ImageIcon, X, Copy, Check
} from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import { useGetCategoriesQuery } from '@/store/api/categoriesApi';
import {
  useGetProductQuery,
  useUpdateProductMutation,
  useUploadProductImageMutation,
  useUpdateProductImageMutation,
  useDeleteProductImageMutation,
  useSyncVariantSetupMutation,
  useGetStoreSettingsQuery,
  useGetSellersQuery,
} from '@/store/api/productsApi';
import JsBarcode from 'jsbarcode';
import { getMediaUrl, routeId } from '@/lib/utils';
import SpecificationFields, { cleanSpecifications } from '@/components/products/SpecificationFields';
import VariantOptions from '@/components/products/VariantOptions';

function variantSelections(variant) {
  if (Array.isArray(variant?.options) && variant.options.length) {
    return variant.options.map((option) => ({ name: option.name, label: option.label }));
  }
  const selections = [];
  if (variant?.size) selections.push({ name: 'Size', label: variant.size });
  if (variant?.color) selections.push({ name: 'Color', label: variant.color });
  return selections;
}

function selectionsMatch(left, right) {
  if (!left?.length || !right?.length || left.length !== right.length) return false;
  return left.every((item) => right.some((other) => other.name === item.name && other.label === item.label));
}

function variantLabel(variant) {
  const labels = variantSelections(variant).map((item) => item.label);
  return labels.length ? labels.join(' / ') : (variant.sku || 'Variant');
}

export default function EditProductPage() {
  const router = useRouter();
  const id = routeId(router);
  const barcodeRef = useRef(null);
  const variantRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [hasVariants, setHasVariants] = useState(false);
  const [copied, setCopied] = useState(false);

  const { data: product, isLoading: productLoading, refetch } = useGetProductQuery(id, { skip: !id });
  const { data: categoriesData } = useGetCategoriesQuery();
  const { data: storeSettings } = useGetStoreSettingsQuery();
  const { data: sellers = [] } = useGetSellersQuery();
  const [updateProduct] = useUpdateProductMutation();
  const [uploadProductImage] = useUploadProductImageMutation();
  const [updateProductImage] = useUpdateProductImageMutation();
  const [deleteProductImage] = useDeleteProductImageMutation();
  const [syncVariantSetup] = useSyncVariantSetupMutation();
  const [variantSnapshot, setVariantSnapshot] = useState(null);
  const [allProductImages, setAllProductImages] = useState([]);

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
    warehouse_stock: 0,
    dealer_stock: 0,
    dealer_available: false,
    low_stock_threshold: 10,
    weight: '',
    is_active: true,
    is_featured: false,
    is_official: false,
    warranty_period: '',
    supply_type: 'available_stock',
    supplied_by: '',
  });

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
        warehouse_stock: product.warehouse_stock || 0,
        dealer_stock: product.dealer_stock || 0,
        dealer_available: product.dealer_available ?? false,
        low_stock_threshold: product.low_stock_threshold || 10,
        weight: product.weight || '',
        is_active: product.is_active ?? true,
        is_featured: product.is_featured ?? false,
        is_official: product.is_official ?? false,
        warranty_period: product.warranty_period || '',
        supply_type: product.supply_type || 'available_stock',
        supplied_by: product.supplied_by || '',
      });

      // Shared gallery images (variant-linked ones are edited on each combination)
      if (product.images) {
        const mapped = product.images.map((img) => ({
          ...img,
          url: getMediaUrl(img.image),
        }));
        setAllProductImages(mapped);
        setExistingImages(mapped.filter((img) => !img.variant));
      }

      setHasVariants((product.variants || []).length > 0);

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
    if (formData.supply_type === 'seller_provided' && !formData.supplied_by) {
      toast.error('Select the seller who provides this product');
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
        low_stock_threshold: parseInt(formData.low_stock_threshold),
        dealer_available: formData.dealer_available,
        weight: formData.weight ? parseFloat(formData.weight) : null,
        is_active: formData.is_active,
        is_featured: formData.is_featured,
        is_official: formData.is_official,
        warranty_period: formData.warranty_period,
        supply_type: formData.supply_type,
        supplied_by: formData.supply_type === 'seller_provided' ? formData.supplied_by : null,
        specifications: specResult.specifications,
      };

      await updateProduct(productData).unwrap();

      // Upload new shared product images
      if (newImages.length > 0) {
        for (const img of newImages) {
          const imageData = new FormData();
          imageData.append('image', img.file);
          imageData.append('is_primary', img.is_primary ? 'true' : 'false');
          if (img.variant) imageData.append('variant', img.variant);
          try {
            await uploadProductImage({ productId: id, imageData }).unwrap();
          } catch (imgError) {
            console.error('Image upload error:', imgError);
            toast.error('Failed to upload an image');
          }
        }
      }

      if (setup?.payload) {
        const saved = await syncVariantSetup({ productId: id, ...setup.payload }).unwrap();
        setVariantSnapshot(saved);

        for (const imageId of setup.removedImageIds || []) {
          try {
            await deleteProductImage(imageId).unwrap();
          } catch (error) {
            console.error('Failed to remove variant image:', error);
          }
        }

        for (const pending of setup.pendingImages || []) {
          const match = (saved.variants || []).find((variant) => (
            String(variant.id) === String(pending.variantId)
            || selectionsMatch(pending.selections, variantSelections(variant))
          ));
          if (!match) continue;
          if (pending.replaceImageId) {
            try {
              await deleteProductImage(pending.replaceImageId).unwrap();
            } catch (error) {
              console.error('Failed to replace variant image:', error);
            }
          }
          const imageData = new FormData();
          imageData.append('image', pending.file);
          imageData.append('is_primary', 'false');
          imageData.append('variant', match.id);
          try {
            await uploadProductImage({ productId: id, imageData }).unwrap();
          } catch (imgError) {
            console.error('Variant image upload error:', imgError);
            toast.error('Failed to upload a variant image');
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

            {/* Stock — quantity is transaction-driven; only threshold + dealer availability are edited here */}
            {!hasVariants && (
              <div className="card">
                <h2 className="text-lg font-semibold mb-4">Stock & dealer availability</h2>
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Warehouse stock</label>
                    <input
                      type="number"
                      value={formData.warehouse_stock}
                      className="input bg-gray-50"
                      readOnly
                      disabled
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Calculated from purchases and sales.{' '}
                      <Link href="/finance" className="text-primary-600 font-medium">Finance</Link>
                      {' '}records restocks.
                    </p>
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
                <label className="flex items-center justify-between cursor-pointer border border-gray-200 rounded-xl p-3">
                  <span>
                    <span className="block text-sm font-medium text-gray-700">Dealer availability</span>
                    <span className="block text-xs text-gray-500">
                      Allow dealer fulfillment when warehouse stock is empty. This is a yes/no flag, not a stock quantity.
                    </span>
                  </span>
                  <input
                    type="checkbox"
                    name="dealer_available"
                    checked={formData.dealer_available}
                    onChange={handleInputChange}
                    className="toggle"
                  />
                </label>
              </div>
            )}

            <VariantOptions
              key={`${product.id}:${(variantSnapshot?.variants || product.variants || []).map((variant) => variant.id).join(',')}:${allProductImages.map((image) => `${image.id}:${image.variant || ''}`).join('|')}`}
              ref={variantRef}
              productSku={formData.sku}
              barcodePrefix={storeSettings?.barcode_prefix || 'ZZ'}
              productName={formData.name}
              productPrice={formData.price}
              initialGroups={variantSnapshot?.option_groups || product.option_groups}
              initialVariants={variantSnapshot?.variants || product.variants}
              productImages={allProductImages}
              onCount={(count) => setHasVariants(count > 0)}
            />

            {/* Images */}
            <div className="card">
              <h2 className="text-lg font-semibold mb-4">Shared Product Images</h2>
              <p className="text-sm text-gray-500 mb-4">
                These show for every variant. Add per-variant photos on each combination above.
              </p>

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
                        {(variantSnapshot?.variants || product.variants || []).length > 0 && (
                          <select
                            value={img.variant || ''}
                            onChange={async (event) => {
                              const variant = event.target.value || null;
                              try {
                                await updateProductImage({
                                  imageId: img.id,
                                  productId: id,
                                  variant,
                                }).unwrap();
                                setExistingImages((current) => (
                                  variant
                                    ? current.filter((item) => item.id !== img.id)
                                    : current.map((item) => (
                                      item.id === img.id ? { ...item, variant } : item
                                    ))
                                ));
                                setAllProductImages((current) => current.map((item) => (
                                  item.id === img.id ? { ...item, variant } : item
                                )));
                                toast.success(variant ? 'Image moved to variant' : 'Image is shared');
                              } catch (error) {
                                toast.error('Could not update image');
                              }
                            }}
                            className="absolute bottom-1 left-1 right-1 rounded bg-white/95 px-1 py-0.5 text-[10px] text-gray-700"
                            title="Assign to variant"
                          >
                            <option value="">All variants</option>
                            {(variantSnapshot?.variants || product.variants || []).map((variant) => (
                              <option key={variant.id} value={variant.id}>
                                {variantLabel(variant)}
                              </option>
                            ))}
                          </select>
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
                <label className="flex items-center justify-between gap-3 cursor-pointer">
                  <span>
                    <span className="block text-gray-700">Show in Trending</span>
                    <span className="block text-xs text-gray-500">Homepage on website &amp; app</span>
                  </span>
                  <input
                    type="checkbox"
                    name="is_featured"
                    checked={formData.is_featured}
                    onChange={handleInputChange}
                    className="toggle"
                  />
                </label>
                {hasVariants && (
                  <label className="flex items-center justify-between cursor-pointer">
                    <span>
                      <span className="block text-gray-700">Dealer availability</span>
                      <span className="block text-xs text-gray-500">Independent of warehouse stock</span>
                    </span>
                    <input
                      type="checkbox"
                      name="dealer_available"
                      checked={formData.dealer_available}
                      onChange={handleInputChange}
                      className="toggle"
                    />
                  </label>
                )}
              </div>
            </div>

            
            <div className="card">
              <h2 className="text-lg font-semibold mb-4">Inventory source</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Classification</label>
                  <select
                    name="supply_type"
                    value={formData.supply_type}
                    onChange={handleInputChange}
                    className="input"
                  >
                    <option value="available_stock">Available Stock</option>
                    <option value="seller_provided">Seller-Provided</option>
                  </select>
                  <p className="text-xs text-gray-500 mt-1">
                    Internal only. Shoppers do not see this classification.
                  </p>
                </div>
                {formData.supply_type === 'seller_provided' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Seller <span className="text-red-500">*</span>
                    </label>
                    <select
                      name="supplied_by"
                      value={formData.supplied_by || ''}
                      onChange={handleInputChange}
                      className="input"
                      required
                    >
                      <option value="">Select seller</option>
                      {sellers.map((seller) => (
                        <option key={seller.id} value={seller.id}>{seller.full_name}</option>
                      ))}
                    </select>
                  </div>
                )}
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
