import { useEffect } from 'react';
import { useRouter } from 'next/router';

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    let role = '';
    try {
      role = JSON.parse(localStorage.getItem('admin_user_data') || '{}')?.role || '';
    } catch {
      role = '';
    }
    router.replace(role === 'finance_manager' ? '/finance' : '/dashboard');
  }, [router]);

  return null;
}
