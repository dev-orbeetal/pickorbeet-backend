import { useState } from 'react';
import {
  CreditCard, Search, Filter, RefreshCw, Eye,
  CheckCircle, XCircle, Clock, AlertTriangle,
  DollarSign, TrendingUp, ArrowDownLeft
} from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import { useGetPaymentsQuery, useGetRefundsQuery, useProcessRefundMutation } from '@/store/api/paymentsApi';

export default function PaymentsPage() {
  const { data: paymentsData, isLoading: paymentsLoading } = useGetPaymentsQuery();
  const { data: refundsData, isLoading: refundsLoading } = useGetRefundsQuery();
  const [processRefundMutation, { isLoading: processing }] = useProcessRefundMutation();

  const payments = Array.isArray(paymentsData?.results || paymentsData)
    ? (paymentsData?.results || paymentsData)
    : [];
  const refunds = Array.isArray(refundsData?.results || refundsData)
    ? (refundsData?.results || refundsData)
    : [];
  const loading = paymentsLoading || refundsLoading;

  const [activeTab, setActiveTab] = useState('payments');
  const [filters, setFilters] = useState({
    status: '',
    method: '',
    search: '',
  });
  const [selectedPayment, setSelectedPayment] = useState(null);
  const [showModal, setShowModal] = useState(false);

  const processRefund = async (refundId, action) => {
    try {
      await processRefundMutation({ id: refundId, action }).unwrap();
      toast.success(`Refund ${action === 'approve' ? 'approved' : 'rejected'} successfully`);
    } catch (error) {
      toast.error(error?.data?.error || 'Failed to process refund');
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      pending: { class: 'badge-warning', icon: Clock },
      completed: { class: 'badge-success', icon: CheckCircle },
      paid: { class: 'badge-success', icon: CheckCircle },
      failed: { class: 'badge-danger', icon: XCircle },
      refunded: { class: 'bg-purple-100 text-purple-800', icon: ArrowDownLeft },
    };
    const style = styles[status] || { class: 'badge-gray', icon: Clock };
    const Icon = style.icon;
    return (
      <span className={`badge ${style.class} flex items-center gap-1`}>
        <Icon className="w-3 h-3" />
        {status?.charAt(0).toUpperCase() + status?.slice(1)}
      </span>
    );
  };

  const getMethodIcon = (method) => {
    const methods = {
      sslcommerz: '💳',
      cod: '💵',
      cash: '💵',
      card: '💳',
      bkash: '📱',
      nagad: '📱',
    };
    return methods[method?.toLowerCase()] || '💳';
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const filteredPayments = payments.filter(payment => {
    if (filters.status && payment.status !== filters.status) return false;
    if (filters.method && payment.payment_method !== filters.method) return false;
    if (filters.search) {
      const search = filters.search.toLowerCase();
      return (
        payment.transaction_id?.toLowerCase().includes(search) ||
        payment.order?.order_number?.toLowerCase().includes(search)
      );
    }
    return true;
  });

  // Calculate stats
  const totalRevenue = payments
    .filter(p => p.status === 'completed' || p.status === 'paid')
    .reduce((sum, p) => sum + parseFloat(p.amount || 0), 0);
  const pendingPayments = payments.filter(p => p.status === 'pending').length;
  const totalRefunds = refunds.reduce((sum, r) => sum + parseFloat(r.amount || 0), 0);

  return (
    <AdminLayout title="Payments">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="stat-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Revenue</p>
              <p className="text-2xl font-bold text-gray-900">৳{totalRevenue.toLocaleString()}</p>
            </div>
            <div className="p-3 bg-green-100 rounded-xl">
              <DollarSign className="w-6 h-6 text-green-600" />
            </div>
          </div>
        </div>

        <div className="stat-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Payments</p>
              <p className="text-2xl font-bold text-gray-900">{payments.length}</p>
            </div>
            <div className="p-3 bg-blue-100 rounded-xl">
              <CreditCard className="w-6 h-6 text-blue-600" />
            </div>
          </div>
        </div>

        <div className="stat-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Pending</p>
              <p className="text-2xl font-bold text-yellow-600">{pendingPayments}</p>
            </div>
            <div className="p-3 bg-yellow-100 rounded-xl">
              <Clock className="w-6 h-6 text-yellow-600" />
            </div>
          </div>
        </div>

        <div className="stat-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Refunds</p>
              <p className="text-2xl font-bold text-purple-600">৳{totalRefunds.toLocaleString()}</p>
            </div>
            <div className="p-3 bg-purple-100 rounded-xl">
              <ArrowDownLeft className="w-6 h-6 text-purple-600" />
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-4 mb-6">
        <button
          onClick={() => setActiveTab('payments')}
          className={`px-4 py-2 font-medium rounded-lg transition-colors ${activeTab === 'payments'
              ? 'bg-primary-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
        >
          <CreditCard className="w-4 h-4 inline mr-2" />
          Payments ({payments.length})
        </button>
        <button
          onClick={() => setActiveTab('refunds')}
          className={`px-4 py-2 font-medium rounded-lg transition-colors ${activeTab === 'refunds'
              ? 'bg-primary-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
        >
          <ArrowDownLeft className="w-4 h-4 inline mr-2" />
          Refunds ({refunds.length})
        </button>
      </div>

      {activeTab === 'payments' && (
        <>
          {/* Filters */}
          <div className="card mb-6">
            <div className="flex flex-col md:flex-row gap-4">
              <div className="flex-1">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Search by transaction ID or order number..."
                    value={filters.search}
                    onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                    className="input pl-10"
                  />
                </div>
              </div>

              <select
                value={filters.status}
                onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                className="input w-auto"
              >
                <option value="">All Status</option>
                <option value="pending">Pending</option>
                <option value="completed">Completed</option>
                <option value="paid">Paid</option>
                <option value="failed">Failed</option>
                <option value="refunded">Refunded</option>
              </select>

              <select
                value={filters.method}
                onChange={(e) => setFilters({ ...filters, method: e.target.value })}
                className="input w-auto"
              >
                <option value="">All Methods</option>
                <option value="sslcommerz">SSLCommerz</option>
                <option value="cod">Cash on Delivery</option>
                <option value="cash">Cash</option>
                <option value="card">Card</option>
                <option value="bkash">bKash</option>
                <option value="nagad">Nagad</option>
              </select>

              <button
                onClick={() => {
                  setLoading(true);
                  fetchPayments();
                }}
                className="btn btn-secondary"
              >
                <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>
          </div>

          {/* Payments Table */}
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="px-4 py-3 text-left table-header">Transaction ID</th>
                    <th className="px-4 py-3 text-left table-header">Order</th>
                    <th className="px-4 py-3 text-left table-header">Method</th>
                    <th className="px-4 py-3 text-left table-header">Amount</th>
                    <th className="px-4 py-3 text-left table-header">Status</th>
                    <th className="px-4 py-3 text-left table-header">Date</th>
                    <th className="px-4 py-3 text-left table-header">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {loading ? (
                    [...Array(5)].map((_, i) => (
                      <tr key={i}>
                        <td colSpan="7" className="px-4 py-4">
                          <div className="animate-pulse flex space-x-4">
                            <div className="flex-1 space-y-2 py-1">
                              <div className="h-4 bg-gray-200 rounded w-3/4"></div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    ))
                  ) : filteredPayments.length === 0 ? (
                    <tr>
                      <td colSpan="7" className="px-4 py-12 text-center text-gray-500">
                        <CreditCard className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                        <p>No payments found</p>
                      </td>
                    </tr>
                  ) : (
                    filteredPayments.map((payment) => (
                      <tr key={payment.id} className="hover:bg-gray-50">
                        <td className="px-4 py-4">
                          <span className="font-mono text-sm text-gray-900">
                            {payment.transaction_id || '-'}
                          </span>
                        </td>
                        <td className="px-4 py-4">
                          <span className="text-primary-600 font-medium">
                            #{payment.order?.order_number || payment.order_id}
                          </span>
                        </td>
                        <td className="px-4 py-4">
                          <span className="flex items-center gap-2">
                            <span>{getMethodIcon(payment.payment_method)}</span>
                            <span className="capitalize">{payment.payment_method}</span>
                          </span>
                        </td>
                        <td className="px-4 py-4 font-semibold">
                          ৳{parseFloat(payment.amount || 0).toLocaleString()}
                        </td>
                        <td className="px-4 py-4">
                          {getStatusBadge(payment.status)}
                        </td>
                        <td className="px-4 py-4 text-sm text-gray-500">
                          {formatDate(payment.created_at)}
                        </td>
                        <td className="px-4 py-4">
                          <button
                            onClick={() => {
                              setSelectedPayment(payment);
                              setShowModal(true);
                            }}
                            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                            title="View Details"
                          >
                            <Eye className="w-4 h-4 text-gray-500" />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {activeTab === 'refunds' && (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-4 py-3 text-left table-header">Refund ID</th>
                  <th className="px-4 py-3 text-left table-header">Order</th>
                  <th className="px-4 py-3 text-left table-header">Amount</th>
                  <th className="px-4 py-3 text-left table-header">Reason</th>
                  <th className="px-4 py-3 text-left table-header">Status</th>
                  <th className="px-4 py-3 text-left table-header">Requested</th>
                  <th className="px-4 py-3 text-left table-header">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {refunds.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="px-4 py-12 text-center text-gray-500">
                      <ArrowDownLeft className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                      <p>No refund requests</p>
                    </td>
                  </tr>
                ) : (
                  refunds.map((refund) => (
                    <tr key={refund.id} className="hover:bg-gray-50">
                      <td className="px-4 py-4 font-mono text-sm">
                        {refund.id?.slice(0, 8)}...
                      </td>
                      <td className="px-4 py-4">
                        <span className="text-primary-600 font-medium">
                          #{refund.order?.order_number || refund.payment?.order_id}
                        </span>
                      </td>
                      <td className="px-4 py-4 font-semibold">
                        ৳{parseFloat(refund.amount || 0).toLocaleString()}
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-600 max-w-xs truncate">
                        {refund.reason || '-'}
                      </td>
                      <td className="px-4 py-4">
                        {getStatusBadge(refund.status)}
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-500">
                        {formatDate(refund.created_at)}
                      </td>
                      <td className="px-4 py-4">
                        {refund.status === 'pending' ? (
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => processRefund(refund.id, 'approve')}
                              disabled={processing}
                              className="p-2 bg-green-100 text-green-700 hover:bg-green-200 rounded-lg transition-colors"
                              title="Approve"
                            >
                              <CheckCircle className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => processRefund(refund.id, 'reject')}
                              disabled={processing}
                              className="p-2 bg-red-100 text-red-700 hover:bg-red-200 rounded-lg transition-colors"
                              title="Reject"
                            >
                              <XCircle className="w-4 h-4" />
                            </button>
                          </div>
                        ) : (
                          <span className="text-sm text-gray-400">Processed</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Payment Details Modal */}
      {showModal && selectedPayment && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">Payment Details</h2>
                <button
                  onClick={() => setShowModal(false)}
                  className="p-2 hover:bg-gray-100 rounded-lg"
                >
                  <XCircle className="w-5 h-5" />
                </button>
              </div>
            </div>

            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-500">Transaction ID</p>
                  <p className="font-mono font-medium">{selectedPayment.transaction_id || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Order Number</p>
                  <p className="font-medium text-primary-600">
                    #{selectedPayment.order?.order_number || selectedPayment.order_id}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Amount</p>
                  <p className="text-2xl font-bold">৳{parseFloat(selectedPayment.amount || 0).toLocaleString()}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Status</p>
                  <p>{getStatusBadge(selectedPayment.status)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Payment Method</p>
                  <p className="capitalize flex items-center gap-2">
                    {getMethodIcon(selectedPayment.payment_method)}
                    {selectedPayment.payment_method}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Date</p>
                  <p>{formatDate(selectedPayment.created_at)}</p>
                </div>
              </div>

              {selectedPayment.gateway_response && (
                <div className="mt-4 pt-4 border-t">
                  <p className="text-sm text-gray-500 mb-2">Gateway Response</p>
                  <pre className="bg-gray-50 p-3 rounded-lg text-xs overflow-x-auto">
                    {JSON.stringify(selectedPayment.gateway_response, null, 2)}
                  </pre>
                </div>
              )}
            </div>

            <div className="p-6 border-t bg-gray-50">
              <button
                onClick={() => setShowModal(false)}
                className="btn btn-secondary w-full"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}
