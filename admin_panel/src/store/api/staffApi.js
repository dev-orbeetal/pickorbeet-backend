import { baseApi } from './baseApi';

export const staffApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getStaffList: builder.query({
      query: () => '/auth/staff/',
      transformResponse: (response) => {
        // Handle both paginated {results: [...]} and flat array responses
        return Array.isArray(response) ? response : (response?.results || []);
      },
      providesTags: (result) =>
        result && Array.isArray(result)
          ? [
              ...result.map(({ id }) => ({ type: 'Staff', id })),
              { type: 'Staff', id: 'LIST' },
            ]
          : [{ type: 'Staff', id: 'LIST' }],
    }),

    getStaffMember: builder.query({
      query: (id) => `/auth/staff/${id}/`,
      providesTags: (result, error, id) => [{ type: 'Staff', id }],
    }),

    createStaffMember: builder.mutation({
      query: (data) => ({
        url: '/auth/staff/',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: [{ type: 'Staff', id: 'LIST' }],
    }),

    updateStaffMember: builder.mutation({
      query: ({ id, ...data }) => ({
        url: `/auth/staff/${id}/`,
        method: 'PATCH',
        body: data,
      }),
      invalidatesTags: (result, error, { id }) => [
        { type: 'Staff', id },
        { type: 'Staff', id: 'LIST' },
      ],
    }),

    deleteStaffMember: builder.mutation({
      query: (id) => ({
        url: `/auth/staff/${id}/`,
        method: 'DELETE',
      }),
      invalidatesTags: [{ type: 'Staff', id: 'LIST' }],
    }),
  }),
  overrideExisting: false,
});

export const {
  useGetStaffListQuery,
  useGetStaffMemberQuery,
  useCreateStaffMemberMutation,
  useUpdateStaffMemberMutation,
  useDeleteStaffMemberMutation,
} = staffApi;
