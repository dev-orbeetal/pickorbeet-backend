import { useRouter } from 'next/router';
import Link from 'next/link';
import { useSelector } from 'react-redux';
import {
  LayoutDashboard, Package, ShoppingCart, Users, BarChart3, Activity,
  Settings, Tag, Receipt, UserCog, Truck, Bell,
  Warehouse, Ticket, MessageSquare, Headphones, Wallet, ClipboardList, LayoutTemplate,
} from 'lucide-react';
import { MENU_GROUPS } from '@/lib/access';

const ICONS = {
  LayoutDashboard, Package, ShoppingCart, Users, BarChart3, Activity,
  Settings, Tag, Receipt, UserCog, Truck, Bell,
  Warehouse, Ticket, MessageSquare, Headphones, Wallet, ClipboardList, LayoutTemplate,
};

export default function Sidebar() {
  const router = useRouter();
  const { user } = useSelector((state) => state.auth);
  const userRole = user?.role || 'seller';

  const groups = MENU_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => item.roles.includes(userRole)),
  })).filter((group) => group.items.length > 0);

  return (
    <aside className="fixed left-0 top-0 h-screen w-64 bg-sidebar-bg text-white flex flex-col z-50">
      <div className="p-6 border-b border-white/10">
        <Link href="/dashboard" className="text-2xl font-bold text-primary-500">
          PickOrbeet
        </Link>
        <p className="text-xs text-gray-400 mt-1">Admin Panel</p>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 py-3">
        {groups.map((group, index) => (
          <div key={group.label} className={index === 0 ? 'mb-3' : 'mb-3 mt-4'}>
            <p className="px-4 pb-2 text-[11px] font-bold uppercase tracking-[0.14em] text-white/45">
              {group.label}
            </p>
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const Icon = ICONS[item.icon];
                const isActive = router.pathname === item.href || router.pathname.startsWith(`${item.href}/`);
                return (
                  <li key={item.href}>
                    <Link href={item.href} className={`sidebar-link !mx-0 ${isActive ? 'active' : ''}`}>
                      {Icon && <Icon className="w-5 h-5 mr-3" />}
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

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
