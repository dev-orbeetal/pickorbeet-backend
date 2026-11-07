import { baseApi, OVERRIDE_EXISTING } from './baseApi';

export const authApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    login: builder.mutation({
      query: (credentials) => ({
        url: '/auth/login/',
        method: 'POST',
        body: credentials,
      }),
      invalidatesTags: ['Auth'],
    }),
    
    logout: builder.mutation({
      query: (data) => ({
        url: '/auth/logout/',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['Auth'],
    }),
    
    getProfile: builder.query({
      query: () => '/auth/profile/',
      providesTags: ['Auth'],
    }),
  }),
  overrideExisting: OVERRIDE_EXISTING,
});

export const {
  useLoginMutation,
  useLogoutMutation,
  useGetProfileQuery,
  useLazyGetProfileQuery,
} = authApi;
