import { useState } from 'react';
import { Plus, Edit, Trash2, UserCog, Shield, Calculator, Store } from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import {
  useGetStaffListQuery,
  useCreateStaffMemberMutation,
  useUpdateStaffMemberMutation,
  useDeleteStaffMemberMutation
} from '@/store/api/staffApi';

export default function StaffPage() {
  const token = typeof window !== 'undefined' ? localStorage.getItem('admin_access_token') : null;
  const { data: staffData, isLoading: loading, error } = useGetStaffListQuery(undefined, {
    skip: !token,
  });
  const [createStaffMember] = useCreateStaffMemberMutation();
  const [updateStaffMember] = useUpdateStaffMemberMutation();
  const [deleteStaffMember] = useDeleteStaffMemberMutation();

  const staff = Array.isArray(staffData) ? staffData : [];

  const [showModal, setShowModal] = useState(false);
  const [editingStaff, setEditingStaff] = useState(null);
  const [formData, setFormData] = useState({
    email: '',
    first_name: '',
    last_name: '',
    phone: '',
    role: 'seller',
    password: '',
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingStaff) {
        const updateData = { ...formData };
        if (!updateData.password) delete updateData.password;
        await updateStaffMember({ id: editingStaff.id, ...updateData }).unwrap();
        toast.success('Staff updated');
      } else {
        await createStaffMember(formData).unwrap();
        toast.success('Staff created');
      }
      setShowModal(false);
      setEditingStaff(null);
      setFormData({ email: '', first_name: '', last_name: '', phone: '', role: 'seller', password: '' });
    } catch (error) {
      toast.error(error?.data?.email?.[0] || 'Operation failed');
    }
  };

  const handleEdit = (staffMember) => {
    setEditingStaff(staffMember);
    setFormData({
      email: staffMember.email,
      first_name: staffMember.first_name,
      last_name: staffMember.last_name,
      phone: staffMember.phone || '',
      role: staffMember.role,
      password: '',
    });
    setShowModal(true);
  };

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this staff member?')) return;
    try {
      await deleteStaffMember(id).unwrap();
      toast.success('Staff deleted');
    } catch (error) {
      toast.error('Failed to delete staff');
    }
  };

  const getRoleIcon = (role) => {
    switch (role) {
      case 'super_admin': return Shield;
      case 'accountant': return Calculator;
      case 'seller': return Store;
      default: return UserCog;
    }
  };

  const getRoleBadge = (role) => {
    switch (role) {
      case 'super_admin': return 'bg-purple-100 text-purple-800';
      case 'accountant': return 'bg-blue-100 text-blue-800';
      case 'seller': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <AdminLayout title="Staff Management">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <p className="text-gray-600">
          Manage staff accounts and their access levels
        </p>
        <button
          onClick={() => {
            setEditingStaff(null);
            setFormData({ email: '', first_name: '', last_name: '', phone: '', role: 'seller', password: '' });
            setShowModal(true);
          }}
          className="btn btn-primary"
        >
          <Plus className="w-4 h-4 mr-2" />
          Add Staff
        </button>
      </div>

      {/* Error Display */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-800 font-medium">
            {error.status === 403
              ? 'Access Denied: You need Super Admin privileges to manage staff.'
              : `Error: ${error.data?.detail || 'Failed to load staff members'}`
            }
          </p>
        </div>
      )}

      {/* Role Legend */}
      <div className="card p-4 mb-6">
        <div className="flex flex-wrap gap-6">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-purple-600" />
            <span className="text-sm">
              <strong>Super Admin:</strong> Full access to all features
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Calculator className="w-5 h-5 text-blue-600" />
            <span className="text-sm">
              <strong>Accountant:</strong> Reports, payments, orders
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Store className="w-5 h-5 text-green-600" />
            <span className="text-sm">
              <strong>Seller:</strong> POS, orders, products
            </span>
          </div>
        </div>
      </div>

      {/* Staff Grid */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {loading ? (
          [...Array(6)].map((_, i) => (
            <div key={i} className="card p-6 animate-pulse">
              <div className="h-16 bg-gray-200 rounded mb-4" />
              <div className="h-4 bg-gray-200 rounded w-3/4" />
            </div>
          ))
        ) : staff.length === 0 ? (
          <div className="col-span-full text-center py-12 text-gray-500">
            No staff members found
          </div>
        ) : (
          Array.isArray(staff) && staff.map((member) => {
            const RoleIcon = getRoleIcon(member.role);
            return (
              <div key={member.id} className="card p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-primary-100 rounded-full flex items-center justify-center">
                      <span className="text-primary-600 font-semibold text-lg">
                        {member.first_name?.charAt(0)}{member.last_name?.charAt(0)}
                      </span>
                    </div>
                    <div>
                      <h3 className="font-medium text-gray-900">{member.full_name}</h3>
                      <p className="text-sm text-gray-500">{member.email}</p>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 mb-4">
                  <RoleIcon className="w-4 h-4" />
                  <span className={`badge ${getRoleBadge(member.role)}`}>
                    {member.role.replace('_', ' ')}
                  </span>
                  <span className={`badge ${member.is_active ? 'badge-success' : 'badge-danger'}`}>
                    {member.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>

                {member.phone && (
                  <p className="text-sm text-gray-500 mb-4">{member.phone}</p>
                )}

                <div className="flex items-center gap-2 pt-4 border-t">
                  <button
                    onClick={() => handleEdit(member)}
                    className="flex-1 btn btn-secondary text-sm"
                  >
                    <Edit className="w-4 h-4 mr-1" />
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(member.id)}
                    className="btn btn-danger text-sm"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
            <div className="p-6 border-b">
              <h2 className="text-xl font-semibold text-gray-900">
                {editingStaff ? 'Edit Staff' : 'Add New Staff'}
              </h2>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">First Name</label>
                  <input
                    type="text"
                    value={formData.first_name}
                    onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                    className="input"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Last Name</label>
                  <input
                    type="text"
                    value={formData.last_name}
                    onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                    className="input"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="input"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                <input
                  type="tel"
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  className="input"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  className="input"
                >
                  <option value="seller">Seller</option>
                  <option value="accountant">Accountant</option>
                  <option value="super_admin">Super Admin</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Password {editingStaff && '(leave blank to keep current)'}
                </label>
                <input
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className="input"
                  required={!editingStaff}
                  minLength={8}
                />
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="flex-1 btn btn-secondary"
                >
                  Cancel
                </button>
                <button type="submit" className="flex-1 btn btn-primary">
                  {editingStaff ? 'Update' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}
