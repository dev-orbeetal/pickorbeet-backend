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

    getManualIncome: builder.query({
      query: (params) => ({
        url: '/payments/admin/manual-income/',
        params,
      }),
      providesTags: ['Income'],
    }),

    createManualIncome: builder.mutation({
      query: (data) => ({
        url: '/payments/admin/manual-income/',
        method: 'POST',
        body: data,
        formData: data instanceof FormData,
      }),
      invalidatesTags: ['Income', 'Finance', 'Transactions'],
    }),

    updateManualIncome: builder.mutation({
      query: ({ id, data }) => ({
        url: `/payments/admin/manual-income/${id}/`,
        method: 'PATCH',
        body: data,
        formData: data instanceof FormData,
      }),
      invalidatesTags: ['Income', 'Finance', 'Transactions'],
    }),

    deleteManualIncome: builder.mutation({
      query: (id) => ({
        url: `/payments/admin/manual-income/${id}/`,
        method: 'DELETE',
      }),
      invalidatesTags: ['Income', 'Finance', 'Transactions'],
    }),

    getFinanceSummary: builder.query({
      query: () => '/payments/admin/finance/summary/',
      providesTags: ['Finance'],
    }),

    getProductFinance: builder.query({
      query: () => '/payments/admin/finance/products/',
      providesTags: ['Finance'],
    }),

    getLatestTransactions: builder.query({
      query: (params) => ({
        url: '/payments/admin/finance/transactions/',
        params,
      }),
      providesTags: ['Transactions'],
    }),

    recordProductCost: builder.mutation({
      query: ({ productId, ...body }) => ({
        url: `/payments/admin/finance/products/${productId}/record-cost/`,
        method: 'POST',
        body,
      }),
      invalidatesTags: ['Finance', 'Expenses', 'Income', 'Transactions'],
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
        formData: data instanceof FormData,
      }),
      invalidatesTags: ['Expenses', 'Finance', 'Transactions'],
    }),

    updateExpense: builder.mutation({
      query: ({ id, data }) => ({
        url: `/payments/admin/expenses/${id}/`,
        method: 'PATCH',
        body: data,
        formData: data instanceof FormData,
      }),
      invalidatesTags: ['Expenses', 'Finance', 'Transactions'],
    }),

    deleteExpense: builder.mutation({
      query: (id) => ({
        url: `/payments/admin/expenses/${id}/`,
        method: 'DELETE',
      }),
      invalidatesTags: ['Expenses', 'Finance', 'Transactions', 'Inventory'],
    }),

    createPurchaseReceipt: builder.mutation({
      query: (data) => ({
        url: '/payments/admin/purchase-receipts/',
        method: 'POST',
        body: data,
        formData: data instanceof FormData,
      }),
      invalidatesTags: ['Expenses', 'Finance', 'Transactions', 'Inventory', 'Products'],
    }),

    updatePurchaseReceipt: builder.mutation({
      query: ({ id, data }) => ({
        url: `/payments/admin/purchase-receipts/${id}/`,
        method: 'PATCH',
        body: data,
        formData: data instanceof FormData,
      }),
      invalidatesTags: ['Expenses', 'Finance', 'Transactions', 'Inventory', 'Products'],
    }),

    deletePurchaseReceipt: builder.mutation({
      query: (id) => ({
        url: `/payments/admin/purchase-receipts/${id}/`,
        method: 'DELETE',
      }),
      invalidatesTags: ['Expenses', 'Finance', 'Transactions', 'Inventory', 'Products'],
    }),
  }),
  overrideExisting: false,
});

export const {
  useGetPaymentsQuery,
  useGetRefundsQuery,
  useProcessRefundMutation,
  useGetIncomeQuery,
  useGetManualIncomeQuery,
  useCreateManualIncomeMutation,
  useUpdateManualIncomeMutation,
  useDeleteManualIncomeMutation,
  useGetFinanceSummaryQuery,
  useGetProductFinanceQuery,
  useGetLatestTransactionsQuery,
  useRecordProductCostMutation,
  useGetExpensesQuery,
  useGetExpensesByProductQuery,
  useCreateExpenseMutation,
  useUpdateExpenseMutation,
  useDeleteExpenseMutation,
  useCreatePurchaseReceiptMutation,
  useUpdatePurchaseReceiptMutation,
  useDeletePurchaseReceiptMutation,
} = paymentsApi;
