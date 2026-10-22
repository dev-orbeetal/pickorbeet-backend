import { useState } from 'react';
import {
  Search, Users, Eye, Mail, Phone, MapPin,
  ShoppingBag, Calendar, RefreshCw, X, User
} from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import { useGetCustomersQuery, useLazyGetCustomerOrdersQuery } from '@/store/api/customersApi';

export default function CustomersPage() {
  const { data: customersData, isLoading: loading } = useGetCustomersQuery();
  const [getCustomerOrders, { isFetching: loadingOrders }] = useLazyGetCustomerOrdersQuery();

  const customers = Array.isArray(customersData?.results || customersData)
    ? (customersData?.results || customersData)
    : [];

  const [search, setSearch] = useState('');
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [customerOrders, setCustomerOrders] = useState([]);

  const viewCustomer = async (customer) => {
    setSelectedCustomer(customer);
    setShowModal(true);
    try {
      const result = await getCustomerOrders(customer.id).unwrap();
      const ordersData = result?.results || result;
      setCustomerOrders(Array.isArray(ordersData) ? ordersData : []);
    } catch (error) {
      console.error('Failed to fetch customer orders:', error);
      setCustomerOrders([]);
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const filteredCustomers = customers.filter(customer => {
    if (!search) return true;
    const searchLower = search.toLowerCase();
    return (
      customer.full_name?.toLowerCase().includes(searchLower) ||
      customer.email?.toLowerCase().includes(searchLower) ||
      customer.phone?.includes(search)
    );
  });

  // Calculate stats
  const totalCustomers = customers.length;
  const activeCustomers = customers.filter(c => c.is_active).length;
  const newThisMonth = customers.filter(c => {
    const joinDate = new Date(c.date_joined || c.created_at);
    const now = new Date();
    return joinDate.getMonth() === now.getMonth() && joinDate.getFullYear() === now.getFullYear();
  }).length;

  return (
    <AdminLayout title="Customers">
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="stat-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Customers</p>
              <p className="text-2xl font-bold text-gray-900">{totalCustomers}</p>
            </div>
            <div className="p-3 bg-blue-100 rounded-xl">
              <Users className="w-6 h-6 text-blue-600" />
            </div>
          </div>
        </div>

        <div className="stat-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Active Customers</p>
              <p className="text-2xl font-bold text-green-600">{activeCustomers}</p>
            </div>
            <div className="p-3 bg-green-100 rounded-xl">
              <User className="w-6 h-6 text-green-600" />
            </div>
          </div>
        </div>

        <div className="stat-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">New This Month</p>
              <p className="text-2xl font-bold text-purple-600">{newThisMonth}</p>
            </div>
            <div className="p-3 bg-purple-100 rounded-xl">
              <Calendar className="w-6 h-6 text-purple-600" />
            </div>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="card mb-6">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search by name, email or phone..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="input pl-10"
              />
            </div>
          </div>
          <button
            onClick={() => {
              setLoading(true);
              fetchCustomers();
            }}
            className="btn btn-secondary"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Customers Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left table-header">Customer</th>
                <th className="px-4 py-3 text-left table-header">Contact</th>
                <th className="px-4 py-3 text-left table-header">Orders</th>
                <th className="px-4 py-3 text-left table-header">Total Spent</th>
                <th className="px-4 py-3 text-left table-header">Joined</th>
                <th className="px-4 py-3 text-left table-header">Status</th>
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
              ) : filteredCustomers.length === 0 ? (
                <tr>
                  <td colSpan="7" className="px-4 py-12 text-center text-gray-500">
                    <Users className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                    <p>No customers found</p>
                  </td>
                </tr>
              ) : (
                filteredCustomers.map((customer) => (
                  <tr key={customer.id} className="hover:bg-gray-50">
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-primary-100 rounded-full flex items-center justify-center">
                          <span className="text-primary-600 font-semibold">
                            {customer.first_name?.charAt(0)}{customer.last_name?.charAt(0)}
                          </span>
                        </div>
                        <div>
                          <p className="font-medium text-gray-900">{customer.full_name}</p>
                          <p className="text-sm text-gray-500">{customer.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex flex-col gap-1">
                        {customer.phone && (
                          <span className="text-sm flex items-center gap-1">
                            <Phone className="w-3 h-3 text-gray-400" />
                            {customer.phone}
                          </span>
                        )}
                        {customer.address && (
                          <span className="text-sm text-gray-500 flex items-center gap-1">
                            <MapPin className="w-3 h-3 text-gray-400" />
                            {customer.city || 'N/A'}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <span className="flex items-center gap-1">
                        <ShoppingBag className="w-4 h-4 text-gray-400" />
                        {customer.order_count || 0}
                      </span>
                    </td>
                    <td className="px-4 py-4 font-semibold">
                      ৳{parseFloat(customer.total_spent || 0).toLocaleString()}
                    </td>
                    <td className="px-4 py-4 text-sm text-gray-500">
                      {formatDate(customer.date_joined || customer.created_at)}
                    </td>
                    <td className="px-4 py-4">
                      <span className={`badge ${customer.is_active ? 'badge-success' : 'badge-danger'}`}>
                        {customer.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      <button
                        onClick={() => viewCustomer(customer)}
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

      {/* Customer Details Modal */}
      {showModal && selectedCustomer && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b sticky top-0 bg-white">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">Customer Details</h2>
                <button
                  onClick={() => setShowModal(false)}
                  className="p-2 hover:bg-gray-100 rounded-lg"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            <div className="p-6">
              {/* Customer Info */}
              <div className="flex items-center gap-4 mb-6">
                <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center">
                  <span className="text-primary-600 font-bold text-xl">
                    {selectedCustomer.first_name?.charAt(0)}{selectedCustomer.last_name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <h3 className="text-xl font-semibold">{selectedCustomer.full_name}</h3>
                  <p className="text-gray-500">Customer since {formatDate(selectedCustomer.date_joined || selectedCustomer.created_at)}</p>
                </div>
              </div>

              {/* Contact Info */}
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                  <Mail className="w-5 h-5 text-gray-400" />
                  <div>
                    <p className="text-xs text-gray-500">Email</p>
                    <p className="font-medium">{selectedCustomer.email}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                  <Phone className="w-5 h-5 text-gray-400" />
                  <div>
                    <p className="text-xs text-gray-500">Phone</p>
                    <p className="font-medium">{selectedCustomer.phone || 'N/A'}</p>
                  </div>
                </div>
              </div>

              {/* Address */}
              {selectedCustomer.address && (
                <div className="mb-6 p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-start gap-3">
                    <MapPin className="w-5 h-5 text-gray-400 mt-0.5" />
                    <div>
                      <p className="text-xs text-gray-500">Address</p>
                      <p className="font-medium">{selectedCustomer.address}</p>
                      <p className="text-sm text-gray-500">
                        {selectedCustomer.city}{selectedCustomer.postal_code ? `, ${selectedCustomer.postal_code}` : ''}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Stats */}
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="text-center p-4 bg-blue-50 rounded-lg">
                  <p className="text-3xl font-bold text-blue-600">{selectedCustomer.order_count || 0}</p>
                  <p className="text-sm text-blue-700">Total Orders</p>
                </div>
                <div className="text-center p-4 bg-green-50 rounded-lg">
                  <p className="text-3xl font-bold text-green-600">৳{parseFloat(selectedCustomer.total_spent || 0).toLocaleString()}</p>
                  <p className="text-sm text-green-700">Total Spent</p>
                </div>
              </div>

              {/* Recent Orders */}
              <div>
                <h4 className="font-semibold mb-3">Recent Orders</h4>
                {loadingOrders ? (
                  <div className="text-center py-4">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto text-gray-400" />
                  </div>
                ) : customerOrders.length === 0 ? (
                  <div className="text-center py-4 text-gray-500">
                    <ShoppingBag className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                    <p>No orders yet</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {customerOrders.slice(0, 5).map((order) => (
                      <div key={order.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                        <div>
                          <p className="font-medium text-primary-600">#{order.order_number}</p>
                          <p className="text-sm text-gray-500">{formatDate(order.created_at)}</p>
                        </div>
                        <div className="text-right">
                          <p className="font-semibold">৳{parseFloat(order.total_amount || 0).toLocaleString()}</p>
                          <span className={`badge ${order.order_status === 'delivered' ? 'badge-success' :
                              order.order_status === 'cancelled' ? 'badge-danger' :
                                'badge-warning'
                            }`}>
                            {order.order_status}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
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
