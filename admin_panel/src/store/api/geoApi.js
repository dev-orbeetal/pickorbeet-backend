import { baseApi, OVERRIDE_EXISTING } from './baseApi';

export const geoApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getDivisions: builder.query({
      query: () => '/geo/divisions/',
    }),
    getDistricts: builder.query({
      query: (division) => ({
        url: '/geo/districts/',
        params: { division },
      }),
    }),
    getPostOffices: builder.query({
      query: (district) => ({
        url: '/geo/post-offices/',
        params: { district },
      }),
    }),
  }),
  overrideExisting: OVERRIDE_EXISTING,
});

export const {
  useGetDivisionsQuery,
  useGetDistrictsQuery,
  useGetPostOfficesQuery,
} = geoApi;
