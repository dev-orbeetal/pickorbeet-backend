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
  return normalized.endsWith('/') ? normalized : `${normalized}/`;
}

export function routeId(router) {
  const queryId = typeof router.query?.id === 'string' ? router.query.id : '';
  if (queryId && queryId !== '_') return queryId;
  if (typeof window === 'undefined') return undefined;
  const parts = window.location.pathname.split('/').filter(Boolean);
  const last = parts[parts.length - 1];
  return last && last !== '_' ? last : undefined;
}

export function stockTotals(product) {
  const variants = product.variants || [];
  if (variants.length > 0) {
    const warehouse = variants.reduce((sum, v) => sum + Number(v.warehouse_stock || 0), 0);
    const dealer = variants.reduce((sum, v) => sum + Number(v.dealer_stock || 0), 0);
    return { warehouse, dealer, total: warehouse + dealer };
  }
  const warehouse = Number(product.warehouse_stock || 0);
  const dealer = Number(product.dealer_stock || 0);
  return {
    warehouse,
    dealer,
    total: warehouse + dealer || Number(product.stock_quantity || 0),
  };
}

// crypto.randomUUID needs HTTPS or localhost; getRandomValues works everywhere.
export function newIdempotencyKey() {
  if (crypto.randomUUID) return crypto.randomUUID();
  return '10000000-1000-4000-8000-100000000000'.replace(/[018]/g, (digit) => (
    (Number(digit) ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (Number(digit) / 4)))).toString(16)
  ));
}
