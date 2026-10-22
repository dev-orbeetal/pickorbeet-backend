import { baseApi } from './baseApi';

export const reportsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getSalesReport: builder.mutation({
      query: (data) => ({
        url: '/reports/sales/',
        method: 'POST',
        body: data,
      }),
    }),

    getStockReport: builder.query({
      query: () => '/reports/stock/',
      providesTags: ['Reports', 'Inventory'],
    }),

    getStockMovements: builder.query({
      query: (params) => ({
        url: '/reports/stock/movements/',
        params,
      }),
      providesTags: ['Reports', 'Inventory'],
    }),

    generateDailyReport: builder.mutation({
      query: (data) => ({
        url: '/reports/sales/generate/',
        method: 'POST',
        body: data,
      }),
    }),

    getInventoryAnalytics: builder.query({
      query: () => '/reports/inventory/analytics/',
      providesTags: ['Inventory', 'Reports'],
    }),
  }),
  overrideExisting: false,
});

export const {
  useGetSalesReportMutation,
  useGetStockReportQuery,
  useGetStockMovementsQuery,
  useLazyGetStockMovementsQuery,
  useGenerateDailyReportMutation,
  useGetInventoryAnalyticsQuery,
} = reportsApi;
