import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { useDispatch, useSelector } from 'react-redux';
import Head from 'next/head';
import Sidebar from './Sidebar';
import Header from './Header';
import Link from 'next/link';
import { checkAuth } from '@/store/slices/authSlice';
import { useGetProfileQuery } from '@/store/api/authApi';
import { rolesForPath } from '@/lib/access';

export default function AdminLayout({ children, title = 'Admin Panel' }) {
  const router = useRouter();
  const dispatch = useDispatch();
  const { isAuthenticated, user } = useSelector((state) => state.auth);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  const token = typeof window !== 'undefined' ? localStorage.getItem('admin_access_token') : null;
  const storedUser = typeof window !== 'undefined' ? localStorage.getItem('admin_user_data') : null;

  // Profile query only for verification, NOT for updating user state
  const { isLoading: loading } = useGetProfileQuery(undefined, {
    skip: !token || !storedUser,
  });

  useEffect(() => {
    setMounted(true);
    dispatch(checkAuth());
  }, [dispatch]);

  useEffect(() => {
    if (mounted && !token) {
      router.push('/login');
    }
  }, [mounted, token, router]);

  // Wait for client-side hydration
  if (!mounted) {
    return null;
  }

  if (!isAuthenticated && !loading && !storedUser) {
    router.push('/login');
    return null;
  }

  const allowed = rolesForPath(router.pathname);
  const denied = user?.role && allowed && !allowed.includes(user.role);

  return (
    <>
      <Head>
        <title>{title} - PickOrbeet Admin</title>
      </Head>

      <div className="min-h-screen bg-[#F5F7FC]">
        {/* Sidebar */}
        <div className={`lg:block ${sidebarOpen ? 'block' : 'hidden'}`}>
          <Sidebar />
        </div>

        {/* Overlay for mobile */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 bg-black/50 z-40 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Main Content */}
        <div className="min-w-0 lg:ml-64">
          <Header title={title} onMenuClick={() => setSidebarOpen(!sidebarOpen)} />
          <main className="min-w-0 overflow-x-hidden p-6">
            {denied ? (
              <div className="card max-w-lg p-8">
                <h2 className="text-lg font-semibold text-gray-900">You don&apos;t have access</h2>
                <p className="mt-2 text-sm text-gray-500">
                  This section is not available for your role.
                </p>
                <Link href="/dashboard" className="btn btn-primary mt-4 inline-flex">
                  Back to dashboard
                </Link>
              </div>
            ) : children}
          </main>
        </div>
      </div>
    </>
  );
}
