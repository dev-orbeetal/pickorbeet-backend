export default function LoadError({ title = 'Could not load this data', onRetry }) {
  return (
    <div className="card p-8 text-center">
      <p className="text-gray-900 font-medium">{title}</p>
      <p className="text-sm text-gray-500 mt-1">The request failed. This is not an empty list.</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="btn btn-primary mt-4">
          Try again
        </button>
      )}
    </div>
  );
}
