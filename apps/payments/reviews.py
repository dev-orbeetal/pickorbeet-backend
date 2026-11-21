"""Finance-manager review state for income and expense transactions."""
from django.core.exceptions import ObjectDoesNotExist, ValidationError

from apps.orders.models import Order

from .models import Expense, FinanceReview, ManualIncome

REVIEW_TARGETS = {
    'expense': ('expense', Expense),
    'manual_income': ('manual_income', ManualIncome),
    'order': ('order', Order),
}


def review_state(obj):
    cached = getattr(obj, '_finance_review_state', None)
    if cached is not None:
        return cached
    try:
        review = obj.finance_review
    except ObjectDoesNotExist:
        review = None
    if review is None:
        state = {
            'finance_reviewed': False,
            'finance_reviewed_at': None,
            'finance_reviewed_by_name': None,
        }
    else:
        reviewer = review.reviewed_by
        state = {
            'finance_reviewed': True,
            'finance_reviewed_at': review.reviewed_at.isoformat() if review.reviewed_at else None,
            'finance_reviewed_by_name': reviewer.full_name if reviewer else None,
        }
    obj._finance_review_state = state
    return state


def toggle_review(user, target, record_id):
    """Mark a transaction reviewed, or clear that mark if it is already reviewed."""
    if target not in REVIEW_TARGETS:
        raise ValueError(target)
    field, model = REVIEW_TARGETS[target]
    try:
        record = model.objects.get(pk=record_id)
    except (model.DoesNotExist, ValidationError, ValueError, TypeError):
        return None
    existing = FinanceReview.objects.filter(**{field: record}).select_related('reviewed_by').first()
    if existing is not None:
        existing.delete()
        if hasattr(record, '_finance_review_state'):
            del record._finance_review_state
        return review_state(record)
    FinanceReview.objects.create(**{field: record}, reviewed_by=user)
    if hasattr(record, '_finance_review_state'):
        del record._finance_review_state
    return review_state(record)
