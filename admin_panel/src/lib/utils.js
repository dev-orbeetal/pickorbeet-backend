/**
 * Build a full media URL from an image path returned by the API.
 * Strips /api/v1 from the base URL so media paths resolve correctly.
 */
export function getMediaUrl(url, placeholder) {
  if (!url) return placeholder || null;
  if (url.startsWith('http')) return url;
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
  const base = apiUrl.replace(/\/api\/v1\/?$/, '');
  if (!base) return url;
  return `${base}${url}`;
}

export function adminHref(path) {
  const normalized = path.startsWith('/') ? path : `/${path}`;
  const withSlash = normalized.endsWith('/') ? normalized : `${normalized}/`;
  return `/admin${withSlash}`;
}

export function routeId(router) {
  const queryId = typeof router.query?.id === 'string' ? router.query.id : '';
  if (queryId && queryId !== '_') return queryId;
  if (typeof window === 'undefined') return undefined;
  const parts = window.location.pathname.split('/').filter(Boolean);
  const last = parts[parts.length - 1];
  return last && last !== '_' ? last : undefined;
}
