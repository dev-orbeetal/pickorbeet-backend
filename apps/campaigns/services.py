"""Create, preview, schedule, send and cancel product-notification campaigns."""
from datetime import timedelta

from django.utils import timezone

from apps.products.models import Product

from .audience import AudienceError, reach
from .dispatch import CampaignError, campaign_image_url, dispatch, filled_copy, send_one
from .models import PRODUCT_AUDIENCES, Campaign, CampaignSettings
from .rendering import unknown_placeholders


def in_quiet_hours(now=None, settings=None):
    settings = settings or CampaignSettings.load()
    local = timezone.localtime(now or timezone.now()).time()
    start, end = settings.quiet_start, settings.quiet_end
    if start <= end:
        return start <= local < end
    return local >= start or local < end


def next_open_at(now=None, settings=None):
    """When quiet hours end. ``None`` when it is already open."""
    settings = settings or CampaignSettings.load()
    now = now or timezone.now()
    if not in_quiet_hours(now, settings):
        return None
    local = timezone.localtime(now)
    end = settings.quiet_end
    end_today = local.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    start = settings.quiet_start
    if start > end and local.time() >= start:
        return end_today + timedelta(days=1)
    return end_today


def _require_editable(campaign):
    if campaign.status not in Campaign.EDITABLE_STATUSES:
        raise CampaignError('not_editable', 'This notification has already gone out.')


def validate_copy(title, body):
    unknown = unknown_placeholders(f'{title} {body}')
    if unknown:
        names = ', '.join(f'{{{{{name}}}}}' for name in unknown)
        raise CampaignError('unknown_placeholder', f'Unknown placeholder: {names}.')


def preview(*, title, body, product=None, context=None, campaign=None):
    """Filled wording and the photo a phone would show, without sending."""
    from .models import Campaign as CampaignModel

    stand_in = campaign or CampaignModel(
        title=title or '',
        body=body or '',
        context=context or {},
        product=product,
        kind=getattr(campaign, 'kind', 'custom') if campaign else 'custom',
        cta_label=getattr(campaign, 'cta_label', '') or 'Tap to explore',
    )
    if campaign is None:
        stand_in.title = title or ''
        stand_in.body = body or ''
        stand_in.context = context or {}
        stand_in.product = product
    filled_title, filled_body, filled = filled_copy(stand_in, product)
    return {
        'title': filled_title,
        'body': filled_body,
        'cta_label': stand_in.cta_label or 'Tap to explore',
        'image': campaign_image_url(stand_in, product),
        'placeholders': filled,
    }


def estimate(*, audience, product=None, category=None, customer_ids=(), daily_cap=None):
    from .audience import audience_users

    try:
        users = audience_users(
            audience=audience, product=product, category=category,
            customer_ids=customer_ids, daily_cap=daily_cap,
        )
    except AudienceError as exc:
        raise CampaignError('audience', str(exc)) from exc
    return reach(users)


def _product(product_id):
    if not product_id:
        return None
    try:
        return Product.objects.select_related('category').prefetch_related('images', 'variants').get(pk=product_id)
    except Product.DoesNotExist as exc:
        raise CampaignError('product_not_found', 'Product not found.') from exc


def save_campaign(data, *, user=None, campaign=None):
    """Create or update a draft. Scheduling is a separate step so a send cannot be half-written."""
    if campaign is not None:
        _require_editable(campaign)
    title = (data.get('title') or '').strip()
    body = (data.get('body') or '').strip()
    if not title or not body:
        raise CampaignError('copy_required', 'Write a title and a message.')
    validate_copy(title, body)

    product = _product(data.get('product_id') or getattr(campaign, 'product_id', None))
    audience = data.get('audience') or getattr(campaign, 'audience', None) or 'all'
    if audience in PRODUCT_AUDIENCES and product is None:
        raise CampaignError('product_required', 'Choose a product for this audience.')

    fields = {
        'name': (data.get('name') or '').strip()[:120],
        'kind': data.get('kind') or getattr(campaign, 'kind', None) or 'custom',
        'title': title[:80],
        'body': body[:240],
        'cta_label': (data.get('cta_label') or 'Tap to explore')[:40],
        'product': product,
        'product_ids': [str(value) for value in (data.get('product_ids') or getattr(campaign, 'product_ids', None) or [])],
        'audience': audience,
        'customer_ids': [str(value) for value in (data.get('customer_ids') or [])],
        'context': data.get('context') or getattr(campaign, 'context', None) or {},
        'trigger': data.get('trigger') or getattr(campaign, 'trigger', '') or '',
    }
    category_id = data.get('category_id')
    if category_id:
        fields['category_id'] = category_id
    elif product is not None:
        fields['category'] = product.category

    if campaign is None:
        campaign = Campaign.objects.create(created_by=user, source=Campaign.SOURCE_MANUAL, **fields)
    else:
        for key, value in fields.items():
            setattr(campaign, key, value)
        campaign.save()
    return campaign


def attach_image(campaign, image):
    _require_editable(campaign)
    campaign.image = image
    campaign.save(update_fields=['image', 'updated_at'])
    return campaign


def schedule(campaign, when):
    _require_editable(campaign)
    if when is None:
        raise CampaignError('when_required', 'Choose a time to send.')
    if timezone.is_naive(when):
        when = timezone.make_aware(when)
    if when <= timezone.now():
        raise CampaignError('when_past', 'Pick a time in the future.')
    campaign.status = Campaign.STATUS_SCHEDULED
    campaign.scheduled_for = when
    campaign.save(update_fields=['status', 'scheduled_for', 'updated_at'])
    return campaign


def cancel(campaign):
    if campaign.status != Campaign.STATUS_SCHEDULED:
        raise CampaignError('not_scheduled', 'Only a scheduled send can be cancelled.')
    campaign.status = Campaign.STATUS_CANCELLED
    campaign.save(update_fields=['status', 'updated_at'])
    return campaign


def send_now(campaign, *, users=None, daily_cap=None):
    """Send immediately. A second call on the same campaign is ignored."""
    from .dispatch import _claim

    if campaign.status not in Campaign.EDITABLE_STATUSES:
        raise CampaignError('not_editable', 'This notification has already gone out.')
    if not _claim(campaign):
        raise CampaignError('already_sending', 'This notification is already going out.')
    if daily_cap is None and campaign.source == Campaign.SOURCE_AUTOMATION:
        daily_cap = CampaignSettings.load().daily_cap

    try:
        if users is None:
            from .audience import for_campaign as audience_for
            users = audience_for(campaign, daily_cap=daily_cap)
        recipients, pushed = dispatch(campaign, users)
    except AudienceError as exc:
        Campaign.objects.filter(pk=campaign.pk).update(
            status=Campaign.STATUS_FAILED, error=str(exc), finished_at=timezone.now(),
        )
        raise CampaignError('audience', str(exc)) from exc
    except Exception:
        Campaign.objects.filter(pk=campaign.pk).update(
            status=Campaign.STATUS_FAILED, error='Send failed.', finished_at=timezone.now(),
        )
        raise

    Campaign.objects.filter(pk=campaign.pk).update(
        status=Campaign.STATUS_SENT,
        recipients=recipients,
        pushed=pushed,
        finished_at=timezone.now(),
        error='',
    )
    campaign.refresh_from_db()
    return campaign


def test_send(campaign, customer):
    """One real phone of ``customer``, without counting as the campaign going out."""
    if customer is None or customer.role != 'customer' or not customer.is_active:
        raise CampaignError('customer_required', 'Choose a customer to send a test to.')
    title, body, _ = filled_copy(campaign)
    image = campaign_image_url(campaign)
    from .dispatch import notification_data
    data = notification_data(campaign, image=image)
    stamp = timezone.now().isoformat()
    return send_one(
        campaign, customer, image=image, title=title, body=body, data=data,
        dedupe_key=f'campaign:{campaign.id}:test:{customer.pk}:{stamp}',
    )


def send_due(now=None):
    """Every scheduled campaign whose time has come. Returns how many were sent."""
    now = now or timezone.now()
    sent = 0
    due = list(
        Campaign.objects.filter(status=Campaign.STATUS_SCHEDULED, scheduled_for__lte=now)
        .select_related('product', 'product__category', 'category')
        .prefetch_related('product__images', 'product__variants')
    )
    for campaign in due:
        try:
            send_now(campaign)
            sent += 1
        except CampaignError:
            continue
    return sent
