import Link from 'next/link';
import { useRouter } from 'next/router';
import { Plus } from 'lucide-react';
import AdminLayout from '@/components/layout/AdminLayout';
import CatalogManager from '@/components/products/CatalogManager';
import ProductTable from '@/components/products/ProductTable';

const VIEWS = [
  { id: 'catalog', label: 'By category', href: '/products' },
  { id: 'all', label: 'All products', href: '/products?view=all' },
];

export default function ProductsPage() {
  const router = useRouter();
  const view = router.query.view === 'all' ? 'all' : 'catalog';

  return (
    <AdminLayout title="Products">
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Products</h1>
          <p className="mt-1 text-sm text-gray-500">
            Organize categories and subcategories, and manage the products inside them.
          </p>
        </div>
        <Link href="/products/new" className="btn btn-primary shrink-0">
          <Plus className="mr-2 h-4 w-4" />
          Add Product
        </Link>
      </div>

      <div className="mb-5 flex gap-1 border-b border-gray-200">
        {VIEWS.map((item) => (
          <Link
            key={item.id}
            href={item.href}
            shallow
            aria-current={view === item.id ? 'page' : undefined}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
              view === item.id
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-800'
            }`}
          >
            {item.label}
          </Link>
        ))}
      </div>

      {router.isReady && (view === 'all' ? <ProductTable /> : <CatalogManager />)}
    </AdminLayout>
  );
}
