import { baseApi } from './baseApi';

export const productsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getProducts: builder.query({
      query: (params) => ({
        url: '/products/admin/products/',
        params,
      }),
      providesTags: (result) =>
        result?.results
          ? [
              ...result.results.map(({ id }) => ({ type: 'Products', id })),
              { type: 'Products', id: 'LIST' },
            ]
          : [{ type: 'Products', id: 'LIST' }],
    }),

    getProduct: builder.query({
      query: (id) => `/products/admin/products/${id}/`,
      providesTags: (result, error, id) => [{ type: 'Products', id }],
    }),

    createProduct: builder.mutation({
      query: (data) => ({
        url: '/products/admin/products/',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: [{ type: 'Products', id: 'LIST' }, 'Inventory', 'Finance'],
    }),

    updateProduct: builder.mutation({
      query: ({ id, ...data }) => ({
        url: `/products/admin/products/${id}/`,
        method: 'PATCH',
        body: data,
      }),
      invalidatesTags: (result, error, { id }) => [
        { type: 'Products', id },
        { type: 'Products', id: 'LIST' },
      ],
    }),

    deleteProduct: builder.mutation({
      query: (id) => ({
        url: `/products/admin/products/${id}/`,
        method: 'DELETE',
      }),
      invalidatesTags: [{ type: 'Products', id: 'LIST' }],
    }),

    updateStock: builder.mutation({
      query: ({ id, ...data }) => ({
        url: `/products/admin/products/${id}/stock/`,
        method: 'POST',
        body: data,
      }),
      invalidatesTags: (result, error, { id }) => [
        { type: 'Products', id },
        { type: 'Products', id: 'LIST' },
        'Inventory',
      ],
    }),

    getLowStock: builder.query({
      query: () => '/products/admin/low-stock/',
      providesTags: ['Products', 'Inventory'],
    }),

    uploadProductImage: builder.mutation({
      query: ({ productId, imageData }) => ({
        url: `/products/admin/products/${productId}/images/`,
        method: 'POST',
        body: imageData,
      }),
      invalidatesTags: (result, error, { productId }) => [
        { type: 'Products', id: productId },
      ],
    }),

    updateProductImage: builder.mutation({
      query: ({ imageId, ...data }) => ({
        url: `/products/admin/images/${imageId}/`,
        method: 'PATCH',
        body: data,
      }),
      invalidatesTags: (result, error, { productId }) => [
        { type: 'Products', id: productId || 'LIST' },
        { type: 'Products', id: 'LIST' },
      ],
    }),

    deleteProductImage: builder.mutation({
      query: (imageId) => ({
        url: `/products/admin/images/${imageId}/`,
        method: 'DELETE',
      }),
      invalidatesTags: [{ type: 'Products', id: 'LIST' }],
    }),

    createVariant: builder.mutation({
      query: ({ productId, ...data }) => ({
        url: `/products/admin/products/${productId}/variants/`,
        method: 'POST',
        body: data,
      }),
      invalidatesTags: (result, error, { productId }) => [
        { type: 'Products', id: productId },
      ],
    }),

    updateVariant: builder.mutation({
      query: ({ productId, variantId, ...data }) => ({
        url: `/products/admin/products/${productId}/variants/${variantId}/`,
        method: 'PATCH',
        body: data,
      }),
      invalidatesTags: (result, error, { productId }) => [
        { type: 'Products', id: productId },
      ],
    }),

    syncVariantSetup: builder.mutation({
      query: ({ productId, ...body }) => ({
        url: `/products/admin/products/${productId}/variant-setup/`,
        method: 'PUT',
        body,
      }),
      invalidatesTags: (result, error, { productId }) => [
        { type: 'Products', id: productId },
      ],
    }),

    deleteVariant: builder.mutation({
      query: ({ productId, variantId }) => ({
        url: `/products/admin/products/${productId}/variants/${variantId}/`,
        method: 'DELETE',
      }),
      invalidatesTags: (result, error, { productId }) => [
        { type: 'Products', id: productId },
      ],
    }),

    getInventoryItems: builder.query({
      query: (params) => ({
        url: '/products/admin/inventory/',
        params,
      }),
      providesTags: ['Inventory'],
    }),

    updateProductStock: builder.mutation({
      query: ({ productId, ...data }) => ({
        url: `/products/admin/products/${productId}/stock/`,
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['Inventory', 'Products', 'Finance'],
    }),

    updateVariantStock: builder.mutation({
      query: ({ variantId, ...data }) => ({
        url: `/products/admin/variants/${variantId}/stock/`,
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['Inventory', 'Products', 'Finance'],
    }),

    transferProductStock: builder.mutation({
      query: ({ productId, ...data }) => ({
        url: `/products/admin/products/${productId}/stock/transfer/`,
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['Inventory', 'Products', 'Finance'],
    }),

    transferVariantStock: builder.mutation({
      query: ({ variantId, ...data }) => ({
        url: `/products/admin/variants/${variantId}/stock/transfer/`,
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['Inventory', 'Products', 'Finance'],
    }),

    uploadInventoryCsv: builder.mutation({
      query: (file) => {
        const body = new FormData();
        body.append('file', file);
        return {
          url: '/products/admin/inventory/upload/',
          method: 'POST',
          body,
          formData: true,
        };
      },
      invalidatesTags: ['Inventory', 'Products', 'Finance'],
    }),

    getSellers: builder.query({
      query: () => '/products/admin/sellers/',
      providesTags: ['Staff'],
    }),

    getStoreSettings: builder.query({
      query: () => '/products/admin/settings/',
      providesTags: ['StoreSettings'],
    }),

    updateStoreSettings: builder.mutation({
      query: (data) => {
        const isFormData = data instanceof FormData;
        return {
          url: '/products/admin/settings/',
          method: 'PATCH',
          body: data,
          formData: isFormData,
        };
      },
      invalidatesTags: ['StoreSettings'],
    }),

    getBanners: builder.query({
      query: () => '/products/admin/banners/',
      providesTags: ['Banners'],
    }),

    createBanner: builder.mutation({
      query: (data) => ({
        url: '/products/admin/banners/',
        method: 'POST',
        body: data,
        formData: data instanceof FormData,
      }),
      invalidatesTags: ['Banners'],
    }),

    updateBanner: builder.mutation({
      query: ({ id, data }) => ({
        url: `/products/admin/banners/${id}/`,
        method: 'PATCH',
        body: data,
        formData: data instanceof FormData,
      }),
      invalidatesTags: ['Banners'],
    }),

    deleteBanner: builder.mutation({
      query: (id) => ({
        url: `/products/admin/banners/${id}/`,
        method: 'DELETE',
      }),
      invalidatesTags: ['Banners'],
    }),

    getHomepageSections: builder.query({
      query: () => '/products/admin/homepage-sections/',
      providesTags: ['HomepageSections'],
    }),

    updateHomepageSection: builder.mutation({
      query: ({ key, data }) => ({
        url: `/products/admin/homepage-sections/${key}/`,
        method: 'PATCH',
        body: data,
        formData: data instanceof FormData,
      }),
      invalidatesTags: ['HomepageSections'],
    }),
  }),
  overrideExisting: false,
});

export const {
  useGetProductsQuery,
  useLazyGetProductsQuery,
  useGetProductQuery,
  useLazyGetProductQuery,
  useCreateProductMutation,
  useUpdateProductMutation,
  useDeleteProductMutation,
  useUpdateStockMutation,
  useGetLowStockQuery,
  useUploadProductImageMutation,
  useUpdateProductImageMutation,
  useDeleteProductImageMutation,
  useCreateVariantMutation,
  useUpdateVariantMutation,
  useDeleteVariantMutation,
  useSyncVariantSetupMutation,
  useGetInventoryItemsQuery,
  useUpdateProductStockMutation,
  useUpdateVariantStockMutation,
  useTransferProductStockMutation,
  useTransferVariantStockMutation,
  useUploadInventoryCsvMutation,
  useGetSellersQuery,
  useGetStoreSettingsQuery,
  useUpdateStoreSettingsMutation,
  useGetBannersQuery,
  useCreateBannerMutation,
  useUpdateBannerMutation,
  useDeleteBannerMutation,
  useGetHomepageSectionsQuery,
  useUpdateHomepageSectionMutation,
} = productsApi;
