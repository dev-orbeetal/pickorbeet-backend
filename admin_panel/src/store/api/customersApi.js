import { baseApi, OVERRIDE_EXISTING } from './baseApi';

export const customersApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getCustomers: builder.query({
      query: (params) => ({
        url: '/auth/customers/',
        params,
      }),
      providesTags: (result) => [
        { type: 'Customers', id: 'LIST' },
        ...(result?.results || []).map((user) => ({ type: 'Customers', id: user.id })),
      ],
    }),

    getCustomerSummary: builder.query({
      query: () => '/auth/customers/summary/',
      providesTags: [{ type: 'Customers', id: 'SUMMARY' }],
    }),

    getCustomer: builder.query({
      query: (id) => `/auth/customers/${id}/`,
      providesTags: (result, error, id) => [{ type: 'Customers', id }],
    }),

    updateCustomer: builder.mutation({
      query: ({ id, ...body }) => ({
        url: `/auth/customers/${id}/`,
        method: 'PATCH',
        body,
      }),
      invalidatesTags: (result, error, { id }) => [
        { type: 'Customers', id },
        { type: 'Customers', id: 'LIST' },
        { type: 'Customers', id: 'SUMMARY' },
      ],
    }),

    createCustomerAddress: builder.mutation({
      query: ({ userId, ...body }) => ({
        url: `/auth/customers/${userId}/addresses/`,
        method: 'POST',
        body,
      }),
      invalidatesTags: (result, error, { userId }) => [{ type: 'Customers', id: userId }],
    }),

    updateCustomerAddress: builder.mutation({
      query: ({ userId, addressId, ...body }) => ({
        url: `/auth/customers/${userId}/addresses/${addressId}/`,
        method: 'PATCH',
        body,
      }),
      invalidatesTags: (result, error, { userId }) => [{ type: 'Customers', id: userId }],
    }),

    deleteCustomerAddress: builder.mutation({
      query: ({ userId, addressId }) => ({
        url: `/auth/customers/${userId}/addresses/${addressId}/`,
        method: 'DELETE',
      }),
      invalidatesTags: (result, error, { userId }) => [{ type: 'Customers', id: userId }],
    }),
  }),
  overrideExisting: OVERRIDE_EXISTING,
});

export const {
  useGetCustomersQuery,
  useGetCustomerSummaryQuery,
  useGetCustomerQuery,
  useUpdateCustomerMutation,
  useCreateCustomerAddressMutation,
  useUpdateCustomerAddressMutation,
  useDeleteCustomerAddressMutation,
} = customersApi;
