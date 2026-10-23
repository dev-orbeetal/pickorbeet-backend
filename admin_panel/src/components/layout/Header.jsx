import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/router';
import { useDispatch, useSelector } from 'react-redux';
import { Bell, LogOut, Menu } from 'lucide-react';
import { logoutState } from '@/store/slices/authSlice';
import { useLogoutMutation } from '@/store/api/authApi';
import {
  getNotificationState,
  markNotificationRead,
  startNotificationSocket,
  stopNotificationSocket,
  subscribeNotifications,
} from '@/lib/notifications';

export default function Header({ title, onMenuClick }) {
  const router = useRouter();
  const dispatch = useDispatch();
  const { user } = useSelector((state) => state.auth);
  const [logout] = useLogoutMutation();
  const [open, setOpen] = useState(false);
  const [inbox, setInbox] = useState(getNotificationState);
  const root = useRef(null);

  useEffect(() => {
    startNotificationSocket();
    return () => stopNotificationSocket();
  }, []);

  useEffect(() => subscribeNotifications(() => setInbox(getNotificationState())), []);

  useEffect(() => {
    const close = (event) => {
      if (root.current && !root.current.contains(event.target)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const handleLogout = async () => {
    stopNotificationSocket();
    try {
      const refresh = localStorage.getItem('admin_refresh_token');
      await logout({ refresh }).unwrap();
    } catch (error) {
      // Ignore errors on logout
    } finally {
      localStorage.removeItem('admin_access_token');
      localStorage.removeItem('admin_refresh_token');
      localStorage.removeItem('admin_user_id');
      localStorage.removeItem('admin_user_data');
      dispatch(logoutState());
      router.push('/login');
    }
  };

  const recent = inbox.items.slice(0, 8);

  return (
    <header className="h-16 bg-white border-b border-[#E4E9F2] flex items-center justify-between px-6">
      <div className="flex items-center">
        <button
          onClick={onMenuClick}
          className="lg:hidden p-2 text-gray-600 hover:bg-gray-100 rounded-lg mr-4"
        >
          <Menu className="w-5 h-5" />
        </button>
        <h1 className="text-xl font-semibold text-gray-900">{title}</h1>
      </div>

      <div className="flex items-center space-x-4">
        <div className="relative" ref={root}>
          <button
            type="button"
            className="relative p-2 text-gray-600 hover:bg-gray-100 rounded-lg"
            aria-label={inbox.unreadCount ? `Notifications, ${inbox.unreadCount} unread` : 'Notifications'}
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
          >
            <Bell className="w-5 h-5" />
            {inbox.unreadCount > 0 && (
              <span className="absolute top-1 right-1 min-w-[8px] h-2 px-1 bg-red-500 rounded-full" />
            )}
          </button>
          {open && (
            <div className="absolute right-0 top-full z-50 mt-2 w-80 overflow-hidden rounded-xl border border-[#E4E9F2] bg-white shadow-lg">
              <p className="border-b border-[#E4E9F2] px-4 py-2.5 text-sm font-semibold text-gray-900">Notifications</p>
              {recent.length === 0 ? (
                <p className="px-4 py-6 text-sm text-gray-500">You&apos;re all caught up.</p>
              ) : recent.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="block w-full border-b border-[#F3F5F8] px-4 py-3 text-left last:border-b-0 hover:bg-gray-50"
                  onClick={() => {
                    markNotificationRead(item.id);
                    setOpen(false);
                    if (item.orderId) router.push(`/orders/${item.orderId}`);
                  }}
                >
                  <p className={`text-sm ${item.unread ? 'font-semibold text-gray-900' : 'text-gray-700'}`}>{item.title}</p>
                  <p className="mt-0.5 line-clamp-2 text-xs text-gray-500">{item.body}</p>
                  <p className="mt-1 text-[11px] text-gray-400">{item.time}</p>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center space-x-3 pl-4 border-l">
          <div className="text-right hidden sm:block">
            <p className="text-sm font-medium text-gray-900">{user?.full_name}</p>
            <p className="text-xs text-gray-500 capitalize">{user?.role?.replace('_', ' ')}</p>
          </div>

          <button
            onClick={handleLogout}
            className="p-2 text-gray-600 hover:bg-red-50 hover:text-red-600 rounded-lg"
            title="Logout"
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </div>
    </header>
  );
}
