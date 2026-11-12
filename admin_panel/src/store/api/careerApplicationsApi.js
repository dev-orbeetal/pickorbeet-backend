import { baseApi, OVERRIDE_EXISTING } from './baseApi';

const careerApplicationsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getCareerApplications: builder.query({
      query: (params) => ({
        url: '/careers/admin/applications/',
        params,
      }),
      providesTags: ['CareerApplication'],
    }),
    getCareerApplication: builder.query({
      query: (id) => `/careers/admin/applications/${id}/`,
      providesTags: (result, error, id) => [{ type: 'CareerApplication', id }],
    }),
    updateCareerApplication: builder.mutation({
      query: ({ id, ...data }) => ({
        url: `/careers/admin/applications/${id}/`,
        method: 'PATCH',
        body: data,
      }),
      invalidatesTags: ['CareerApplication'],
    }),
    deleteCareerApplication: builder.mutation({
      query: (id) => ({
        url: `/careers/admin/applications/${id}/`,
        method: 'DELETE',
      }),
      invalidatesTags: ['CareerApplication'],
    }),
  }),
  overrideExisting: OVERRIDE_EXISTING,
});

export const {
  useGetCareerApplicationsQuery,
  useGetCareerApplicationQuery,
  useUpdateCareerApplicationMutation,
  useDeleteCareerApplicationMutation,
} = careerApplicationsApi;
