import { useEffect } from 'react';
import { useRouter } from 'next/router';
import AdminLayout from '@/components/layout/AdminLayout';

export default function CustomersRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/users');
  }, [router]);

  return (
    <AdminLayout title="Users">
      <p className="text-sm text-gray-500">Opening users…</p>
    </AdminLayout>
  );
}
