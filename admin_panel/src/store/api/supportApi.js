import { baseApi } from './baseApi';

const supportApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getSupportInbox: builder.query({
      query: () => '/support/inbox/',
      providesTags: ['Support'],
    }),
    getSupportThread: builder.query({
      query: (id) => `/support/inbox/${id}/`,
      providesTags: (result, error, id) => [{ type: 'SupportThread', id }],
      async onQueryStarted(_id, { dispatch, queryFulfilled }) {
        try {
          await queryFulfilled;
        } catch {
          return;
        }
        dispatch(supportApi.util.invalidateTags(['Support']));
      },
    }),
    markSupportRead: builder.mutation({
      query: (id) => ({
        url: `/support/inbox/${id}/read/`,
        method: 'POST',
      }),
      invalidatesTags: ['Support'],
    }),
    replySupport: builder.mutation({
      query: ({ id, body }) => ({
        url: `/support/inbox/${id}/reply/`,
        method: 'POST',
        body: { body },
      }),
      invalidatesTags: (result, error, { id }) => ['Support', { type: 'SupportThread', id }],
    }),
  }),
});

export const {
  useGetSupportInboxQuery,
  useGetSupportThreadQuery,
  useMarkSupportReadMutation,
  useReplySupportMutation,
} = supportApi;

export { supportApi };
