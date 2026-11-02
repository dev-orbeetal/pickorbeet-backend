import { baseApi } from './baseApi';

export const shippingApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getShipments: builder.query({
      query: (params = {}) => ({ url: '/shipping/admin/shipments/', params }),
      providesTags: (result) =>
        result?.results
          ? [
              ...result.results.map(({ id }) => ({ type: 'Shipments', id })),
              { type: 'Shipments', id: 'LIST' },
            ]
          : [{ type: 'Shipments', id: 'LIST' }],
    }),
    getShipmentSummary: builder.query({
      query: (params = {}) => ({ url: '/shipping/admin/shipments/summary/', params }),
      providesTags: [{ type: 'Shipments', id: 'SUMMARY' }],
    }),
    getShipment: builder.query({
      query: ({ id, live = false }) => ({
        url: `/shipping/admin/shipments/${id}/`,
        params: live ? { live: 1 } : undefined,
      }),
      providesTags: (_result, _error, arg) => [{ type: 'Shipments', id: arg.id }],
    }),
    refreshShipment: builder.mutation({
      query: (id) => ({
        url: `/shipping/admin/shipments/${id}/refresh/`,
        method: 'POST',
      }),
      invalidatesTags: (_result, _error, id) => [
        { type: 'Shipments', id },
        { type: 'Shipments', id: 'LIST' },
        { type: 'Shipments', id: 'SUMMARY' },
      ],
    }),
    bulkRefreshShipments: builder.mutation({
      query: (body = {}) => ({
        url: '/shipping/admin/shipments/bulk-refresh/',
        method: 'POST',
        body,
      }),
      invalidatesTags: [
        { type: 'Shipments', id: 'LIST' },
        { type: 'Shipments', id: 'SUMMARY' },
      ],
    }),
    getSteadfastBalance: builder.query({
      query: () => '/shipping/admin/steadfast/balance/',
      providesTags: ['SteadfastBalance'],
    }),
    previewShipmentImport: builder.mutation({
      query: (body) => ({
        url: '/shipping/admin/shipments/import/preview/',
        method: 'POST',
        body,
      }),
    }),
    importShipment: builder.mutation({
      query: (body) => ({
        url: '/shipping/admin/shipments/import/',
        method: 'POST',
        body,
      }),
      invalidatesTags: [
        { type: 'Shipments', id: 'LIST' },
        { type: 'Shipments', id: 'SUMMARY' },
        { type: 'Orders', id: 'LIST' },
      ],
    }),
  }),
});

export const {
  useGetShipmentsQuery,
  useGetShipmentSummaryQuery,
  useGetShipmentQuery,
  useLazyGetShipmentQuery,
  useRefreshShipmentMutation,
  useBulkRefreshShipmentsMutation,
  useGetSteadfastBalanceQuery,
  usePreviewShipmentImportMutation,
  useImportShipmentMutation,
} = shippingApi;
