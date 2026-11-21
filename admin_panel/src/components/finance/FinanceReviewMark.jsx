import { Check } from 'lucide-react';

export function FinanceReviewTick({ reviewed, reviewerName, canReview, onToggle, pending }) {
  if (!reviewed) return null;
  const label = reviewerName ? `Reviewed by ${reviewerName}` : 'Reviewed by finance manager';
  const icon = <Check className="h-3.5 w-3.5" strokeWidth={2.75} aria-hidden="true" />;
  if (canReview && onToggle) {
    return (
      <button
        type="button"
        onClick={onToggle}
        disabled={pending}
        className="ml-1.5 inline-flex text-emerald-600 hover:text-emerald-700"
        title={`${label}. Click to undo.`}
        aria-label={`Undo finance review${reviewerName ? ` by ${reviewerName}` : ''}`}
      >
        {icon}
      </button>
    );
  }
  return (
    <span className="ml-1.5 inline-flex text-emerald-600" title={label} aria-label={label}>
      {icon}
    </span>
  );
}

export function FinanceReviewButton({ reviewed, canReview, onToggle, pending }) {
  if (reviewed || !canReview) return null;
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={pending}
      className="mr-3 text-sm text-gray-600 hover:text-gray-900"
    >
      Review
    </button>
  );
}
