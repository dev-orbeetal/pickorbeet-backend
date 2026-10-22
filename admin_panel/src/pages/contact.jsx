import { useState } from 'react';
import {
  Search, Mail, Phone, User, Clock, MessageSquare,
  Eye, Trash2, Filter, RefreshCw, X, Send,
  CheckCircle, Archive, AlertCircle, MailOpen
} from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import {
  useGetContactMessagesQuery,
  useUpdateContactMessageMutation,
  useDeleteContactMessageMutation,
} from '@/store/api/contactApi';

const STATUS_CONFIG = {
  new: { label: 'New', color: 'bg-blue-100 text-blue-700', icon: Mail },
  read: { label: 'Read', color: 'bg-yellow-100 text-yellow-700', icon: MailOpen },
  replied: { label: 'Replied', color: 'bg-green-100 text-green-700', icon: CheckCircle },
  archived: { label: 'Archived', color: 'bg-gray-100 text-gray-600', icon: Archive },
};

export default function ContactPage() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedMessage, setSelectedMessage] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [adminNotes, setAdminNotes] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  const { data: messagesData, isLoading: loading, refetch } = useGetContactMessagesQuery({
    status: statusFilter || undefined,
    search: search || undefined,
  });
  const [updateMessage, { isLoading: updating }] = useUpdateContactMessageMutation();
  const [deleteMessage, { isLoading: deleting }] = useDeleteContactMessageMutation();

  const messages = Array.isArray(messagesData?.results || messagesData)
    ? (messagesData?.results || messagesData)
    : [];

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  };

  const timeAgo = (dateString) => {
    const now = new Date();
    const date = new Date(dateString);
    const diff = Math.floor((now - date) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
    return formatDate(dateString);
  };

  const openMessage = (msg) => {
    setSelectedMessage(msg);
    setAdminNotes(msg.admin_notes || '');
    setShowModal(true);
  };

  const handleStatusUpdate = async (id, newStatus) => {
    try {
      await updateMessage({ id, status: newStatus }).unwrap();
      toast.success(`Status updated to ${STATUS_CONFIG[newStatus].label}`);
      if (selectedMessage?.id === id) {
        setSelectedMessage({ ...selectedMessage, status: newStatus });
      }
    } catch (error) {
      toast.error('Failed to update status');
    }
  };

  const handleSaveNotes = async () => {
    if (!selectedMessage) return;
    try {
      await updateMessage({ id: selectedMessage.id, admin_notes: adminNotes }).unwrap();
      toast.success('Notes saved');
      setSelectedMessage({ ...selectedMessage, admin_notes: adminNotes });
    } catch (error) {
      toast.error('Failed to save notes');
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteMessage(id).unwrap();
      toast.success('Message deleted');
      setDeleteConfirm(null);
      if (selectedMessage?.id === id) {
        setShowModal(false);
        setSelectedMessage(null);
      }
    } catch (error) {
      toast.error('Failed to delete message');
    }
  };

  // Stats
  const allMessages = messages;
  const newCount = allMessages.filter(m => m.status === 'new').length;
  const readCount = allMessages.filter(m => m.status === 'read').length;
  const repliedCount = allMessages.filter(m => m.status === 'replied').length;

  return (
    <AdminLayout title="Contact Messages">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-indigo-100 rounded-xl">
            <MessageSquare className="w-6 h-6 text-indigo-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Contact Messages</h1>
            <p className="text-sm text-gray-500">{messages.length} total messages</p>
          </div>
        </div>
        <button onClick={refetch} className="btn btn-secondary flex items-center gap-2">
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase">New</p>
              <p className="text-2xl font-bold text-blue-600 mt-1">{newCount}</p>
            </div>
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <Mail className="w-5 h-5 text-blue-600" />
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase">Read</p>
              <p className="text-2xl font-bold text-yellow-600 mt-1">{readCount}</p>
            </div>
            <div className="w-10 h-10 bg-yellow-100 rounded-lg flex items-center justify-center">
              <MailOpen className="w-5 h-5 text-yellow-600" />
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase">Replied</p>
              <p className="text-2xl font-bold text-green-600 mt-1">{repliedCount}</p>
            </div>
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <CheckCircle className="w-5 h-5 text-green-600" />
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase">Total</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{messages.length}</p>
            </div>
            <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
              <MessageSquare className="w-5 h-5 text-gray-600" />
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 mb-6">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search by name, email, subject..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input pl-10 w-full"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input w-full sm:w-48"
          >
            <option value="">All Status</option>
            <option value="new">New</option>
            <option value="read">Read</option>
            <option value="replied">Replied</option>
            <option value="archived">Archived</option>
          </select>
        </div>
      </div>

      {/* Message List */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
          </div>
        ) : messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-gray-400">
            <MessageSquare className="w-12 h-12 mb-3" />
            <p className="text-lg font-medium">No messages found</p>
            <p className="text-sm">Contact messages from customers will appear here</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {messages.map((msg) => {
              const statusCfg = STATUS_CONFIG[msg.status] || STATUS_CONFIG.new;
              const StatusIcon = statusCfg.icon;
              return (
                <div
                  key={msg.id}
                  onClick={() => openMessage(msg)}
                  className={`flex items-start gap-4 p-4 hover:bg-gray-50 cursor-pointer transition-colors ${
                    msg.status === 'new' ? 'bg-blue-50/40' : ''
                  }`}
                >
                  {/* Avatar */}
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                    msg.status === 'new' ? 'bg-indigo-100' : 'bg-gray-100'
                  }`}>
                    <User className={`w-5 h-5 ${msg.status === 'new' ? 'text-indigo-600' : 'text-gray-500'}`} />
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <p className={`text-sm truncate ${msg.status === 'new' ? 'font-bold text-gray-900' : 'font-medium text-gray-700'}`}>
                        {msg.name}
                      </p>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusCfg.color}`}>
                        {statusCfg.label}
                      </span>
                    </div>
                    <p className={`text-sm truncate ${msg.status === 'new' ? 'font-semibold text-gray-800' : 'text-gray-600'}`}>
                      {msg.subject}
                    </p>
                    <p className="text-xs text-gray-400 truncate mt-0.5">
                      {msg.message}
                    </p>
                  </div>

                  {/* Meta */}
                  <div className="flex flex-col items-end gap-1 flex-shrink-0">
                    <span className="text-xs text-gray-400">{timeAgo(msg.created_at)}</span>
                    <span className="text-xs text-gray-400">{msg.email}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Detail Modal */}
      {showModal && selectedMessage && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowModal(false)}>
          <div
            className="bg-white rounded-2xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-100">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 bg-indigo-100 rounded-full flex items-center justify-center">
                  <User className="w-6 h-6 text-indigo-600" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-gray-900">{selectedMessage.name}</h2>
                  <p className="text-sm text-gray-500">{formatDate(selectedMessage.created_at)}</p>
                </div>
              </div>
              <button onClick={() => setShowModal(false)} className="p-2 hover:bg-gray-100 rounded-lg">
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            {/* Contact Info */}
            <div className="p-6 border-b border-gray-100">
              <div className="flex flex-wrap gap-4">
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <Mail className="w-4 h-4 text-gray-400" />
                  <a href={`mailto:${selectedMessage.email}`} className="text-indigo-600 hover:underline">
                    {selectedMessage.email}
                  </a>
                </div>
                {selectedMessage.phone && (
                  <div className="flex items-center gap-2 text-sm text-gray-600">
                    <Phone className="w-4 h-4 text-gray-400" />
                    <a href={`tel:${selectedMessage.phone}`} className="text-indigo-600 hover:underline">
                      {selectedMessage.phone}
                    </a>
                  </div>
                )}
              </div>
            </div>

            {/* Subject & Message */}
            <div className="p-6 border-b border-gray-100">
              <h3 className="text-base font-semibold text-gray-900 mb-3">{selectedMessage.subject}</h3>
              <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{selectedMessage.message}</p>
            </div>

            {/* Status Actions */}
            <div className="p-6 border-b border-gray-100">
              <p className="text-xs font-medium text-gray-500 uppercase mb-3">Update Status</p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(STATUS_CONFIG).map(([key, cfg]) => {
                  const Icon = cfg.icon;
                  const isActive = selectedMessage.status === key;
                  return (
                    <button
                      key={key}
                      onClick={() => handleStatusUpdate(selectedMessage.id, key)}
                      disabled={updating || isActive}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                        isActive
                          ? `${cfg.color} ring-2 ring-offset-1 ring-current`
                          : 'bg-gray-50 text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <Icon className="w-3.5 h-3.5" />
                      {cfg.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Admin Notes */}
            <div className="p-6 border-b border-gray-100">
              <p className="text-xs font-medium text-gray-500 uppercase mb-3">Admin Notes</p>
              <textarea
                value={adminNotes}
                onChange={(e) => setAdminNotes(e.target.value)}
                rows={3}
                placeholder="Add internal notes about this message..."
                className="input w-full text-sm"
              />
              <div className="flex justify-end mt-3">
                <button
                  onClick={handleSaveNotes}
                  disabled={updating || adminNotes === (selectedMessage.admin_notes || '')}
                  className="btn btn-primary text-sm flex items-center gap-1.5"
                >
                  <Send className="w-3.5 h-3.5" />
                  Save Notes
                </button>
              </div>
            </div>

            {/* Delete */}
            <div className="p-6">
              {deleteConfirm === selectedMessage.id ? (
                <div className="flex items-center gap-3">
                  <p className="text-sm text-red-600 flex-1">Are you sure you want to delete this message?</p>
                  <button
                    onClick={() => handleDelete(selectedMessage.id)}
                    disabled={deleting}
                    className="btn bg-red-600 text-white hover:bg-red-700 text-sm"
                  >
                    {deleting ? 'Deleting...' : 'Yes, Delete'}
                  </button>
                  <button
                    onClick={() => setDeleteConfirm(null)}
                    className="btn btn-secondary text-sm"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setDeleteConfirm(selectedMessage.id)}
                  className="flex items-center gap-1.5 text-sm text-red-500 hover:text-red-700 transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                  Delete this message
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}
