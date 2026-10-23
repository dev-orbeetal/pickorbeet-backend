import { useRef, useState } from 'react';
import { useRouter } from 'next/router';
import {
  ArrowLeft, Printer, Package, Truck, CheckCircle,
  XCircle, Clock, MapPin, Phone, Mail, User,
  RotateCcw, AlertTriangle, X, ChevronRight,
  ShoppingBag, BoxIcon, Send, CircleDot, Ban, RefreshCw
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useReactToPrint } from 'react-to-print';
import AdminLayout from '@/components/layout/AdminLayout';
import { useGetOrderQuery, useUpdateOrderStatusMutation, useBookShipmentMutation, useRefreshShipmentMutation } from '@/store/api/ordersApi';
import SteadfastCard from '@/components/orders/SteadfastCard';
import { getMediaUrl, routeId } from '@/lib/utils';

const ALL_STATUSES = [
  { key: 'pending', label: 'Pending', icon: Clock, color: 'yellow', ring: 'ring-yellow-400', bg: 'bg-yellow-50', text: 'text-yellow-700', border: 'border-yellow-200', activeBg: 'bg-yellow-500', activeText: 'text-white' },
  { key: 'confirmed', label: 'Confirmed', icon: CheckCircle, color: 'blue', ring: 'ring-blue-400', bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200', activeBg: 'bg-blue-500', activeText: 'text-white' },
  { key: 'processing', label: 'Processing', icon: Package, color: 'purple', ring: 'ring-purple-400', bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200', activeBg: 'bg-purple-500', activeText: 'text-white' },
  { key: 'shipped', label: 'Shipped', icon: Send, color: 'indigo', ring: 'ring-indigo-400', bg: 'bg-indigo-50', text: 'text-indigo-700', border: 'border-indigo-200', activeBg: 'bg-indigo-500', activeText: 'text-white' },
  { key: 'out_for_delivery', label: 'Out for Delivery', icon: Truck, color: 'cyan', ring: 'ring-cyan-400', bg: 'bg-cyan-50', text: 'text-cyan-700', border: 'border-cyan-200', activeBg: 'bg-cyan-500', activeText: 'text-white' },
  { key: 'delivered', label: 'Delivered', icon: CheckCircle, color: 'green', ring: 'ring-green-400', bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200', activeBg: 'bg-green-500', activeText: 'text-white' },
  { key: 'cancelled', label: 'Cancelled', icon: XCircle, color: 'red', ring: 'ring-red-400', bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200', activeBg: 'bg-red-500', activeText: 'text-white' },
  { key: 'refunded', label: 'Refunded', icon: RefreshCw, color: 'orange', ring: 'ring-orange-400', bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200', activeBg: 'bg-orange-500', activeText: 'text-white' },
];

const MAIN_FLOW = ['pending', 'confirmed', 'processing', 'shipped', 'out_for_delivery', 'delivered'];

function StatusChangeModal({ isOpen, onClose, targetStatus, currentStatus, onConfirm, updating }) {
  const [note, setNote] = useState('');
  if (!isOpen || !targetStatus) return null;

  const statusInfo = ALL_STATUSES.find(s => s.key === targetStatus);
  const currentInfo = ALL_STATUSES.find(s => s.key === currentStatus);
  const isReverse = MAIN_FLOW.indexOf(targetStatus) < MAIN_FLOW.indexOf(currentStatus) && MAIN_FLOW.includes(targetStatus);
  const isDangerous = targetStatus === 'cancelled' || targetStatus === 'refunded';

  const handleSubmit = () => {
    onConfirm(targetStatus, note.trim());
    setNote('');
  };

  const Icon = statusInfo?.icon || Clock;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden">
        {/* Header */}
        <div className={`px-6 py-5 ${isDangerous ? 'bg-red-50' : isReverse ? 'bg-amber-50' : 'bg-gray-50'} border-b`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {isDangerous ? (
                <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
                  <AlertTriangle className="w-5 h-5 text-red-600" />
                </div>
              ) : isReverse ? (
                <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center">
                  <RotateCcw className="w-5 h-5 text-amber-600" />
                </div>
              ) : (
                <div className={`w-10 h-10 rounded-full ${statusInfo?.bg} flex items-center justify-center`}>
                  <Icon className={`w-5 h-5 ${statusInfo?.text}`} />
                </div>
              )}
              <div>
                <h3 className="text-lg font-semibold text-gray-900">
                  {isDangerous ? 'Confirm Action' : isReverse ? 'Reverse Status' : 'Update Status'}
                </h3>
                <p className="text-sm text-gray-500">
                  {currentInfo?.label} → {statusInfo?.label}
                </p>
              </div>
            </div>
            <button onClick={onClose} className="p-1 hover:bg-gray-200 rounded-lg transition-colors">
              <X className="w-5 h-5 text-gray-400" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-4">
          {isReverse && (
            <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-xl text-sm">
              <RotateCcw className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
              <p className="text-amber-800">
                You are reversing the order status from <strong>{currentInfo?.label}</strong> back to <strong>{statusInfo?.label}</strong>. This will be recorded in the status history.
              </p>
            </div>
          )}
          {isDangerous && (
            <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-xl text-sm">
              <AlertTriangle className="w-4 h-4 text-red-600 mt-0.5 flex-shrink-0" />
              <p className="text-red-800">
                {targetStatus === 'cancelled' ? 'Cancelling this order may affect inventory and customer notifications.' : 'Refunding this order will mark the payment as refunded.'}
              </p>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Note <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              className="w-full px-3 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none placeholder-gray-400"
              placeholder={isReverse ? 'Reason for reversing status...' : isDangerous ? 'Reason for this action...' : 'Add a note about this change...'}
            />
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-gray-50 border-t flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-xl hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={updating}
            className={`px-5 py-2 text-sm font-medium rounded-xl transition-all ${isDangerous
              ? 'bg-red-600 text-white hover:bg-red-700 disabled:bg-red-400'
              : `${statusInfo?.activeBg} ${statusInfo?.activeText} hover:opacity-90 disabled:opacity-50`
              }`}
          >
            {updating ? (
              <span className="flex items-center gap-2">
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Updating...
              </span>
            ) : (
              `Change to ${statusInfo?.label}`
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function OrderDetailPage() {
  const router = useRouter();
  const id = routeId(router);
  const printRef = useRef();
  const [statusModal, setStatusModal] = useState({ open: false, target: null });

  const { data: order, isLoading: loading, error } = useGetOrderQuery(id, {
    skip: !id,
  });
  const [updateOrderStatus, { isLoading: updating }] = useUpdateOrderStatusMutation();
  const [bookShipment, { isLoading: booking }] = useBookShipmentMutation();
  const [refreshShipment, { isLoading: refreshingCourier }] = useRefreshShipmentMutation();

  if (error) {
    toast.error('Failed to fetch order');
    router.push('/orders');
  }

  const handleStatusClick = (statusKey) => {
    if (statusKey === order?.order_status) return;
    setStatusModal({ open: true, target: statusKey });
  };

  const confirmStatusChange = async (newStatus, note) => {
    try {
      const payload = { id, status: newStatus };
      if (note) payload.note = note;
      await updateOrderStatus(payload).unwrap();
      toast.success(`Status updated to ${ALL_STATUSES.find(s => s.key === newStatus)?.label}`);
      setStatusModal({ open: false, target: null });
    } catch (error) {
      toast.error('Failed to update status');
    }
  };

  const handleBook = async (note) => {
    try {
      await bookShipment({ id, note }).unwrap();
      toast.success('Parcel booked with Steadfast');
    } catch (error) {
      toast.error(error?.data?.error || 'Could not book this parcel');
    }
  };

  const handleRefreshCourier = async () => {
    try {
      await refreshShipment(id).unwrap();
      toast.success('Courier status updated');
    } catch (error) {
      toast.error(error?.data?.error || 'Could not refresh the courier status');
    }
  };

  const handlePrint = useReactToPrint({
    content: () => printRef.current,
    documentTitle: `Order-${order?.order_number}`,
  });

  const getStatusColor = (status) => {
    const colors = {
      pending: 'text-yellow-600 bg-yellow-100',
      confirmed: 'text-blue-600 bg-blue-100',
      processing: 'text-purple-600 bg-purple-100',
      shipped: 'text-indigo-600 bg-indigo-100',
      out_for_delivery: 'text-cyan-600 bg-cyan-100',
      delivered: 'text-green-600 bg-green-100',
      cancelled: 'text-red-600 bg-red-100',
      refunded: 'text-orange-600 bg-orange-100',
    };
    return colors[status] || 'text-gray-600 bg-gray-100';
  };

  if (loading) {
    return (
      <AdminLayout title="Order Details">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-1/4" />
          <div className="h-64 bg-gray-200 rounded" />
        </div>
      </AdminLayout>
    );
  }

  if (!order) return null;

  const currentIdx = MAIN_FLOW.indexOf(order.order_status);
  const isTerminal = order.order_status === 'cancelled' || order.order_status === 'refunded';

  return (
    <AdminLayout title={`Order ${order.order_number}`}>
      {/* Status Change Modal */}
      <StatusChangeModal
        isOpen={statusModal.open}
        onClose={() => setStatusModal({ open: false, target: null })}
        targetStatus={statusModal.target}
        currentStatus={order.order_status}
        onConfirm={confirmStatusChange}
        updating={updating}
      />

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <button
          onClick={() => router.push('/orders')}
          className="flex items-center text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Orders
        </button>

        <div className="flex items-center space-x-3">
          <button onClick={handlePrint} className="btn btn-secondary">
            <Printer className="w-4 h-4 mr-2" />
            Print Voucher
          </button>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Main Info */}
        <div className="lg:col-span-2 space-y-6">
          {/* Order Status — Interactive Stepper */}
          <div className="card p-6">
            <div className="flex items-center justify-between mb-2">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Order Status</h2>
                <p className="text-sm text-gray-500">
                  Reference: {order.tracking_number}
                  {order.shipment?.tracking_code ? ` · Steadfast ${order.shipment.tracking_code}` : ''}
                </p>
              </div>
              <span className={`badge text-sm px-3 py-1 ${getStatusColor(order.order_status)}`}>
                {order.order_status.replace(/_/g, ' ')}
              </span>
            </div>
            <p className="text-xs text-gray-400 mb-5">Click any status to change. You can reverse or skip steps freely.</p>

            {/* Main Flow Stepper */}
            <div className="relative">
              {/* Progress line background */}
              <div className="absolute top-5 left-5 right-5 h-0.5 bg-gray-200 z-0" />
              {/* Progress line filled */}
              {!isTerminal && currentIdx >= 0 && (
                <div
                  className="absolute top-5 left-5 h-0.5 bg-gradient-to-r from-green-400 to-green-500 z-0 transition-all duration-500"
                  style={{ width: `${(currentIdx / (MAIN_FLOW.length - 1)) * (100 - (10 / MAIN_FLOW.length))}%` }}
                />
              )}

              <div className="relative z-10 flex justify-between">
                {MAIN_FLOW.map((statusKey, idx) => {
                  const info = ALL_STATUSES.find(s => s.key === statusKey);
                  const Icon = info.icon;
                  const isCurrent = order.order_status === statusKey;
                  const isPassed = !isTerminal && currentIdx >= 0 && idx < currentIdx;
                  const isFuture = !isTerminal && currentIdx >= 0 && idx > currentIdx;

                  return (
                    <button
                      key={statusKey}
                      onClick={() => handleStatusClick(statusKey)}
                      disabled={isCurrent || updating}
                      className="flex flex-col items-center group w-16 disabled:cursor-default"
                      title={isCurrent ? 'Current status' : `Change to ${info.label}`}
                    >
                      <div
                        className={`w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300 ${isCurrent
                          ? `${info.activeBg} ${info.activeText} ring-4 ${info.ring}/30 scale-110 shadow-lg`
                          : isPassed
                            ? 'bg-green-100 text-green-600 ring-2 ring-green-300/50'
                            : isTerminal
                              ? 'bg-gray-100 text-gray-400'
                              : 'bg-gray-100 text-gray-400 group-hover:bg-gray-200 group-hover:text-gray-600 group-hover:ring-2 group-hover:ring-gray-300 group-hover:scale-105'
                          }`}
                      >
                        {isPassed ? (
                          <CheckCircle className="w-5 h-5" />
                        ) : (
                          <Icon className="w-5 h-5" />
                        )}
                      </div>
                      <span className={`mt-2 text-[10px] leading-tight text-center font-medium transition-colors ${isCurrent ? info.text : isPassed ? 'text-green-600' : 'text-gray-400 group-hover:text-gray-600'
                        }`}>
                        {info.label}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Terminal Statuses (Cancelled / Refunded) */}
            <div className="flex items-center gap-3 mt-6 pt-5 border-t border-dashed border-gray-200">
              {ALL_STATUSES.filter(s => !MAIN_FLOW.includes(s.key)).map((info) => {
                const Icon = info.icon;
                const isCurrent = order.order_status === info.key;
                return (
                  <button
                    key={info.key}
                    onClick={() => handleStatusClick(info.key)}
                    disabled={isCurrent || updating}
                    className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all disabled:cursor-default ${isCurrent
                      ? `${info.activeBg} ${info.activeText} ring-2 ${info.ring}/30 shadow-md`
                      : `${info.bg} ${info.text} ${info.border} border hover:shadow-md hover:scale-[1.02]`
                      }`}
                    title={isCurrent ? 'Current status' : `Change to ${info.label}`}
                  >
                    <Icon className="w-4 h-4" />
                    {info.label}
                  </button>
                );
              })}
              {isTerminal && (
                <button
                  onClick={() => handleStatusClick('pending')}
                  disabled={updating}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 hover:shadow-md hover:scale-[1.02] transition-all ml-auto"
                >
                  <RotateCcw className="w-4 h-4" />
                  Reopen Order
                </button>
              )}
            </div>
          </div>

          {/* Order Items */}
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Order Items</h2>
            <div className="space-y-4">
              {order.items?.map((item) => (
                <div key={item.id} className="flex items-center gap-4 pb-4 border-b last:border-0">
                  <div className="w-16 h-16 bg-gray-100 rounded-lg flex-shrink-0 overflow-hidden flex items-center justify-center">
                    {item.product_image ? (
                      <img src={getMediaUrl(item.product_image)} alt={item.product_name} className="w-full h-full object-cover" />
                    ) : (
                      <Package className="w-6 h-6 text-gray-300" />
                    )}
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-gray-900">{item.product_name}</p>
                    <p className="text-sm text-gray-500">
                      SKU: {item.product_sku}
                      {item.size && ` | Size: ${item.size}`}
                      {item.color && ` | Color: ${item.color}`}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-gray-600">৳{parseFloat(item.unit_price).toLocaleString()} × {item.quantity}</p>
                    <p className="font-semibold">৳{parseFloat(item.total_price).toLocaleString()}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Status History */}
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Status History</h2>
            <div className="space-y-4">
              {order.status_history?.map((history, index) => (
                <div key={history.id} className="flex items-start gap-3">
                  <div className="w-2 h-2 mt-2 bg-primary-500 rounded-full" />
                  <div>
                    <p className="font-medium text-gray-900 capitalize">
                      {history.status.replace('_', ' ')}
                    </p>
                    {history.note && <p className="text-sm text-gray-600">{history.note}</p>}
                    <p className="text-xs text-gray-400">
                      {new Date(history.created_at).toLocaleString()}
                      {history.changed_by_name && ` by ${history.changed_by_name}`}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <SteadfastCard
            order={order}
            onBook={handleBook}
            onRefresh={handleRefreshCourier}
            booking={booking}
            refreshing={refreshingCourier}
          />

          {/* Customer Info */}
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Customer</h2>
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <User className="w-4 h-4 text-gray-400" />
                <span className="text-gray-700">{order.customer_name}</span>
              </div>
              {order.customer_phone && (
                <div className="flex items-center gap-3">
                  <Phone className="w-4 h-4 text-gray-400" />
                  <span className="text-gray-700">{order.customer_phone}</span>
                </div>
              )}
              {order.customer_email && (
                <div className="flex items-center gap-3">
                  <Mail className="w-4 h-4 text-gray-400" />
                  <span className="text-gray-700">{order.customer_email}</span>
                </div>
              )}
            </div>
          </div>

          {/* Shipping Address */}
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Shipping Address</h2>
            <div className="flex items-start gap-3">
              <MapPin className="w-4 h-4 text-gray-400 mt-1" />
              <div className="text-gray-700">
                <p>{order.shipping_name}</p>
                <p>{order.shipping_phone}</p>
                <p>{order.shipping_address_line1}</p>
                {order.shipping_address_line2 && <p>{order.shipping_address_line2}</p>}
                <p>{order.shipping_city}, {order.shipping_district}</p>
              </div>
            </div>
          </div>

          {/* Payment Summary */}
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Payment</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Subtotal</span>
                <span>৳{parseFloat(order.subtotal).toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Delivery</span>
                <span>৳{parseFloat(order.delivery_charge).toLocaleString()}</span>
              </div>
              {parseFloat(order.discount) > 0 && (
                <div className="flex justify-between text-green-600">
                  <span>Discount</span>
                  <span>-৳{parseFloat(order.discount).toLocaleString()}</span>
                </div>
              )}
              <div className="flex justify-between font-semibold text-lg pt-2 border-t">
                <span>Total</span>
                <span className="text-primary-600">৳{parseFloat(order.total).toLocaleString()}</span>
              </div>
              <div className="pt-2">
                <span className={`badge ${order.payment_status === 'paid' ? 'badge-success' : 'badge-warning'}`}>
                  {order.payment_status}
                </span>
                {order.payment_method && (
                  <span className="ml-2 text-gray-500">{order.payment_method}</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Print Template (Hidden) — Elegant Burgundy & Cream Voucher */}
      <div className="hidden">
        <div ref={printRef} style={{ fontFamily: "'Inter', 'Segoe UI', sans-serif", color: '#1F1F1F', maxWidth: '800px', margin: '0 auto', padding: '0', background: '#ffffff' }}>
          {/* Thin elegant burgundy top accent */}
          <div style={{ height: '4px', background: '#FF861F' }} />

          <div style={{ position: 'relative', padding: '32px 40px 36px' }}>
            {/* Very subtle heart watermark — barely visible */}
            <div style={{
              position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, opacity: 0.02, zIndex: 0, pointerEvents: 'none',
              backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 100 100'%3E%3Cpath d='M50 85s-35-25-35-47.5c0-13.75 8.75-22.5 17.5-22.5 6.25 0 12.5 3.75 17.5 12.5 5-8.75 11.25-12.5 17.5-12.5 8.75 0 17.5 8.75 17.5 22.5 0 22.5-35 47.5-35 47.5z' fill='%238B2942'/%3E%3C/svg%3E")`,
              backgroundSize: '100px 100px'
            }} />

            <div style={{ position: 'relative', zIndex: 1 }}>

              {/* Header — Logo + Invoice Info */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '28px', paddingBottom: '20px', borderBottom: '1.5px solid #E4E9F2' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                  <img src="/images/logo.png" alt="PickOrbeet" style={{ height: '52px', width: 'auto' }} />
                  <div>
                    <p style={{ fontSize: '9px', color: '#202D70', margin: 0, letterSpacing: '3px', textTransform: 'uppercase', fontWeight: '600' }}>Premium Fashion & Lifestyle</p>
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <p style={{ fontFamily: "'Playfair Display', Georgia, serif", fontSize: '22px', fontWeight: '700', margin: '0 0 4px 0', color: '#202D70', letterSpacing: '1px' }}>INVOICE</p>
                  <p style={{ fontSize: '13px', color: '#404040', fontWeight: '600', margin: '0 0 2px 0' }}>#{order.order_number}</p>
                  <p style={{ fontSize: '11px', color: '#A3A3A3', margin: 0 }}>{new Date(order.created_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}</p>
                </div>
              </div>

              {/* Two Column: Ship To + Order Info — cream cards */}
              <div style={{ display: 'flex', gap: '16px', marginBottom: '28px' }}>
                <div style={{ flex: 1, background: '#F5F7FC', border: '1px solid #E4E9F2', borderRadius: '12px', padding: '18px 20px' }}>
                  <p style={{ fontSize: '9px', textTransform: 'uppercase', letterSpacing: '2.5px', color: '#202D70', fontWeight: '700', margin: '0 0 10px 0', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ display: 'inline-block', width: '14px', height: '1.5px', background: '#202D70', borderRadius: '1px' }} />
                    Ship To
                  </p>
                  <p style={{ fontWeight: '700', fontSize: '14px', margin: '0 0 3px 0', color: '#1F1F1F' }}>{order.shipping_name}</p>
                  <p style={{ fontSize: '12px', color: '#525252', margin: '0 0 2px 0' }}>{order.shipping_phone}</p>
                  <p style={{ fontSize: '12px', color: '#525252', margin: '0 0 2px 0' }}>{order.shipping_address_line1}</p>
                  {order.shipping_address_line2 && <p style={{ fontSize: '12px', color: '#525252', margin: '0 0 2px 0' }}>{order.shipping_address_line2}</p>}
                  <p style={{ fontSize: '12px', color: '#525252', margin: 0 }}>{order.shipping_city}, {order.shipping_district}</p>
                </div>
                <div style={{ flex: 1, background: '#F5F7FC', border: '1px solid #E4E9F2', borderRadius: '12px', padding: '18px 20px' }}>
                  <p style={{ fontSize: '9px', textTransform: 'uppercase', letterSpacing: '2.5px', color: '#202D70', fontWeight: '700', margin: '0 0 10px 0', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ display: 'inline-block', width: '14px', height: '1.5px', background: '#202D70', borderRadius: '1px' }} />
                    Order Details
                  </p>
                  <table style={{ fontSize: '12px', width: '100%' }}>
                    <tbody>
                      <tr><td style={{ color: '#737373', paddingBottom: '5px', paddingRight: '12px' }}>Reference:</td><td style={{ fontWeight: '600', color: '#1F1F1F', paddingBottom: '5px' }}>{order.tracking_number}</td></tr>
                      {order.shipment?.tracking_code && (
                        <tr><td style={{ color: '#737373', paddingBottom: '5px', paddingRight: '12px' }}>Steadfast:</td><td style={{ fontWeight: '600', color: '#1F1F1F', paddingBottom: '5px' }}>{order.shipment.tracking_code}</td></tr>
                      )}
                      <tr><td style={{ color: '#737373', paddingBottom: '5px', paddingRight: '12px' }}>Status:</td><td style={{ fontWeight: '600', color: '#1F1F1F', textTransform: 'capitalize', paddingBottom: '5px' }}>{order.order_status.replace(/_/g, ' ')}</td></tr>
                      <tr><td style={{ color: '#737373', paddingRight: '12px' }}>Payment:</td><td style={{ fontWeight: '600', color: '#1F1F1F', textTransform: 'capitalize' }}>{order.payment_status}{order.payment_method ? ` (${order.payment_method})` : ''}</td></tr>
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Items Table — clean with burgundy header */}
              <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: '0', marginBottom: '24px', borderRadius: '12px', overflow: 'hidden', border: '1px solid #E4E9F2' }}>
                <thead>
                  <tr style={{ background: '#202D70' }}>
                    <th style={{ textAlign: 'left', padding: '11px 14px', fontSize: '9px', textTransform: 'uppercase', letterSpacing: '1.5px', color: '#fff', fontWeight: '600' }}>#</th>
                    <th style={{ textAlign: 'left', padding: '11px 14px', fontSize: '9px', textTransform: 'uppercase', letterSpacing: '1.5px', color: '#fff', fontWeight: '600' }}>Item Description</th>
                    <th style={{ textAlign: 'center', padding: '11px 14px', fontSize: '9px', textTransform: 'uppercase', letterSpacing: '1.5px', color: '#fff', fontWeight: '600' }}>Qty</th>
                    <th style={{ textAlign: 'right', padding: '11px 14px', fontSize: '9px', textTransform: 'uppercase', letterSpacing: '1.5px', color: '#fff', fontWeight: '600' }}>Unit Price</th>
                    <th style={{ textAlign: 'right', padding: '11px 14px', fontSize: '9px', textTransform: 'uppercase', letterSpacing: '1.5px', color: '#fff', fontWeight: '600' }}>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {order.items?.map((item, idx) => (
                    <tr key={item.id} style={{ background: idx % 2 === 0 ? '#ffffff' : '#F5F7FC' }}>
                      <td style={{ padding: '11px 14px', fontSize: '12px', color: '#A3A3A3' }}>{idx + 1}</td>
                      <td style={{ padding: '11px 14px' }}>
                        <p style={{ fontSize: '13px', fontWeight: '600', margin: '0 0 2px 0', color: '#1F1F1F' }}>{item.product_name}</p>
                        <p style={{ fontSize: '11px', color: '#737373', margin: 0 }}>
                          {item.product_sku && `SKU: ${item.product_sku}`}
                          {item.size && ` · Size: ${item.size}`}
                          {item.color && ` · Color: ${item.color}`}
                        </p>
                      </td>
                      <td style={{ padding: '11px 14px', textAlign: 'center', fontSize: '13px', color: '#1F1F1F' }}>{item.quantity}</td>
                      <td style={{ padding: '11px 14px', textAlign: 'right', fontSize: '13px', color: '#404040' }}>৳{parseFloat(item.unit_price).toLocaleString()}</td>
                      <td style={{ padding: '11px 14px', textAlign: 'right', fontSize: '13px', fontWeight: '700', color: '#202D70' }}>৳{parseFloat(item.total_price).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Totals — cream box */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '28px' }}>
                <div style={{ background: '#F5F7FC', border: '1px solid #E4E9F2', borderRadius: '12px', padding: '16px 24px', minWidth: '280px' }}>
                  <table style={{ width: '100%' }}>
                    <tbody>
                      <tr>
                        <td style={{ padding: '5px 0', fontSize: '12px', color: '#737373' }}>Subtotal</td>
                        <td style={{ padding: '5px 0', fontSize: '13px', textAlign: 'right', color: '#1F1F1F' }}>৳{parseFloat(order.subtotal).toLocaleString()}</td>
                      </tr>
                      <tr>
                        <td style={{ padding: '5px 0', fontSize: '12px', color: '#737373' }}>Delivery Charge</td>
                        <td style={{ padding: '5px 0', fontSize: '13px', textAlign: 'right', color: '#1F1F1F' }}>৳{parseFloat(order.delivery_charge).toLocaleString()}</td>
                      </tr>
                      {parseFloat(order.discount) > 0 && (
                        <tr>
                          <td style={{ padding: '5px 0', fontSize: '12px', color: '#16a34a' }}>Discount</td>
                          <td style={{ padding: '5px 0', fontSize: '13px', textAlign: 'right', color: '#16a34a' }}>-৳{parseFloat(order.discount).toLocaleString()}</td>
                        </tr>
                      )}
                      <tr>
                        <td colSpan={2} style={{ padding: '8px 0 0 0' }}><div style={{ height: '1.5px', background: 'linear-gradient(90deg, transparent, #202D70, transparent)', borderRadius: '1px' }} /></td>
                      </tr>
                      <tr>
                        <td style={{ padding: '10px 0 0 0', fontFamily: "'Playfair Display', Georgia, serif", fontSize: '16px', fontWeight: '700', color: '#202D70' }}>Total</td>
                        <td style={{ padding: '10px 0 0 0', fontFamily: "'Playfair Display', Georgia, serif", fontSize: '20px', fontWeight: '700', textAlign: 'right', color: '#202D70' }}>৳{parseFloat(order.total).toLocaleString()}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Thank You Banner — soft cream with burgundy text */}
              <div style={{ background: '#F5F7FC', border: '1px solid #E4E9F2', borderRadius: '12px', padding: '20px 30px', textAlign: 'center', marginBottom: '24px' }}>
                <p style={{ fontFamily: "'Playfair Display', Georgia, serif", fontSize: '18px', fontWeight: '700', color: '#202D70', margin: '0 0 4px 0', letterSpacing: '0.5px' }}>
                  Thank You for Choosing PickOrbeet!
                </p>
                <p style={{ fontSize: '11px', color: '#737373', margin: 0, letterSpacing: '0.5px' }}>
                  Your style, our passion — we love having you!
                </p>
              </div>

              {/* Footer — subtle divider */}
              <div style={{ borderTop: '1px solid #E4E9F2', paddingTop: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <p style={{ fontSize: '11px', color: '#737373', margin: '0 0 2px 0' }}>For queries, contact us at support@PickOrbeet.com</p>
                  <p style={{ fontSize: '10px', color: '#A3A3A3', margin: 0 }}>This is a computer-generated invoice.</p>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <p style={{ fontSize: '12px', fontWeight: '600', color: '#202D70', margin: '0 0 2px 0' }}>www.PickOrbeet.com</p>
                  <p style={{ fontSize: '10px', color: '#A3A3A3', margin: 0 }}>Follow us on social media</p>
                </div>
              </div>
            </div>
          </div>

          {/* Thin elegant burgundy bottom accent */}
          <div style={{ height: '4px', background: '#FF861F' }} />
        </div>
      </div>
    </AdminLayout>
  );
}

export async function getStaticPaths() {
  return { paths: [{ params: { id: '_' } }], fallback: false };
}

export async function getStaticProps() {
  return { props: {} };
}
