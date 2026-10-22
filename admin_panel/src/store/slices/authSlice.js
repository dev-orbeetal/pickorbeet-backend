import { createSlice } from '@reduxjs/toolkit';
import { authApi } from '@/store/api/authApi';
import { adminHref } from '@/lib/utils';

// Load user from localStorage on init
const loadUserFromStorage = () => {
  if (typeof window === 'undefined') return null;
  try {
    const userData = localStorage.getItem('admin_user_data');
    return userData ? JSON.parse(userData) : null;
  } catch {
    return null;
  }
};

const initialState = {
  user: loadUserFromStorage(),
  isAuthenticated: typeof window !== 'undefined' && !!localStorage.getItem('admin_access_token'),
  loading: false,
  error: null,
};

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
    checkAuth: (state) => {
      const token = typeof window !== 'undefined' ? localStorage.getItem('admin_access_token') : null;
      state.isAuthenticated = !!token;
    },
    setCredentials: (state, action) => {
      state.user = action.payload;
      state.isAuthenticated = true;
      state.loading = false;
      state.error = null;
      // Persist user data to localStorage
      if (typeof window !== 'undefined') {
        localStorage.setItem('admin_user_data', JSON.stringify(action.payload));
        localStorage.setItem('admin_user_id', action.payload.id);
      }
    },
    setLoading: (state, action) => {
      state.loading = action.payload;
    },
    setError: (state, action) => {
      state.error = action.payload;
      state.loading = false;
    },
    logoutState: (state) => {
      state.user = null;
      state.isAuthenticated = false;
      state.loading = false;
      state.error = null;
      // Clear all auth data from localStorage
      if (typeof window !== 'undefined') {
        localStorage.removeItem('admin_access_token');
        localStorage.removeItem('admin_refresh_token');
        localStorage.removeItem('admin_user_id');
        localStorage.removeItem('admin_user_data');
      }
    },
  },
  extraReducers: (builder) => {
    // DO NOT auto-update user from profile query
    // This prevents the role from being changed unexpectedly
    // User data is only set via setCredentials on login
    builder
      .addMatcher(authApi.endpoints.getProfile.matchFulfilled, (state, action) => {
        const storedUserId = typeof window !== 'undefined' ? localStorage.getItem('admin_user_id') : null;
        
        // Only verify - if mismatch, force logout but don't change role
        if (storedUserId && action.payload.id !== storedUserId) {
          console.error('CRITICAL: Profile user ID mismatch! Forcing logout.');
          state.user = null;
          state.isAuthenticated = false;
          if (typeof window !== 'undefined') {
            localStorage.removeItem('admin_access_token');
            localStorage.removeItem('admin_refresh_token');
            localStorage.removeItem('admin_user_id');
            localStorage.removeItem('admin_user_data');
            window.location.href = adminHref('/login');
          }
        }
        // If no stored user (shouldn't happen), restore from profile
        else if (!state.user && action.payload) {
          state.user = action.payload;
          state.isAuthenticated = true;
          if (typeof window !== 'undefined') {
            localStorage.setItem('admin_user_data', JSON.stringify(action.payload));
            localStorage.setItem('admin_user_id', action.payload.id);
          }
        }
        // Otherwise, keep the existing user data - DO NOT OVERWRITE
      });
  },
});

export const { 
  clearError, 
  checkAuth, 
  setCredentials, 
  setLoading, 
  setError, 
  logoutState 
} = authSlice.actions;

export default authSlice.reducer;
