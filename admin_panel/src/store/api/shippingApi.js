import { baseApi, OVERRIDE_EXISTING } from './baseApi';

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
      invalidatesTags: (result, _error, id) => [
        { type: 'Shipments', id },
        { type: 'Shipments', id: 'LIST' },
        { type: 'Shipments', id: 'SUMMARY' },
        ...(result?.order?.id ? [{ type: 'Orders', id: result.order.id }] : []),
        { type: 'Orders', id: 'LIST' },
        'Dashboard',
      ],
    }),
    bulkRefreshShipments: builder.mutation({
      query: (body = {}) => ({
        url: '/shipping/admin/shipments/bulk-refresh/',
        method: 'POST',
        body,
      }),
      invalidatesTags: [
        { type: 'Shipments' },
        { type: 'Orders' },
        'Dashboard',
      ],
    }),
    getBookingPreview: builder.query({
      query: ({ orderId, policeStationId }) => ({
        url: `/shipping/admin/orders/${orderId}/booking-preview/`,
        params: policeStationId ? { police_station_id: policeStationId } : undefined,
      }),
      keepUnusedDataFor: 0,
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
  overrideExisting: OVERRIDE_EXISTING,
});

export const {
  useGetShipmentsQuery,
  useGetShipmentSummaryQuery,
  useGetShipmentQuery,
  useLazyGetShipmentQuery,
  useRefreshShipmentMutation,
  useBulkRefreshShipmentsMutation,
  useGetBookingPreviewQuery,
  useGetSteadfastBalanceQuery,
  usePreviewShipmentImportMutation,
  useImportShipmentMutation,
} = shippingApi;
