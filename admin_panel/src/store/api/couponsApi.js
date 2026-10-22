import { baseApi } from './baseApi';

export const couponsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getCoupons: builder.query({
      query: (params) => ({
        url: '/orders/admin/coupons/',
        params,
      }),
      providesTags: ['Coupons'],
    }),
    getCoupon: builder.query({
      query: (id) => `/orders/admin/coupons/${id}/`,
      providesTags: (result, error, id) => [{ type: 'Coupons', id }],
    }),
    getCouponStats: builder.query({
      query: (id) => `/orders/admin/coupons/${id}/stats/`,
      providesTags: (result, error, id) => [{ type: 'Coupons', id }],
    }),
    createCoupon: builder.mutation({
      query: (data) => ({
        url: '/orders/admin/coupons/',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['Coupons'],
    }),
    updateCoupon: builder.mutation({
      query: ({ id, data }) => ({
        url: `/orders/admin/coupons/${id}/`,
        method: 'PATCH',
        body: data,
      }),
      invalidatesTags: (result, error, { id }) => [{ type: 'Coupons', id }, 'Coupons'],
    }),
    deleteCoupon: builder.mutation({
      query: (id) => ({
        url: `/orders/admin/coupons/${id}/`,
        method: 'DELETE',
      }),
      invalidatesTags: ['Coupons'],
    }),
    validateCoupon: builder.mutation({
      query: (data) => ({
        url: '/orders/coupons/validate/',
        method: 'POST',
        body: data,
      }),
    }),
  }),
});

export const {
  useGetCouponsQuery,
  useGetCouponQuery,
  useGetCouponStatsQuery,
  useCreateCouponMutation,
  useUpdateCouponMutation,
  useDeleteCouponMutation,
  useValidateCouponMutation,
} = couponsApi;
