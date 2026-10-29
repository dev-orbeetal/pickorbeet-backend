import { baseApi } from './baseApi';

export const customersApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getCustomers: builder.query({
      query: (params) => ({
        url: '/auth/customers/',
        params,
      }),
      providesTags: ['Customers'],
    }),

    getCustomerOrders: builder.query({
      query: (customerId) => ({
        url: '/orders/admin/',
        params: { customer: customerId },
      }),
      providesTags: (result, error, customerId) => [
        { type: 'Orders', id: `customer-${customerId}` },
      ],
    }),
  }),
  overrideExisting: false,
});

export const {
  useGetCustomersQuery,
  useLazyGetCustomerOrdersQuery,
} = customersApi;
