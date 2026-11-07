import { baseApi, OVERRIDE_EXISTING } from './baseApi';

export const dashboardApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getDashboardStats: builder.query({
      query: () => '/reports/dashboard/',
      providesTags: ['Dashboard'],
    }),
  }),
  overrideExisting: OVERRIDE_EXISTING,
});

export const { useGetDashboardStatsQuery } = dashboardApi;
