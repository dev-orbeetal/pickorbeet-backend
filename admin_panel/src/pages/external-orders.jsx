import { useEffect } from 'react';
import { useRouter } from 'next/router';
import AdminLayout from '@/components/layout/AdminLayout';

/** Legacy route — Add Order now lives under Orders. */
export default function ExternalOrdersRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/orders/new');
  }, [router]);

  return (
    <AdminLayout title="Add Order">
      <p className="text-sm text-gray-500">Redirecting to Add Order…</p>
    </AdminLayout>
  );
}
