export const MENU_GROUPS = [
  {
    label: 'Sell',
    items: [
      { href: '/dashboard', label: 'Dashboard', icon: 'LayoutDashboard', roles: ['seller', 'accountant', 'super_admin'] },
      { href: '/orders', label: 'Orders', icon: 'ShoppingCart', roles: ['seller', 'accountant', 'super_admin'] },
      { href: '/pos', label: 'POS / In-Shop', icon: 'ShoppingBag', roles: ['seller', 'super_admin'] },
    ],
  },
  {
    label: 'Catalog',
    items: [
      { href: '/products', label: 'Products', icon: 'Package', roles: ['seller', 'accountant', 'super_admin'] },
      { href: '/categories', label: 'Categories', icon: 'Tag', roles: ['seller', 'super_admin'] },
      { href: '/coupons', label: 'Coupons', icon: 'Ticket', roles: ['seller', 'super_admin'] },
      { href: '/inventory', label: 'Inventory', icon: 'Warehouse', roles: ['seller', 'accountant', 'super_admin'] },
    ],
  },
  {
    label: 'Money',
    items: [
      { href: '/reports', label: 'Reports', icon: 'BarChart3', roles: ['accountant', 'super_admin'] },
      { href: '/payments', label: 'Payments', icon: 'Receipt', roles: ['accountant', 'super_admin'] },
      { href: '/finance', label: 'Finance', icon: 'Wallet', roles: ['accountant', 'super_admin'] },
    ],
  },
  {
    label: 'People',
    items: [
      { href: '/customers', label: 'Customers', icon: 'Users', roles: ['seller', 'super_admin'] },
      { href: '/contact', label: 'Contact Messages', icon: 'MessageSquare', roles: ['seller', 'super_admin'] },
      { href: '/support', label: 'Support', icon: 'Headphones', roles: ['seller', 'super_admin'] },
      { href: '/staff', label: 'Staff', icon: 'UserCog', roles: ['super_admin'] },
    ],
  },
  {
    label: 'Store',
    items: [
      { href: '/settings', label: 'Settings', icon: 'Settings', roles: ['super_admin'] },
    ],
  },
];

const PAGE_ACCESS = MENU_GROUPS.flatMap((group) => group.items).concat([
  { href: '/low-stock', roles: ['seller', 'accountant', 'super_admin'] },
]);

export function rolesForPath(pathname) {
  const path = pathname || '/';
  const match = PAGE_ACCESS
    .filter((item) => path === item.href || path.startsWith(`${item.href}/`))
    .sort((a, b) => b.href.length - a.href.length)[0];
  return match ? match.roles : null;
}
