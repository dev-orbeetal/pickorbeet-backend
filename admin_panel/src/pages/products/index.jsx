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
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3 border-b border-gray-200">
        <div className="flex gap-1">
          {VIEWS.map((item) => (
            <Link
              key={item.id}
              href={item.href}
              shallow
              aria-current={view === item.id ? 'page' : undefined}
              className={`-mb-px border-b-2 px-3 py-2 text-base font-medium transition-colors ${
                view === item.id
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-800'
              }`}
            >
              {item.label}
            </Link>
          ))}
        </div>
        <Link href="/products/new" className="btn btn-primary mb-2 shrink-0">
          <Plus className="mr-2 h-4 w-4" />
          Add Product
        </Link>
      </div>

      {router.isReady && (view === 'all' ? <ProductTable /> : <CatalogManager />)}
    </AdminLayout>
  );
}
