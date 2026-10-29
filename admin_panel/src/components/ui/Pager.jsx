export default function Pager({ page, count, pageSize = 20, onPage }) {
  const total = Number(count || 0);
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total <= pageSize) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <div className="flex flex-col gap-3 border-t px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm text-gray-500">
        {from}–{to} of {total}
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          className="btn btn-secondary"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
        >
          Previous
        </button>
        <span className="text-sm text-gray-600">Page {page} of {pages}</span>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
        >
          Next
        </button>
      </div>
    </div>
  );
}
