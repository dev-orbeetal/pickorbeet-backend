import { useRouter } from 'next/router';
import Link from 'next/link';
import { useSelector } from 'react-redux';
import {
  LayoutDashboard, Package, ShoppingCart, Users, BarChart3,
  Settings, Tag, ShoppingBag, AlertTriangle, Receipt, UserCog, LogOut,
  Warehouse, Ticket, MessageSquare, Barcode
} from 'lucide-react';

const menuItems = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, roles: ['seller', 'accountant', 'super_admin'] },
  { href: '/orders', label: 'Orders', icon: ShoppingCart, roles: ['seller', 'accountant', 'super_admin'] },
  { href: '/pos', label: 'POS / In-Shop', icon: ShoppingBag, roles: ['seller', 'super_admin'] },
  { href: '/products', label: 'Products', icon: Package, roles: ['seller', 'accountant', 'super_admin'] },
  { href: '/categories', label: 'Categories', icon: Tag, roles: ['seller', 'super_admin'] },
  { href: '/coupons', label: 'Coupons', icon: Ticket, roles: ['seller', 'super_admin'] },
  { href: '/inventory', label: 'Inventory', icon: Warehouse, roles: ['seller', 'accountant', 'super_admin'] },
  { href: '/barcode-labels', label: 'Barcode Labels', icon: Barcode, roles: ['seller', 'super_admin'] },
  { href: '/low-stock', label: 'Low Stock', icon: AlertTriangle, roles: ['seller', 'accountant', 'super_admin'] },
  { href: '/reports', label: 'Reports', icon: BarChart3, roles: ['accountant', 'super_admin'] },
  { href: '/payments', label: 'Payments', icon: Receipt, roles: ['accountant', 'super_admin'] },
  { href: '/staff', label: 'Staff Management', icon: UserCog, roles: ['super_admin'] },
  { href: '/customers', label: 'Customers', icon: Users, roles: ['seller', 'super_admin'] },
  { href: '/contact', label: 'Contact Messages', icon: MessageSquare, roles: ['seller', 'super_admin'] },
  { href: '/settings', label: 'Settings', icon: Settings, roles: ['super_admin'] },
];

export default function Sidebar() {
  const router = useRouter();
  const { user } = useSelector((state) => state.auth);
  const userRole = user?.role || 'seller';

  const filteredMenu = menuItems.filter(item => item.roles.includes(userRole));

  return (
    <aside className="fixed left-0 top-0 h-screen w-64 bg-sidebar-bg text-white flex flex-col z-50">
      {/* Logo */}
      <div className="p-6 border-b border-white/10">
        <Link href="/dashboard" className="text-2xl font-bold text-primary-400">
          PickOrbeet
        </Link>
        <p className="text-xs text-gray-400 mt-1">Admin Panel</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 overflow-y-auto">
        <ul className="space-y-1">
          {filteredMenu.map((item) => {
            const isActive = router.pathname === item.href || router.pathname.startsWith(item.href + '/');
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`sidebar-link ${isActive ? 'active' : ''}`}
                >
                  <item.icon className="w-5 h-5 mr-3" />
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* User Info */}
      <div className="p-4 border-t border-gray-700">
        <div className="flex items-center">
          <div className="w-10 h-10 bg-primary-600 rounded-full flex items-center justify-center">
            <span className="text-white font-semibold">
              {user?.first_name?.charAt(0) || 'A'}
            </span>
          </div>
          <div className="ml-3 flex-1">
            <p className="text-sm font-medium">{user?.full_name || 'Admin'}</p>
            <p className="text-xs text-gray-400 capitalize">{userRole.replace('_', ' ')}</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
