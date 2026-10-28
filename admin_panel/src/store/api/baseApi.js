import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import { Mutex } from 'async-mutex';
import { adminHref } from '@/lib/utils';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

const mutex = new Mutex();

const baseQuery = fetchBaseQuery({
  baseUrl: API_BASE_URL,
  prepareHeaders: (headers, { getState, endpoint }) => {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('admin_access_token');
      if (token) {
        headers.set('Authorization', `Bearer ${token}`);
      }
    }
    // Don't set Content-Type for FormData - browser will set it with boundary
    // RTK Query's fetchBaseQuery may set it; we must remove it for file uploads
    return headers;
  },
});

const baseQueryWithReauth = async (args, api, extraOptions) => {
  await mutex.waitForUnlock();
  
  let result = await baseQuery(args, api, extraOptions);

  if (result.error && result.error.status === 401) {
    if (!mutex.isLocked()) {
      const release = await mutex.acquire();
      
      try {
        const refreshToken = localStorage.getItem('admin_refresh_token');
        const storedUserId = localStorage.getItem('admin_user_id');
        
        if (refreshToken) {
          const refreshResult = await baseQuery(
            {
              url: '/auth/token/refresh/',
              method: 'POST',
              body: { refresh: refreshToken },
            },
            api,
            extraOptions
          );

          if (refreshResult.data) {
            const { access } = refreshResult.data;
            localStorage.setItem('admin_access_token', access);
            
            // Invalidate Auth cache to force fresh profile fetch
            api.dispatch(baseApi.util.invalidateTags(['Auth']));
            
            // Verify user hasn't changed by fetching profile
            const profileResult = await baseQuery(
              { url: '/auth/profile/' },
              api,
              extraOptions
            );
            
            if (profileResult.data && storedUserId && profileResult.data.id !== storedUserId) {
              // User mismatch - token belongs to different user, force logout
              console.error('User mismatch detected after token refresh');
              localStorage.removeItem('admin_access_token');
              localStorage.removeItem('admin_refresh_token');
              localStorage.removeItem('admin_user_id');
              localStorage.removeItem('admin_user_data');
              if (typeof window !== 'undefined') {
                window.location.href = adminHref('/login');
              }
              return result;
            }
            
            result = await baseQuery(args, api, extraOptions);
          } else {
            localStorage.removeItem('admin_access_token');
            localStorage.removeItem('admin_refresh_token');
            localStorage.removeItem('admin_user_id');
            localStorage.removeItem('admin_user_data');
            if (typeof window !== 'undefined') {
              window.location.href = adminHref('/login');
            }
          }
        } else {
          localStorage.removeItem('admin_access_token');
          localStorage.removeItem('admin_refresh_token');
          localStorage.removeItem('admin_user_id');
          localStorage.removeItem('admin_user_data');
          if (typeof window !== 'undefined') {
            window.location.href = adminHref('/login');
          }
        }
      } finally {
        release();
      }
    } else {
      await mutex.waitForUnlock();
      result = await baseQuery(args, api, extraOptions);
    }
  }

  return result;
};

export const baseApi = createApi({
  reducerPath: 'api',
  baseQuery: baseQueryWithReauth,
  tagTypes: [
    'Auth',
    'Dashboard',
    'Products',
    'Categories',
    'Orders',
    'Staff',
    'Reports',
    'Payments',
    'Inventory',
    'Coupons',
    'Contact',
    'Support',
    'SupportThread',
    'StoreSettings',
    'Banners',
    'Traffic',
  ],
  endpoints: () => ({}),
});

export default baseApi;
