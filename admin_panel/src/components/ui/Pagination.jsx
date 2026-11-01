import { ChevronLeft, ChevronRight } from 'lucide-react';

function buildPageItems(current, total) {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const items = [1];
  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);

  if (start > 2) items.push('ellipsis-start');
  for (let page = start; page <= end; page += 1) items.push(page);
  if (end < total - 1) items.push('ellipsis-end');
  items.push(total);
  return items;
}

export default function Pagination({
  page = 1,
  pageSize = 20,
  count = 0,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 50, 100],
  itemLabel = 'items',
}) {
  const totalPages = Math.max(1, Math.ceil(count / pageSize) || 1);
  const current = Math.min(Math.max(1, page), totalPages);
  const from = count === 0 ? 0 : (current - 1) * pageSize + 1;
  const to = Math.min(current * pageSize, count);
  const pages = buildPageItems(current, totalPages);

  if (count === 0) return null;

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between px-4 py-3 border-t bg-gray-50">
      <div className="flex flex-wrap items-center gap-3 text-sm text-gray-600">
        <span>
          Showing <span className="font-medium text-gray-900">{from}</span>
          –<span className="font-medium text-gray-900">{to}</span>
          {' '}of <span className="font-medium text-gray-900">{count}</span> {itemLabel}
        </span>
        {onPageSizeChange && (
          <label className="inline-flex items-center gap-2">
            <span className="text-gray-500">Rows</span>
            <select
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              className="input w-auto py-1.5 text-sm"
            >
              {pageSizeOptions.map((size) => (
                <option key={size} value={size}>{size}</option>
              ))}
            </select>
          </label>
        )}
      </div>

      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => onPageChange(current - 1)}
          disabled={current <= 1}
          className="inline-flex items-center gap-1 px-2.5 py-1.5 text-sm rounded-lg border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
          aria-label="Previous page"
        >
          <ChevronLeft className="w-4 h-4" />
          <span className="hidden sm:inline">Prev</span>
        </button>

        {pages.map((item) => (
          typeof item === 'string' ? (
            <span key={item} className="px-2 text-gray-400 select-none">…</span>
          ) : (
            <button
              key={item}
              type="button"
              onClick={() => onPageChange(item)}
              className={`min-w-[2.25rem] h-9 px-2 text-sm rounded-lg border transition-colors ${
                item === current
                  ? 'bg-primary-600 border-primary-600 text-white font-semibold'
                  : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50'
              }`}
              aria-current={item === current ? 'page' : undefined}
            >
              {item}
            </button>
          )
        ))}

        <button
          type="button"
          onClick={() => onPageChange(current + 1)}
          disabled={current >= totalPages}
          className="inline-flex items-center gap-1 px-2.5 py-1.5 text-sm rounded-lg border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
          aria-label="Next page"
        >
          <span className="hidden sm:inline">Next</span>
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
