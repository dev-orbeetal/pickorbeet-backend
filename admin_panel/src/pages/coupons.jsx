import { useState } from 'react';
import { Plus, Edit, Trash2, Ticket, X, BarChart3, Copy, Check, Printer } from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import {
  useGetCouponsQuery,
  useCreateCouponMutation,
  useUpdateCouponMutation,
  useDeleteCouponMutation,
  useGetCouponStatsQuery,
} from '@/store/api/couponsApi';

export default function CouponsPage() {
  const token = typeof window !== 'undefined' ? localStorage.getItem('admin_access_token') : null;
  const { data: couponsData, isLoading: loading, error } = useGetCouponsQuery(undefined, {
    skip: !token,
  });
  const [createCoupon] = useCreateCouponMutation();
  const [updateCoupon] = useUpdateCouponMutation();
  const [deleteCoupon] = useDeleteCouponMutation();

  const coupons = Array.isArray(couponsData) ? couponsData : couponsData?.results || [];

  const [showModal, setShowModal] = useState(false);
  const [showStatsModal, setShowStatsModal] = useState(false);
  const [selectedCouponId, setSelectedCouponId] = useState(null);
  const [editingCoupon, setEditingCoupon] = useState(null);
  const [copiedCode, setCopiedCode] = useState(null);
  const [formData, setFormData] = useState({
    code: '',
    name: '',
    description: '',
    discount_type: 'percentage',
    discount_value: '',
    minimum_order_amount: '0',
    maximum_discount: '',
    usage_limit: '',
    usage_limit_per_user: '1',
    valid_from: '',
    valid_until: '',
    is_active: true,
    first_order_only: false,
    new_users_only: false,
  });

  const handleSubmit = async (e) => {
    e.preventDefault();

    const submitData = {
      ...formData,
      discount_value: parseFloat(formData.discount_value) || 0,
      minimum_order_amount: parseFloat(formData.minimum_order_amount) || 0,
      maximum_discount: formData.maximum_discount ? parseFloat(formData.maximum_discount) : null,
      usage_limit: formData.usage_limit ? parseInt(formData.usage_limit) : null,
      usage_limit_per_user: formData.usage_limit_per_user ? parseInt(formData.usage_limit_per_user) : null,
      valid_from: formData.valid_from || null,
      valid_until: formData.valid_until || null,
    };

    try {
      if (editingCoupon) {
        await updateCoupon({ id: editingCoupon.id, data: submitData }).unwrap();
        toast.success('Coupon updated successfully');
      } else {
        await createCoupon(submitData).unwrap();
        toast.success('Coupon created successfully');
      }
      resetForm();
    } catch (error) {
      toast.error(error.data?.detail || error.data?.code?.[0] || 'Failed to save coupon');
    }
  };

  const handleEdit = (coupon) => {
    setEditingCoupon(coupon);
    setFormData({
      code: coupon.code || '',
      name: coupon.name || '',
      description: coupon.description || '',
      discount_type: coupon.discount_type || 'percentage',
      discount_value: coupon.discount_value?.toString() || '',
      minimum_order_amount: coupon.minimum_order_amount?.toString() || '0',
      maximum_discount: coupon.maximum_discount?.toString() || '',
      usage_limit: coupon.usage_limit?.toString() || '',
      usage_limit_per_user: coupon.usage_limit_per_user?.toString() || '1',
      valid_from: coupon.valid_from ? coupon.valid_from.slice(0, 16) : '',
      valid_until: coupon.valid_until ? coupon.valid_until.slice(0, 16) : '',
      is_active: coupon.is_active ?? true,
      first_order_only: coupon.first_order_only ?? false,
      new_users_only: coupon.new_users_only ?? false,
    });
    setShowModal(true);
  };

  const handleDelete = async (id) => {
    if (confirm('Are you sure you want to delete this coupon?')) {
      try {
        await deleteCoupon(id).unwrap();
        toast.success('Coupon deleted successfully');
      } catch (error) {
        toast.error(error.data?.detail || 'Failed to delete coupon');
      }
    }
  };

  const handleViewStats = (couponId) => {
    setSelectedCouponId(couponId);
    setShowStatsModal(true);
  };

  const copyCode = (code) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(code);
    toast.success('Coupon code copied!');
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const printVoucher = (coupon) => {
    const printWindow = window.open('', '_blank');
    const voucherHTML = `
      <!DOCTYPE html>
      <html>
        <head>
          <title>Voucher - ${coupon.code}</title>
          <style>
            @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Inter:wght@400;500;600&display=swap');
            
            * { margin: 0; padding: 0; box-sizing: border-box; }
            
            body {
              font-family: 'Inter', sans-serif;
              background: #f5f5f5;
              display: flex;
              justify-content: center;
              align-items: center;
              min-height: 100vh;
              padding: 20px;
            }
            
            .voucher {
              width: 500px;
              background: linear-gradient(135deg, #8B2942 0%, #6B1D32 100%);
              border-radius: 20px;
              overflow: hidden;
              box-shadow: 0 20px 60px rgba(139, 41, 66, 0.3);
              position: relative;
            }
            
            .voucher::before {
              content: '';
              position: absolute;
              top: 0;
              left: 0;
              right: 0;
              bottom: 0;
              background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.05'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
              pointer-events: none;
            }
            
            .voucher-header {
              padding: 30px 30px 20px;
              text-align: center;
              position: relative;
              z-index: 1;
            }
            
            .logo {
              font-family: 'Playfair Display', serif;
              font-size: 32px;
              font-weight: 700;
              color: #D4AF37;
              letter-spacing: 2px;
              margin-bottom: 5px;
            }
            
            .tagline {
              color: rgba(255,255,255,0.7);
              font-size: 11px;
              letter-spacing: 3px;
              text-transform: uppercase;
            }
            
            .voucher-body {
              background: white;
              margin: 0 20px 20px;
              border-radius: 16px;
              padding: 30px;
              text-align: center;
              position: relative;
              z-index: 1;
            }
            
            .discount-badge {
              display: inline-block;
              background: linear-gradient(135deg, #D4AF37 0%, #B8962E 100%);
              color: #1a1a1a;
              font-size: 42px;
              font-weight: 700;
              padding: 15px 40px;
              border-radius: 12px;
              margin-bottom: 20px;
              box-shadow: 0 4px 15px rgba(212, 175, 55, 0.3);
            }
            
            .coupon-name {
              font-family: 'Playfair Display', serif;
              font-size: 24px;
              color: #1a1a1a;
              margin-bottom: 10px;
            }
            
            .coupon-description {
              color: #666;
              font-size: 14px;
              margin-bottom: 25px;
            }
            
            .code-container {
              background: #f8f5f0;
              border: 2px dashed #D4AF37;
              border-radius: 12px;
              padding: 20px;
              margin-bottom: 20px;
            }
            
            .code-label {
              color: #8B2942;
              font-size: 11px;
              letter-spacing: 2px;
              text-transform: uppercase;
              margin-bottom: 8px;
            }
            
            .code {
              font-family: 'Courier New', monospace;
              font-size: 32px;
              font-weight: bold;
              color: #8B2942;
              letter-spacing: 3px;
            }
            
            .terms {
              font-size: 11px;
              color: #999;
              line-height: 1.6;
            }
            
            .terms strong {
              color: #666;
            }
            
            .voucher-footer {
              padding: 15px 30px 25px;
              text-align: center;
              position: relative;
              z-index: 1;
            }
            
            .validity {
              color: rgba(255,255,255,0.8);
              font-size: 12px;
            }
            
            .validity strong {
              color: #D4AF37;
            }
            
            .decorative-circle {
              position: absolute;
              width: 40px;
              height: 40px;
              background: #f5f5f5;
              border-radius: 50%;
              z-index: 2;
            }
            
            .circle-left {
              left: -20px;
              top: 50%;
              transform: translateY(-50%);
            }
            
            .circle-right {
              right: -20px;
              top: 50%;
              transform: translateY(-50%);
            }
            
            @media print {
              body { background: white; padding: 0; }
              .voucher { box-shadow: none; }
            }
          </style>
        </head>
        <body>
          <div class="voucher">
            <div class="decorative-circle circle-left"></div>
            <div class="decorative-circle circle-right"></div>
            
            <div class="voucher-header">
              <div class="logo">ZZUHANA</div>
              <div class="tagline">Premium Fashion & Lifestyle</div>
            </div>
            
            <div class="voucher-body">
              <div class="discount-badge">
                ${coupon.discount_type === 'percentage' ? coupon.discount_value + '%' : '৳' + coupon.discount_value}
                <span style="font-size: 16px; font-weight: 500; display: block;">OFF</span>
              </div>
              
              <h2 class="coupon-name">${coupon.name}</h2>
              <p class="coupon-description">${coupon.description || 'Exclusive discount for our valued customers'}</p>
              
              <div class="code-container">
                <p class="code-label">Your Exclusive Code</p>
                <p class="code">${coupon.code}</p>
              </div>
              
              <p class="terms">
                ${parseFloat(coupon.minimum_order_amount) > 0 ? `<strong>Min. Order:</strong> ৳${coupon.minimum_order_amount} • ` : ''}
                ${coupon.maximum_discount ? `<strong>Max Discount:</strong> ৳${coupon.maximum_discount} • ` : ''}
                ${coupon.usage_limit_per_user ? `<strong>Limit:</strong> ${coupon.usage_limit_per_user} use per customer` : ''}
              </p>
            </div>
            
            <div class="voucher-footer">
              <p class="validity">
                ${coupon.valid_until
        ? `Valid until <strong>${new Date(coupon.valid_until).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</strong>`
        : 'No expiration date'
      }
              </p>
            </div>
          </div>
          
          <script>
            setTimeout(() => window.print(), 500);
          </script>
        </body>
      </html>
    `;
    printWindow.document.write(voucherHTML);
    printWindow.document.close();
  };

  const resetForm = () => {
    setFormData({
      code: '',
      name: '',
      description: '',
      discount_type: 'percentage',
      discount_value: '',
      minimum_order_amount: '0',
      maximum_discount: '',
      usage_limit: '',
      usage_limit_per_user: '1',
      valid_from: '',
      valid_until: '',
      is_active: true,
      first_order_only: false,
      new_users_only: false,
    });
    setEditingCoupon(null);
    setShowModal(false);
  };

  const getCouponStatus = (coupon) => {
    if (!coupon.is_active) return { label: 'Inactive', class: 'badge-gray' };
    const now = new Date();
    if (coupon.valid_from && new Date(coupon.valid_from) > now) return { label: 'Scheduled', class: 'badge-warning' };
    if (coupon.valid_until && new Date(coupon.valid_until) < now) return { label: 'Expired', class: 'badge-danger' };
    if (coupon.usage_limit && coupon.times_used >= coupon.usage_limit) return { label: 'Exhausted', class: 'badge-danger' };
    return { label: 'Active', class: 'badge-success' };
  };

  const formatDiscount = (coupon) => {
    if (coupon.discount_type === 'percentage') {
      return `${coupon.discount_value}%`;
    }
    return `৳${coupon.discount_value}`;
  };

  return (
    <AdminLayout title="Coupons">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Coupons</h2>
          <p className="text-gray-600">Create and manage discount coupons for your store</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="btn btn-primary"
        >
          <Plus className="w-4 h-4 mr-2" />
          Add Coupon
        </button>
      </div>

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b">
              <div className="flex items-center justify-between">
                <h3 className="text-xl font-semibold">
                  {editingCoupon ? 'Edit Coupon' : 'Create New Coupon'}
                </h3>
                <button
                  onClick={resetForm}
                  className="p-2 hover:bg-gray-100 rounded-lg"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              {/* Code & Name */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Coupon Code *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.code}
                    onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                    className="input uppercase"
                    placeholder="e.g., WELCOME10"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="input"
                    placeholder="Welcome Discount"
                  />
                </div>
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="input"
                  rows={2}
                  placeholder="Description for internal use"
                />
              </div>

              {/* Discount Type & Value */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Discount Type *
                  </label>
                  <select
                    value={formData.discount_type}
                    onChange={(e) => setFormData({ ...formData, discount_type: e.target.value })}
                    className="input"
                  >
                    <option value="percentage">Percentage (%)</option>
                    <option value="fixed">Fixed Amount (৳)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Discount Value *
                  </label>
                  <input
                    type="number"
                    required
                    value={formData.discount_value}
                    onChange={(e) => setFormData({ ...formData, discount_value: e.target.value })}
                    className="input"
                    min="0"
                    step={formData.discount_type === 'percentage' ? '1' : '0.01'}
                    max={formData.discount_type === 'percentage' ? '100' : undefined}
                    placeholder={formData.discount_type === 'percentage' ? '10' : '100'}
                  />
                </div>
              </div>

              {/* Min Order & Max Discount */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Minimum Order Amount (৳)
                  </label>
                  <input
                    type="number"
                    value={formData.minimum_order_amount}
                    onChange={(e) => setFormData({ ...formData, minimum_order_amount: e.target.value })}
                    className="input"
                    min="0"
                    step="0.01"
                    placeholder="0"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Maximum Discount (৳)
                    <span className="text-xs text-gray-500 font-normal ml-1">(optional)</span>
                  </label>
                  <input
                    type="number"
                    value={formData.maximum_discount}
                    onChange={(e) => setFormData({ ...formData, maximum_discount: e.target.value })}
                    className="input"
                    min="0"
                    step="0.01"
                    placeholder="No limit"
                  />
                </div>
              </div>

              {/* Usage Limits */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Total Usage Limit
                    <span className="text-xs text-gray-500 font-normal ml-1">(optional)</span>
                  </label>
                  <input
                    type="number"
                    value={formData.usage_limit}
                    onChange={(e) => setFormData({ ...formData, usage_limit: e.target.value })}
                    className="input"
                    min="1"
                    placeholder="Unlimited"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Uses Per Customer
                  </label>
                  <input
                    type="number"
                    value={formData.usage_limit_per_user}
                    onChange={(e) => setFormData({ ...formData, usage_limit_per_user: e.target.value })}
                    className="input"
                    min="1"
                    placeholder="1"
                  />
                </div>
              </div>

              {/* Validity Period */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Valid From
                  </label>
                  <input
                    type="datetime-local"
                    value={formData.valid_from}
                    onChange={(e) => setFormData({ ...formData, valid_from: e.target.value })}
                    className="input"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Valid Until
                  </label>
                  <input
                    type="datetime-local"
                    value={formData.valid_until}
                    onChange={(e) => setFormData({ ...formData, valid_until: e.target.value })}
                    className="input"
                  />
                </div>
              </div>

              {/* Restrictions */}
              <div className="space-y-3 pt-2">
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={formData.is_active}
                    onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                    className="mr-2 h-4 w-4"
                  />
                  <span className="text-sm font-medium text-gray-700">Active</span>
                </label>
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={formData.first_order_only}
                    onChange={(e) => setFormData({ ...formData, first_order_only: e.target.checked })}
                    className="mr-2 h-4 w-4"
                  />
                  <span className="text-sm font-medium text-gray-700">First Order Only</span>
                  <span className="text-xs text-gray-500 ml-2">(Only applies to customer's first purchase)</span>
                </label>
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={formData.new_users_only}
                    onChange={(e) => setFormData({ ...formData, new_users_only: e.target.checked })}
                    className="mr-2 h-4 w-4"
                  />
                  <span className="text-sm font-medium text-gray-700">New Users Only</span>
                  <span className="text-xs text-gray-500 ml-2">(Account created within 7 days)</span>
                </label>
              </div>

              {/* Actions */}
              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={resetForm}
                  className="btn btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                >
                  {editingCoupon ? 'Update' : 'Create'} Coupon
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Stats Modal */}
      {showStatsModal && selectedCouponId && (
        <CouponStatsModal
          couponId={selectedCouponId}
          onClose={() => {
            setShowStatsModal(false);
            setSelectedCouponId(null);
          }}
        />
      )}

      {/* Error Display */}
      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-800">Error loading coupons: {error.status || 'Unknown'}</p>
          <p className="text-red-600 text-sm">{error.data?.detail || 'Please check your connection and try again'}</p>
        </div>
      )}

      {/* Coupons Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Code</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Name</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Discount</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Usage</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Valid Until</th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {loading ? (
                [...Array(5)].map((_, i) => (
                  <tr key={i}>
                    <td colSpan={7} className="px-6 py-4">
                      <div className="h-4 bg-gray-200 rounded animate-pulse" />
                    </td>
                  </tr>
                ))
              ) : coupons.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-gray-500">
                    <Ticket className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                    <p>No coupons found. Create your first coupon.</p>
                  </td>
                </tr>
              ) : (
                coupons.map((coupon) => {
                  const status = getCouponStatus(coupon);
                  return (
                    <tr key={coupon.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <div className="flex items-center">
                          <code className="px-2 py-1 bg-gray-100 rounded text-sm font-mono font-bold text-primary-600">
                            {coupon.code}
                          </code>
                          <button
                            onClick={() => copyCode(coupon.code)}
                            className="ml-2 p-1 text-gray-400 hover:text-gray-600"
                            title="Copy code"
                          >
                            {copiedCode === coupon.code ? (
                              <Check className="w-4 h-4 text-green-500" />
                            ) : (
                              <Copy className="w-4 h-4" />
                            )}
                          </button>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div>
                          <p className="font-medium text-gray-900">{coupon.name}</p>
                          {coupon.description && (
                            <p className="text-sm text-gray-500 truncate max-w-xs">{coupon.description}</p>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div>
                          <span className="font-semibold text-green-600">{formatDiscount(coupon)}</span>
                          {parseFloat(coupon.minimum_order_amount) > 0 && (
                            <p className="text-xs text-gray-500">Min: ৳{coupon.minimum_order_amount}</p>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div>
                          <span className="font-medium">{coupon.times_used || 0}</span>
                          {coupon.usage_limit && (
                            <span className="text-gray-500">/{coupon.usage_limit}</span>
                          )}
                          {!coupon.usage_limit && (
                            <span className="text-gray-500 text-xs ml-1">(unlimited)</span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`badge ${status.class}`}>{status.label}</span>
                        <div className="mt-1 flex gap-1">
                          {coupon.first_order_only && (
                            <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">1st Order</span>
                          )}
                          {coupon.new_users_only && (
                            <span className="text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded">New Users</span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {coupon.valid_until ? (
                          new Date(coupon.valid_until).toLocaleDateString('en-US', {
                            year: 'numeric',
                            month: 'short',
                            day: 'numeric',
                          })
                        ) : (
                          <span className="text-gray-400">No expiry</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end space-x-1">
                          <button
                            onClick={() => printVoucher(coupon)}
                            className="p-2 text-primary-600 hover:bg-primary-50 rounded-lg"
                            title="Print Voucher"
                          >
                            <Printer className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleViewStats(coupon.id)}
                            className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg"
                            title="View Stats"
                          >
                            <BarChart3 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleEdit(coupon)}
                            className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg"
                            title="Edit"
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDelete(coupon.id)}
                            className="p-2 text-red-600 hover:bg-red-50 rounded-lg"
                            title="Delete"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </AdminLayout>
  );
}

function CouponStatsModal({ couponId, onClose }) {
  const { data: stats, isLoading } = useGetCouponStatsQuery(couponId);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl max-w-lg w-full max-h-[80vh] overflow-y-auto">
        <div className="p-6 border-b flex items-center justify-between">
          <h3 className="text-xl font-semibold">Coupon Statistics</h3>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6">
          {isLoading ? (
            <div className="space-y-4">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-16 bg-gray-200 rounded animate-pulse" />
              ))}
            </div>
          ) : stats ? (
            <>
              <div className="grid grid-cols-3 gap-4 mb-6">
                <div className="bg-blue-50 rounded-lg p-4 text-center">
                  <p className="text-2xl font-bold text-blue-600">{stats.total_times_used}</p>
                  <p className="text-sm text-gray-600">Times Used</p>
                </div>
                <div className="bg-green-50 rounded-lg p-4 text-center">
                  <p className="text-2xl font-bold text-green-600">৳{stats.total_discount_given}</p>
                  <p className="text-sm text-gray-600">Total Discount</p>
                </div>
                <div className="bg-purple-50 rounded-lg p-4 text-center">
                  <p className="text-2xl font-bold text-purple-600">{stats.unique_users}</p>
                  <p className="text-sm text-gray-600">Unique Users</p>
                </div>
              </div>

              {stats.recent_usages?.length > 0 && (
                <div>
                  <h4 className="font-semibold text-gray-900 mb-3">Recent Usage</h4>
                  <div className="space-y-2">
                    {stats.recent_usages.map((usage, idx) => (
                      <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                        <div>
                          <p className="font-medium text-sm">{usage.order_number}</p>
                          <p className="text-xs text-gray-500">{usage.user_email}</p>
                        </div>
                        <div className="text-right">
                          <p className="font-semibold text-green-600">-৳{usage.discount_amount}</p>
                          <p className="text-xs text-gray-500">
                            {new Date(usage.used_at).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <p className="text-center text-gray-500">Failed to load statistics</p>
          )}
        </div>

        <div className="p-4 border-t">
          <button onClick={onClose} className="btn btn-secondary w-full">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
