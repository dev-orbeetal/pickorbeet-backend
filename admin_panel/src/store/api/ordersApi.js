import { baseApi } from './baseApi';

export const ordersApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getOrders: builder.query({
      query: (params) => ({
        url: '/orders/admin/',
        params,
      }),
      providesTags: (result) =>
        result?.results
          ? [
              ...result.results.map(({ id }) => ({ type: 'Orders', id })),
              { type: 'Orders', id: 'LIST' },
            ]
          : [{ type: 'Orders', id: 'LIST' }],
    }),

    getOrder: builder.query({
      query: (id) => `/orders/admin/${id}/`,
      providesTags: (result, error, id) => [{ type: 'Orders', id }],
    }),

    updateOrderStatus: builder.mutation({
      query: ({ id, ...data }) => ({
        url: `/orders/admin/${id}/status/`,
        method: 'POST',
        body: data,
      }),
      invalidatesTags: (result, error, { id }) => [
        { type: 'Orders', id },
        { type: 'Orders', id: 'LIST' },
        'Dashboard',
      ],
    }),

    createInShopOrder: builder.mutation({
      query: (data) => ({
        url: '/orders/admin/in-shop/',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: [
        { type: 'Orders', id: 'LIST' },
        'Dashboard',
        'Inventory',
        { type: 'Products', id: 'LIST' },
      ],
    }),

    deleteOrder: builder.mutation({
      query: (id) => ({
        url: `/orders/admin/${id}/`,
        method: 'DELETE',
      }),
      invalidatesTags: [
        { type: 'Orders', id: 'LIST' },
        'Dashboard',
      ],
    }),

    // Delivery Options
    getDeliveryOptions: builder.query({
      query: () => '/orders/admin/delivery-options/',
      providesTags: ['DeliveryOptions'],
    }),

    createDeliveryOption: builder.mutation({
      query: (data) => ({
        url: '/orders/admin/delivery-options/',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['DeliveryOptions'],
    }),

    updateDeliveryOption: builder.mutation({
      query: ({ id, ...data }) => ({
        url: `/orders/admin/delivery-options/${id}/`,
        method: 'PATCH',
        body: data,
      }),
      invalidatesTags: ['DeliveryOptions'],
    }),

    deleteDeliveryOption: builder.mutation({
      query: (id) => ({
        url: `/orders/admin/delivery-options/${id}/`,
        method: 'DELETE',
      }),
      invalidatesTags: ['DeliveryOptions'],
    }),
  }),
  overrideExisting: false,
});

export const {
  useGetOrdersQuery,
  useLazyGetOrdersQuery,
  useGetOrderQuery,
  useUpdateOrderStatusMutation,
  useCreateInShopOrderMutation,
  useDeleteOrderMutation,
  useGetDeliveryOptionsQuery,
  useCreateDeliveryOptionMutation,
  useUpdateDeliveryOptionMutation,
  useDeleteDeliveryOptionMutation,
} = ordersApi;
