import { baseApi } from './baseApi';

const contactApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getContactMessages: builder.query({
      query: (params) => ({
        url: '/products/admin/contact/',
        params,
      }),
      providesTags: ['Contact'],
    }),
    getContactMessage: builder.query({
      query: (id) => `/products/admin/contact/${id}/`,
      providesTags: (result, error, id) => [{ type: 'Contact', id }],
    }),
    updateContactMessage: builder.mutation({
      query: ({ id, ...data }) => ({
        url: `/products/admin/contact/${id}/`,
        method: 'PATCH',
        body: data,
      }),
      invalidatesTags: ['Contact'],
    }),
    deleteContactMessage: builder.mutation({
      query: (id) => ({
        url: `/products/admin/contact/${id}/`,
        method: 'DELETE',
      }),
      invalidatesTags: ['Contact'],
    }),
  }),
});

export const {
  useGetContactMessagesQuery,
  useGetContactMessageQuery,
  useUpdateContactMessageMutation,
  useDeleteContactMessageMutation,
} = contactApi;
