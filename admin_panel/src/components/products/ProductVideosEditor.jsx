'use client';

import { useEffect, useState } from 'react';
import { Link2, Plus, X } from 'lucide-react';
import toast from 'react-hot-toast';
import {
  useCreateProductVideoMutation,
  useDeleteProductVideoMutation,
  useUpdateProductVideoMutation,
} from '@/store/api/productsApi';

function variantLabel(variant) {
  if (Array.isArray(variant?.options) && variant.options.length) {
    return variant.options.map((option) => option.label).filter(Boolean).join(' / ') || variant.sku || 'Variant';
  }
  const parts = [variant?.size, variant?.color].filter(Boolean);
  return parts.length ? parts.join(' / ') : (variant?.sku || 'Variant');
}

/**
 * Shared YouTube links for a product.
 * When productId is set, saves immediately. Otherwise keeps draft URLs for create flow.
 */
export default function ProductVideosEditor({
  productId = null,
  variants = [],
  initialVideos,
  drafts = [],
  onDraftsChange,
}) {
  const [videos, setVideos] = useState(initialVideos || []);
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [createVideo] = useCreateProductVideoMutation();
  const [updateVideo] = useUpdateProductVideoMutation();
  const [deleteVideo] = useDeleteProductVideoMutation();

  useEffect(() => {
    setVideos(initialVideos || []);
  }, [initialVideos]);

  const addDraft = () => {
    const value = url.trim();
    if (!value) {
      toast.error('Paste a YouTube link first');
      return;
    }
    onDraftsChange?.([
      ...drafts,
      { key: `${Date.now()}-${drafts.length}`, youtube_url: value, title: title.trim() },
    ]);
    setUrl('');
    setTitle('');
  };

  const addLive = async () => {
    const value = url.trim();
    if (!value) {
      toast.error('Paste a YouTube link first');
      return;
    }
    if (!productId) return;
    try {
      const saved = await createVideo({
        productId,
        youtube_url: value,
        title: title.trim(),
        is_primary: videos.length === 0,
      }).unwrap();
      setVideos((current) => [...current, saved]);
      setUrl('');
      setTitle('');
      toast.success('YouTube video added');
    } catch (error) {
      toast.error(error?.data?.youtube_url?.[0] || error?.data?.detail || 'Could not add video');
    }
  };

  const removeLive = async (videoId) => {
    try {
      await deleteVideo({ videoId, productId }).unwrap();
      setVideos((current) => current.filter((item) => item.id !== videoId));
      toast.success('Video removed');
    } catch (error) {
      toast.error(error?.data?.detail || 'Could not remove video');
    }
  };

  const assignVariant = async (videoId, variant) => {
    try {
      const saved = await updateVideo({
        videoId,
        productId,
        variant: variant || null,
      }).unwrap();
      setVideos((current) => current.map((item) => (item.id === videoId ? saved : item)));
      toast.success(variant ? 'Video linked to variant' : 'Video is shared');
    } catch (error) {
      toast.error(error?.data?.detail || 'Could not update video');
    }
  };

  return (
    <div className="card">
      <h2 className="mb-1 text-lg font-semibold">YouTube videos</h2>
      <p className="mb-4 text-sm text-gray-500">
        Paste a YouTube link to show it in the product gallery on the website and app.
      </p>

      <div className="flex flex-col gap-2 sm:flex-row">
        <label className="block flex-1 text-xs font-medium text-gray-600">
          YouTube URL
          <input
            type="url"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://www.youtube.com/watch?v=…"
            className="input mt-1"
          />
        </label>
        <label className="block w-full text-xs font-medium text-gray-600 sm:w-48">
          Title (optional)
          <input
            type="text"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Unboxing"
            className="input mt-1"
          />
        </label>
        <div className="flex items-end">
          <button
            type="button"
            onClick={productId ? addLive : addDraft}
            className="btn btn-secondary whitespace-nowrap"
          >
            <Plus className="mr-1 h-4 w-4" />
            Add video
          </button>
        </div>
      </div>

      {(videos.length > 0 || drafts.length > 0) && (
        <ul className="mt-4 space-y-2">
          {videos.map((video) => (
            <li
              key={video.id}
              className="flex flex-wrap items-center gap-2 rounded-xl border border-gray-100 bg-gray-50 px-3 py-2"
            >
              <Link2 className="h-4 w-4 shrink-0 text-gray-400" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-gray-800">
                  {video.title || video.youtube_id || 'YouTube video'}
                </p>
                <p className="truncate text-xs text-gray-500">{video.youtube_url}</p>
              </div>
              {variants.length > 0 && (
                <select
                  value={video.variant || ''}
                  onChange={(event) => assignVariant(video.id, event.target.value || null)}
                  className="rounded-lg border border-gray-200 bg-white px-2 py-1 text-xs text-gray-700"
                  title="Assign to variant"
                >
                  <option value="">All variants</option>
                  {variants.map((variant) => (
                    <option key={variant.id} value={variant.id}>
                      {variantLabel(variant)}
                    </option>
                  ))}
                </select>
              )}
              <button
                type="button"
                onClick={() => removeLive(video.id)}
                className="rounded-full bg-red-500 p-1.5 text-white"
                title="Remove"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
          {drafts.map((draft) => (
            <li
              key={draft.key}
              className="flex flex-wrap items-center gap-2 rounded-xl border border-amber-100 bg-amber-50 px-3 py-2"
            >
              <Link2 className="h-4 w-4 shrink-0 text-amber-500" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-gray-800">
                  {draft.title || 'YouTube video'}
                </p>
                <p className="truncate text-xs text-gray-500">{draft.youtube_url}</p>
              </div>
              <button
                type="button"
                onClick={() => onDraftsChange?.(drafts.filter((item) => item.key !== draft.key))}
                className="rounded-full bg-red-500 p-1.5 text-white"
                title="Remove"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
