import { baseApi, OVERRIDE_EXISTING } from './baseApi';

export const campaignsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getCampaignTemplates: builder.query({
      query: () => '/campaigns/admin/templates/',
      providesTags: ['Campaigns'],
    }),
    getCampaigns: builder.query({
      query: (params) => ({ url: '/campaigns/admin/campaigns/', params }),
      providesTags: (result) =>
        result?.results
          ? [...result.results.map(({ id }) => ({ type: 'Campaigns', id })), { type: 'Campaigns', id: 'LIST' }]
          : [{ type: 'Campaigns', id: 'LIST' }],
    }),
    getCampaign: builder.query({
      query: (id) => `/campaigns/admin/campaigns/${id}/`,
      providesTags: (result, error, id) => [{ type: 'Campaigns', id }],
    }),
    createCampaign: builder.mutation({
      query: (body) => ({ url: '/campaigns/admin/campaigns/', method: 'POST', body }),
      invalidatesTags: [{ type: 'Campaigns', id: 'LIST' }],
    }),
    updateCampaign: builder.mutation({
      query: ({ id, ...body }) => ({ url: `/campaigns/admin/campaigns/${id}/`, method: 'PATCH', body }),
      invalidatesTags: (result, error, { id }) => [{ type: 'Campaigns', id }, { type: 'Campaigns', id: 'LIST' }],
    }),
    sendCampaign: builder.mutation({
      query: (id) => ({ url: `/campaigns/admin/campaigns/${id}/send/`, method: 'POST' }),
      invalidatesTags: (result, error, id) => [{ type: 'Campaigns', id }, { type: 'Campaigns', id: 'LIST' }],
    }),
    scheduleCampaign: builder.mutation({
      query: ({ id, when }) => ({
        url: `/campaigns/admin/campaigns/${id}/schedule/`,
        method: 'POST',
        body: { when },
      }),
      invalidatesTags: (result, error, { id }) => [{ type: 'Campaigns', id }, { type: 'Campaigns', id: 'LIST' }],
    }),
    cancelCampaign: builder.mutation({
      query: (id) => ({ url: `/campaigns/admin/campaigns/${id}/cancel/`, method: 'POST' }),
      invalidatesTags: (result, error, id) => [{ type: 'Campaigns', id }, { type: 'Campaigns', id: 'LIST' }],
    }),
    testCampaign: builder.mutation({
      query: ({ id, customer_id }) => ({
        url: `/campaigns/admin/campaigns/${id}/test/`,
        method: 'POST',
        body: { customer_id },
      }),
    }),
    previewCampaign: builder.mutation({
      query: (body) => ({ url: '/campaigns/admin/preview/', method: 'POST', body }),
    }),
    estimateCampaign: builder.mutation({
      query: (body) => ({ url: '/campaigns/admin/estimate/', method: 'POST', body }),
    }),
    getAutomations: builder.query({
      query: () => '/campaigns/admin/automations/',
      providesTags: [{ type: 'Campaigns', id: 'AUTOMATIONS' }],
    }),
    updateAutomation: builder.mutation({
      query: ({ trigger, ...body }) => ({
        url: `/campaigns/admin/automations/${trigger}/`,
        method: 'PATCH',
        body,
      }),
      invalidatesTags: [{ type: 'Campaigns', id: 'AUTOMATIONS' }],
    }),
    getCampaignSettings: builder.query({
      query: () => '/campaigns/admin/settings/',
      providesTags: [{ type: 'Campaigns', id: 'SETTINGS' }],
    }),
    updateCampaignSettings: builder.mutation({
      query: (body) => ({ url: '/campaigns/admin/settings/', method: 'PATCH', body }),
      invalidatesTags: [{ type: 'Campaigns', id: 'SETTINGS' }],
    }),
    searchCampaignCustomers: builder.query({
      query: (params) => ({ url: '/campaigns/admin/customers/', params }),
    }),
  }),
  overrideExisting: OVERRIDE_EXISTING,
});

export const {
  useGetCampaignTemplatesQuery,
  useGetCampaignsQuery,
  useGetCampaignQuery,
  useCreateCampaignMutation,
  useUpdateCampaignMutation,
  useSendCampaignMutation,
  useScheduleCampaignMutation,
  useCancelCampaignMutation,
  useTestCampaignMutation,
  usePreviewCampaignMutation,
  useEstimateCampaignMutation,
  useGetAutomationsQuery,
  useUpdateAutomationMutation,
  useGetCampaignSettingsQuery,
  useUpdateCampaignSettingsMutation,
  useLazySearchCampaignCustomersQuery,
} = campaignsApi;
