import { useRouter } from 'next/router';
import { useDispatch, useSelector } from 'react-redux';
import { Bell, LogOut, User, Menu } from 'lucide-react';
import { logoutState } from '@/store/slices/authSlice';
import { useLogoutMutation } from '@/store/api/authApi';

export default function Header({ title, onMenuClick }) {
  const router = useRouter();
  const dispatch = useDispatch();
  const { user } = useSelector((state) => state.auth);
  const [logout] = useLogoutMutation();

  const handleLogout = async () => {
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
        <button className="relative p-2 text-gray-600 hover:bg-gray-100 rounded-lg">
          <Bell className="w-5 h-5" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
        </button>

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
