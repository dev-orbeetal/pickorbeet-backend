import { baseApi } from './baseApi';

export const paymentsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getPayments: builder.query({
      query: (params) => ({
        url: '/payments/admin/',
        params,
      }),
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
      invalidatesTags: ['Payments', 'Finance'],
    }),

    getIncome: builder.query({
      query: (params) => ({
        url: '/payments/admin/income/',
        params,
      }),
      providesTags: ['Income'],
    }),

    getFinanceSummary: builder.query({
      query: () => '/payments/admin/finance/summary/',
      providesTags: ['Finance'],
    }),

    getProductFinance: builder.query({
      query: () => '/payments/admin/finance/products/',
      providesTags: ['Finance'],
    }),

    getExpenses: builder.query({
      query: (params) => ({
        url: '/payments/admin/expenses/',
        params,
      }),
      providesTags: ['Expenses'],
    }),

    getExpensesByProduct: builder.query({
      query: (params) => ({
        url: '/payments/admin/expenses/by-product/',
        params,
      }),
      providesTags: ['Expenses'],
    }),

    createExpense: builder.mutation({
      query: (data) => ({
        url: '/payments/admin/expenses/',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['Expenses', 'Finance'],
    }),

    updateExpense: builder.mutation({
      query: ({ id, ...data }) => ({
        url: `/payments/admin/expenses/${id}/`,
        method: 'PATCH',
        body: data,
      }),
      invalidatesTags: ['Expenses', 'Finance'],
    }),

    deleteExpense: builder.mutation({
      query: (id) => ({
        url: `/payments/admin/expenses/${id}/`,
        method: 'DELETE',
      }),
      invalidatesTags: ['Expenses', 'Finance'],
    }),
  }),
  overrideExisting: false,
});

export const {
  useGetPaymentsQuery,
  useGetRefundsQuery,
  useProcessRefundMutation,
  useGetIncomeQuery,
  useGetFinanceSummaryQuery,
  useGetProductFinanceQuery,
  useGetExpensesQuery,
  useGetExpensesByProductQuery,
  useCreateExpenseMutation,
  useUpdateExpenseMutation,
  useDeleteExpenseMutation,
} = paymentsApi;
