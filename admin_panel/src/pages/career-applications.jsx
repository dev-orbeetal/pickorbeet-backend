import { useEffect, useRef, useState } from 'react';
import {
  CheckCircle, Clock, Eye, FileText, GraduationCap, Mail, Phone,
  RefreshCw, Search, Trash2, User, X,
} from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import Pager from '@/components/ui/Pager';
import { fetchPrivateBlob } from '@/lib/privateFile';
import {
  useDeleteCareerApplicationMutation,
  useGetCareerApplicationQuery,
  useGetCareerApplicationsQuery,
  useUpdateCareerApplicationMutation,
} from '@/store/api/careerApplicationsApi';

const STATUS_CONFIG = {
  new: { label: 'New', color: 'bg-blue-100 text-blue-700' },
  reviewing: { label: 'Reviewing', color: 'bg-yellow-100 text-yellow-700' },
  shortlisted: { label: 'Shortlisted', color: 'bg-green-100 text-green-700' },
  rejected: { label: 'Rejected', color: 'bg-gray-100 text-gray-600' },
};

function formatDate(value) {
  return new Date(value).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function CareerApplicationsPage() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState(null);
  const [adminNotes, setAdminNotes] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [pictureUrl, setPictureUrl] = useState('');
  const [cvUrl, setCvUrl] = useState('');
  const opened = useRef(null);

  const { data, isLoading, refetch } = useGetCareerApplicationsQuery({
    status: statusFilter || undefined,
    search: search || undefined,
    page,
  });
  const { currentData: detail } = useGetCareerApplicationQuery(selectedId, { skip: !selectedId });
  const [updateApplication, { isLoading: updating }] = useUpdateCareerApplicationMutation();
  const [deleteApplication, { isLoading: deleting }] = useDeleteCareerApplicationMutation();

  const applications = Array.isArray(data?.results)
    ? data.results
    : (Array.isArray(data) ? data : []);
  const total = data?.count ?? applications.length;

  useEffect(() => {
    if (!detail?.id || opened.current === detail.id) return;
    opened.current = detail.id;
    refetch();
  }, [detail?.id, refetch]);

  useEffect(() => {
    if (!detail?.id) return;
    setAdminNotes(detail.admin_notes || '');
  }, [detail?.id, detail?.admin_notes]);

  useEffect(() => {
    if (!detail?.id) return undefined;
    let cancelled = false;
    const urls = [];

    async function load(path) {
      const url = await fetchPrivateBlob(path);
      if (cancelled) {
        URL.revokeObjectURL(url);
        return '';
      }
      urls.push(url);
      return url;
    }

    (async () => {
      try {
        if (detail.has_picture) {
          const url = await load(`/careers/admin/applications/${detail.id}/picture/`);
          if (url) setPictureUrl(url);
        }
        if (!cancelled && detail.has_cv) {
          const url = await load(`/careers/admin/applications/${detail.id}/cv/`);
          if (url) setCvUrl(url);
        }
      } catch {
        if (!cancelled) toast.error('Could not load the application files.');
      }
    })();

    return () => {
      cancelled = true;
      urls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [detail?.id, detail?.has_cv, detail?.has_picture]);

  function closeDrawer() {
    setSelectedId(null);
    setDeleteConfirm(false);
    setPictureUrl('');
    setCvUrl('');
    opened.current = null;
  }

  async function handleStatusUpdate(newStatus) {
    if (!detail) return;
    try {
      await updateApplication({ id: detail.id, status: newStatus }).unwrap();
      toast.success(`Status updated to ${STATUS_CONFIG[newStatus].label}`);
    } catch (error) {
      toast.error('Failed to update status');
    }
  }

  async function handleSaveNotes() {
    if (!detail) return;
    try {
      await updateApplication({ id: detail.id, admin_notes: adminNotes }).unwrap();
      toast.success('Notes saved');
    } catch (error) {
      toast.error('Failed to save notes');
    }
  }

  async function handleDelete() {
    if (!detail) return;
    try {
      await deleteApplication(detail.id).unwrap();
      toast.success('Application deleted');
      closeDrawer();
    } catch (error) {
      toast.error('Failed to delete application');
    }
  }

  return (
    <AdminLayout title="Career Applications">
      <div className="mb-6 flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-indigo-100 p-3">
            <GraduationCap className="h-6 w-6 text-indigo-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Career Applications</h1>
            <p className="text-sm text-gray-500">
              {total === 1 ? '1 student application' : `${total} student applications`}
            </p>
          </div>
        </div>
        <button type="button" onClick={refetch} className="btn btn-secondary flex items-center gap-2">
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      <div className="mb-6 rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search name, email, phone, student ID, or university"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              className="input w-full pl-10"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value);
              setPage(1);
            }}
            className="input w-full sm:w-48"
          >
            <option value="">All statuses</option>
            {Object.entries(STATUS_CONFIG).map(([value, config]) => (
              <option key={value} value={value}>{config.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-gray-100 bg-white shadow-sm">
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-indigo-600" />
          </div>
        ) : applications.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-gray-400">
            <GraduationCap className="mb-3 h-12 w-12" />
            <p className="text-lg font-medium">No applications found</p>
            <p className="text-sm">Student applications from the website will appear here</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-gray-100 bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">University</th>
                  <th className="px-4 py-3 font-medium">Department</th>
                  <th className="px-4 py-3 font-medium">Session</th>
                  <th className="px-4 py-3 font-medium">Student ID</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Submitted</th>
                  <th className="px-4 py-3 font-medium"> </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {applications.map((application) => {
                  const status = STATUS_CONFIG[application.status] || STATUS_CONFIG.new;
                  return (
                    <tr
                      key={application.id}
                      className={application.status === 'new' ? 'bg-blue-50/40' : ''}
                    >
                      <td className="px-4 py-3">
                        <p className={application.status === 'new' ? 'font-semibold text-gray-900' : 'font-medium text-gray-800'}>
                          {application.name}
                        </p>
                        <p className="text-xs text-gray-400">{application.email}</p>
                      </td>
                      <td className="px-4 py-3 text-gray-700">{application.university}</td>
                      <td className="px-4 py-3 text-gray-700">{application.department}</td>
                      <td className="px-4 py-3 text-gray-700">{application.session}</td>
                      <td className="px-4 py-3 font-mono text-xs text-gray-700">{application.student_id}</td>
                      <td className="px-4 py-3">
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${status.color}`}>
                          {status.label}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-gray-500">{formatDate(application.created_at)}</td>
                      <td className="px-4 py-3">
                        <button
                          type="button"
                          onClick={() => {
                            setDeleteConfirm(false);
                            setSelectedId(application.id);
                          }}
                          className="text-sm font-medium text-indigo-600 hover:underline"
                        >
                          Review
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <Pager page={page} count={total} onPage={setPage} />
      </div>

      {selectedId && detail ? (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={closeDrawer}>
          <div
            className="h-full w-full max-w-xl overflow-y-auto bg-white shadow-xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between border-b border-gray-100 p-6">
              <div className="flex items-center gap-3">
                {pictureUrl ? (
                  <img src={pictureUrl} alt="" className="h-14 w-14 rounded-full object-cover" />
                ) : (
                  <div className="flex h-14 w-14 items-center justify-center rounded-full bg-indigo-100">
                    <User className="h-6 w-6 text-indigo-600" />
                  </div>
                )}
                <div>
                  <h2 className="text-lg font-bold text-gray-900">{detail.name}</h2>
                  <p className="text-sm text-gray-500">{formatDate(detail.created_at)}</p>
                </div>
              </div>
              <button type="button" onClick={closeDrawer} className="rounded-lg p-2 hover:bg-gray-100" aria-label="Close">
                <X className="h-5 w-5 text-gray-500" />
              </button>
            </div>

            <div className="space-y-3 border-b border-gray-100 p-6 text-sm text-gray-600">
              <a href={`mailto:${detail.email}`} className="flex items-center gap-2 text-indigo-600 hover:underline">
                <Mail className="h-4 w-4" /> {detail.email}
              </a>
              <a href={`tel:${detail.phone}`} className="flex items-center gap-2 text-indigo-600 hover:underline">
                <Phone className="h-4 w-4" /> {detail.phone}
              </a>
              <p className="flex items-center gap-2"><GraduationCap className="h-4 w-4 text-gray-400" /> {detail.university}</p>
              <p className="flex items-center gap-2"><Clock className="h-4 w-4 text-gray-400" /> Session {detail.session}</p>
              <p>{detail.department}</p>
              <p>Student ID <span className="font-mono text-gray-900">{detail.student_id}</span></p>
            </div>

            <div className="flex flex-wrap gap-3 border-b border-gray-100 p-6">
              {pictureUrl ? (
                <a href={pictureUrl} target="_blank" rel="noopener noreferrer" className="btn btn-secondary text-sm">
                  <Eye className="mr-1.5 h-4 w-4" /> View photo
                </a>
              ) : null}
              {cvUrl ? (
                <a href={cvUrl} target="_blank" rel="noopener noreferrer" className="btn btn-secondary text-sm">
                  <FileText className="mr-1.5 h-4 w-4" /> Open CV
                </a>
              ) : null}
            </div>

            <div className="border-b border-gray-100 p-6">
              <p className="mb-3 text-xs font-medium uppercase text-gray-500">Update status</p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(STATUS_CONFIG).map(([key, config]) => {
                  const active = detail.status === key;
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => handleStatusUpdate(key)}
                      disabled={updating || active}
                      className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
                        active ? `${config.color} ring-2 ring-current ring-offset-1` : 'bg-gray-50 text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      {key === 'shortlisted' ? <CheckCircle className="mr-1 inline h-3.5 w-3.5" /> : null}
                      {config.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="border-b border-gray-100 p-6">
              <p className="mb-3 text-xs font-medium uppercase text-gray-500">Admin notes</p>
              <textarea
                value={adminNotes}
                onChange={(event) => setAdminNotes(event.target.value)}
                rows={4}
                placeholder="Notes for the hiring team"
                className="input w-full text-sm"
              />
              <div className="mt-3 flex justify-end">
                <button
                  type="button"
                  onClick={handleSaveNotes}
                  disabled={updating || adminNotes === (detail.admin_notes || '')}
                  className="btn btn-primary text-sm"
                >
                  Save notes
                </button>
              </div>
            </div>

            <div className="p-6">
              {deleteConfirm ? (
                <div className="flex flex-wrap items-center gap-3">
                  <p className="flex-1 text-sm text-red-600">Delete this application and its files?</p>
                  <button type="button" onClick={handleDelete} disabled={deleting} className="btn bg-red-600 text-sm text-white hover:bg-red-700">
                    {deleting ? 'Deleting...' : 'Yes, delete'}
                  </button>
                  <button type="button" onClick={() => setDeleteConfirm(false)} className="btn btn-secondary text-sm">
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setDeleteConfirm(true)}
                  className="flex items-center gap-1.5 text-sm text-red-500 hover:text-red-700"
                >
                  <Trash2 className="h-4 w-4" /> Delete this application
                </button>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </AdminLayout>
  );
}
