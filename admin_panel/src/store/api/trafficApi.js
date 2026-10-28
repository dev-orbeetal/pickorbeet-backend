import { baseApi } from './baseApi';

export const trafficApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getTrafficOverview: builder.query({
      query: ({ from, to } = {}) => ({
        url: '/analytics/overview/',
        params: { from, to },
      }),
      providesTags: ['Traffic'],
    }),
    getTrafficBreakdown: builder.query({
      query: ({ from, to, dimension }) => ({
        url: '/analytics/breakdown/',
        params: { from, to, dimension },
      }),
      providesTags: ['Traffic'],
    }),
    getTrafficCustomers: builder.query({
      query: ({ from, to, q } = {}) => ({
        url: '/analytics/customers/',
        params: { from, to, q: q || undefined },
      }),
      providesTags: ['Traffic'],
    }),
    getTrafficCustomer: builder.query({
      query: (userId) => `/analytics/customers/${userId}/`,
      providesTags: ['Traffic'],
    }),
    getTrafficLive: builder.query({
      query: () => '/analytics/live/',
      providesTags: ['Traffic'],
    }),
    getTrafficFunnel: builder.query({
      query: ({ from, to } = {}) => ({
        url: '/analytics/funnel/',
        params: { from, to },
      }),
      providesTags: ['Traffic'],
    }),
  }),
  overrideExisting: false,
});

export const {
  useGetTrafficOverviewQuery,
  useGetTrafficBreakdownQuery,
  useGetTrafficCustomersQuery,
  useGetTrafficCustomerQuery,
  useGetTrafficLiveQuery,
  useGetTrafficFunnelQuery,
} = trafficApi;
