import { baseApi } from './baseApi';

export const paymentsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getPayments: builder.query({
      query: () => '/payments/admin/',
      providesTags: ['Payments'],
    }),

    getRefunds: builder.query({
      query: () => '/payments/admin/refunds/',
      providesTags: ['Payments'],
    }),

    processRefund: builder.mutation({
      query: ({ id, ...data }) => ({
        url: `/payments/admin/refunds/${id}/process/`,
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['Payments'],
    }),
  }),
  overrideExisting: false,
});

export const {
  useGetPaymentsQuery,
  useGetRefundsQuery,
  useProcessRefundMutation,
} = paymentsApi;
