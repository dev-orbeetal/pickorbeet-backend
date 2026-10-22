import { baseApi } from './baseApi';

export const categoriesApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getCategories: builder.query({
      query: () => '/products/admin/categories/',
      transformResponse: (response) => {
        // Handle both paginated { results: [...] } and direct array responses
        return Array.isArray(response) ? response : (response?.results || []);
      },
      providesTags: (result) =>
        result && Array.isArray(result)
          ? [
              ...result.map(({ id }) => ({ type: 'Categories', id })),
              { type: 'Categories', id: 'LIST' },
            ]
          : [{ type: 'Categories', id: 'LIST' }],
    }),

    getCategory: builder.query({
      query: (id) => `/products/admin/categories/${id}/`,
      providesTags: (result, error, id) => [{ type: 'Categories', id }],
    }),

    createCategory: builder.mutation({
      query: (data) => {
        const isFormData = data instanceof FormData;
        return {
          url: '/products/admin/categories/',
          method: 'POST',
          body: data,
          formData: isFormData,
        };
      },
      invalidatesTags: [{ type: 'Categories', id: 'LIST' }],
    }),

    updateCategory: builder.mutation({
      query: ({ id, data }) => {
        const isFormData = data instanceof FormData;
        return {
          url: `/products/admin/categories/${id}/`,
          method: 'PATCH',
          body: data,
          formData: isFormData,
        };
      },
      invalidatesTags: (result, error, { id }) => [
        { type: 'Categories', id },
        { type: 'Categories', id: 'LIST' },
      ],
    }),

    deleteCategory: builder.mutation({
      query: (id) => ({
        url: `/products/admin/categories/${id}/`,
        method: 'DELETE',
      }),
      invalidatesTags: [{ type: 'Categories', id: 'LIST' }],
    }),

    createSubcategory: builder.mutation({
      query: (data) => {
        const isFormData = data instanceof FormData;
        return {
          url: '/products/admin/subcategories/',
          method: 'POST',
          body: data,
          formData: isFormData,
        };
      },
      invalidatesTags: [{ type: 'Categories', id: 'LIST' }],
    }),

    updateSubcategory: builder.mutation({
      query: ({ id, data }) => {
        const isFormData = data instanceof FormData;
        return {
          url: `/products/admin/subcategories/${id}/`,
          method: 'PATCH',
          body: data,
          formData: isFormData,
        };
      },
      invalidatesTags: [{ type: 'Categories', id: 'LIST' }],
    }),

    deleteSubcategory: builder.mutation({
      query: (id) => ({
        url: `/products/admin/subcategories/${id}/`,
        method: 'DELETE',
      }),
      invalidatesTags: [{ type: 'Categories', id: 'LIST' }],
    }),
  }),
  overrideExisting: false,
});

export const {
  useGetCategoriesQuery,
  useGetCategoryQuery,
  useCreateCategoryMutation,
  useUpdateCategoryMutation,
  useDeleteCategoryMutation,
  useCreateSubcategoryMutation,
  useUpdateSubcategoryMutation,
  useDeleteSubcategoryMutation,
} = categoriesApi;
