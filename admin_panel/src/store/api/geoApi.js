import { baseApi } from './baseApi';

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
  overrideExisting: false,
});

export const {
  useGetDivisionsQuery,
  useGetDistrictsQuery,
  useGetPostOfficesQuery,
} = geoApi;
