import { useState } from 'react';
import { useRouter } from 'next/router';
import {
  Save, ArrowLeft, Plus, Trash2, Upload, RefreshCw,
  Image as ImageIcon, X
} from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import { useGetCategoriesQuery } from '@/store/api/categoriesApi';
import {
  useCreateProductMutation,
  useUploadProductImageMutation,
  useCreateVariantMutation,
  useGetSellersQuery,
} from '@/store/api/productsApi';

export default function NewProductPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const { data: categoriesData } = useGetCategoriesQuery();
  const { data: sellers = [] } = useGetSellersQuery();
  const [createProduct] = useCreateProductMutation();
  const [uploadProductImage] = useUploadProductImageMutation();
  const [createVariant] = useCreateVariantMutation();

  const categories = Array.isArray(categoriesData?.results || categoriesData)
    ? (categoriesData?.results || categoriesData)
    : [];

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    sku: '',
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
    supply_type: 'available_stock',
    supplied_by: '',
  });

  const [variants, setVariants] = useState([]);
  const [images, setImages] = useState([]);
  const [subcategories, setSubcategories] = useState([]);

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

  // Variant management
  const addVariant = () => {
    setVariants([...variants, {
      id: Date.now(),
      sku: '',
      size: '',
      color: '',
      price: formData.price || '',
      stock_quantity: 0,
      low_stock_threshold: 10,
      is_active: true,
    }]);
  };

  const updateVariant = (id, field, value) => {
    setVariants(variants.map(v =>
      v.id === id ? { ...v, [field]: value } : v
    ));
  };

  const removeVariant = (id) => {
    setVariants(variants.filter(v => v.id !== id));
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
    const openingUnits = variants.length
      ? variants.reduce((sum, variant) => sum + (parseInt(variant.stock_quantity, 10) || 0), 0)
      : parseInt(formData.stock_quantity, 10) || 0;
    if (openingUnits > 0 && !(Number(formData.cost_price) > 0)) {
      toast.error('Enter a cost price to record opening stock as a purchase');
      return;
    }

    setLoading(true);
    try {
      const productData = {
        name: formData.name,
        description: formData.description,
        sku: formData.sku,
        category: formData.category,
        price: parseFloat(formData.price),
        compare_price: formData.compare_price ? parseFloat(formData.compare_price) : null,
        cost_price: formData.cost_price ? parseFloat(formData.cost_price) : null,
        stock_quantity: variants.length ? 0 : parseInt(formData.stock_quantity || 0, 10),
        low_stock_threshold: parseInt(formData.low_stock_threshold),
        subcategory: formData.subcategory || null,
        is_active: formData.is_active,
        is_featured: formData.is_featured,
        supply_type: formData.supply_type,
        supplied_by: formData.supply_type === 'seller_provided' ? formData.supplied_by : null,
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

      // Create variants if any
      let variantErrors = 0;
      if (variants.length > 0) {
        for (const variant of variants) {
          try {
            await createVariant({
              productId,
              sku: variant.sku,
              size: variant.size,
              color: variant.color,
              price: variant.price ? parseFloat(variant.price) : null,
              stock_quantity: parseInt(variant.stock_quantity),
              low_stock_threshold: parseInt(variant.low_stock_threshold ?? 10),
              is_active: variant.is_active,
            }).unwrap();
          } catch (varError) {
            variantErrors++;
            console.error('Variant creation error:', varError);
          }
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

  const sizes = ['XS', 'S', 'M', 'L', 'XL', 'XXL', '3XL', '28', '30', '32', '34', '36', '38', '40', '42'];
  const colors = [
    'Black', 'White', 'Red', 'Blue', 'Green', 'Yellow', 'Orange', 'Purple',
    'Pink', 'Brown', 'Gray', 'Navy', 'Beige', 'Maroon', 'Olive'
  ];

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
                    Cost price (৳)
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
                  <p className="text-xs text-gray-500 mt-1">Unit cost for opening stock. Later purchases from Inventory update the weighted average.</p>
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
                      Opening stock
                    </label>
                    <input
                      type="number"
                      name="stock_quantity"
                      value={formData.stock_quantity}
                      onChange={handleInputChange}
                      className="input"
                      min="0"
                    />
                    <p className="text-xs text-gray-500 mt-1">Recorded as a purchase voucher at the cost price above. Later stock changes are made from Inventory.</p>
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
                  <p>No variants added. Add variants for different sizes, colors, etc.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {variants.map((variant, index) => (
                    <div key={variant.id} className="border rounded-lg p-4 bg-gray-50">
                      <div className="flex items-center justify-between mb-3">
                        <span className="font-medium text-sm">Variant #{index + 1}</span>
                        <button
                          type="button"
                          onClick={() => removeVariant(variant.id)}
                          className="text-red-500 hover:text-red-700"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>

                      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Size</label>
                          <select
                            value={variant.size}
                            onChange={(e) => updateVariant(variant.id, 'size', e.target.value)}
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
                            value={variant.color}
                            onChange={(e) => updateVariant(variant.id, 'color', e.target.value)}
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
                            value={variant.price}
                            onChange={(e) => updateVariant(variant.id, 'price', e.target.value)}
                            className="input text-sm"
                            placeholder="Same as product"
                            step="0.01"
                            min="0"
                          />
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Opening stock</label>
                          <input
                            type="number"
                            value={variant.stock_quantity}
                            onChange={(e) => updateVariant(variant.id, 'stock_quantity', e.target.value)}
                            className="input text-sm"
                            min="0"
                          />
                          <p className="text-xs text-gray-500 mt-1">Purchased at the product cost price.</p>
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Low Stock Alert</label>
                          <input
                            type="number"
                            value={variant.low_stock_threshold ?? 10}
                            onChange={(e) => updateVariant(variant.id, 'low_stock_threshold', e.target.value)}
                            className="input text-sm"
                            min="0"
                          />
                        </div>
                      </div>

                      <div className="mt-3">
                        <label className="block text-xs font-medium text-gray-600 mb-1">Variant SKU</label>
                        <input
                          type="text"
                          value={variant.sku}
                          onChange={(e) => updateVariant(variant.id, 'sku', e.target.value)}
                          className="input text-sm"
                          placeholder="e.g., TSH-BLK-M"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

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
                      value={formData.supplied_by}
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
          </div>
        </div>
      </form>
    </AdminLayout>
  );
}
