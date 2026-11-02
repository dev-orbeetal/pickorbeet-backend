import { useEffect } from 'react';
import { useRouter } from 'next/router';
import AdminLayout from '@/components/layout/AdminLayout';

/**
 * Inventory is no longer a separate module. Stock is shown on Products;
 * purchases and sales update quantities automatically.
 */
export default function InventoryRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    const stock = typeof router.query.stock === 'string' ? router.query.stock : '';
    if (stock === 'low_stock') {
      router.replace('/low-stock');
      return;
    }
    router.replace('/products');
  }, [router]);

  return (
    <AdminLayout title="Products">
      <p className="text-sm text-gray-500">Redirecting to Products…</p>
    </AdminLayout>
  );
}
