import { useEffect } from 'react';
import { useRouter } from 'next/router';
import AdminLayout from '@/components/layout/AdminLayout';

/**
 * Categories are managed on Products now, beside the products they hold.
 */
export default function CategoriesRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/products');
  }, [router]);

  return (
    <AdminLayout title="Products">
      <p className="text-sm text-gray-500">Redirecting to Products…</p>
    </AdminLayout>
  );
}
