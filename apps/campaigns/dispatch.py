"""Turn a campaign into inbox rows, live sockets, and FCM — in batches."""
import logging

from django.db import transaction
from django.utils import timezone

from apps.notifications.delivery import publish_created, send_push, send_push_batch
from apps.notifications.models import Notification

from .images import image_url, product_thumbnail
from .models import KIND_NEW_ARRIVAL, Campaign
from .rendering import product_context, render

logger = logging.getLogger(__name__)

BATCH = 200

KIND_TO_NOTE = {
    'new_arrival': 'product.arrival',
    'low_stock': 'product.low_stock',
    'back_in_stock': 'product.back_in_stock',
    'price_drop': 'product.price_drop',
    'flash_sale': 'promo.sale',
    'custom': 'promo.custom',
}

THUMB = {
    'new_arrival': 'arrivals',
    'price_drop': 'price',
    'flash_sale': 'price',
    'low_stock': 'save',
    'back_in_stock': 'save',
    'custom': 'arrivals',
}


class CampaignError(Exception):
    def __init__(self, code, message, http_status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def note_kind(campaign):
    return KIND_TO_NOTE.get(campaign.kind, 'promo.custom')


def campaign_image_url(campaign, product=None):
    if campaign.image:
        return image_url(campaign.image.name)
    return image_url(product_thumbnail(product or campaign.product))


def filled_copy(campaign, product=None):
    context = product_context(product or campaign.product, extra=campaign.context)
    return render(campaign.title, context)[:80], render(campaign.body, context)[:240], context


def notification_data(campaign, *, product=None, image='', extra=None):
    product = product or campaign.product
    extra_ids = [str(value) for value in (campaign.product_ids or []) if value]
    digest = campaign.kind == KIND_NEW_ARRIVAL and len(extra_ids) > 1
    data = {
        'target': 'products' if digest else 'product',
        'campaign_id': str(campaign.id),
        'cta_label': campaign.cta_label or 'Tap to explore',
        'thumb': THUMB.get(campaign.kind, 'arrivals'),
        'image': image,
    }
    if product is not None:
        data.update({
            'product_id': str(product.id),
            'product_slug': product.slug,
            'product_name': product.name,
        })
        if product.category_id:
            data['category_slug'] = product.category.slug
    if extra_ids:
        data['product_ids'] = ','.join(extra_ids)
    if extra:
        data.update(extra)
    return data


def _claim(campaign):
    """Mark the campaign as sending. Returns False if another worker already took it."""
    with transaction.atomic():
        locked = Campaign.objects.select_for_update().get(pk=campaign.pk)
        if locked.status not in {Campaign.STATUS_DRAFT, Campaign.STATUS_SCHEDULED}:
            return False
        locked.status = Campaign.STATUS_SENDING
        locked.started_at = timezone.now()
        locked.error = ''
        locked.save(update_fields=['status', 'started_at', 'error', 'updated_at'])
    campaign.status = Campaign.STATUS_SENDING
    campaign.started_at = locked.started_at
    return True


def send_one(campaign, recipient, *, image, title, body, data, dedupe_key):
    """One inbox row, then the live socket and the phone. Used for a test send."""
    notification, created = Notification.objects.get_or_create(
        recipient=recipient,
        dedupe_key=dedupe_key,
        defaults={
            'kind': note_kind(campaign),
            'title': title,
            'body': body,
            'data': data,
            'campaign': campaign,
        },
    )
    if not created:
        return notification, False
    try:
        publish_created(notification)
    except Exception:
        logger.warning('Socket publish failed for test send %s', notification.id, exc_info=True)
    try:
        send_push(notification)
    except Exception:
        logger.warning('FCM failed for test send %s', notification.id, exc_info=True)
    return notification, True


def dispatch(campaign, users):
    """Write inbox rows for ``users`` and push them. Returns ``(recipients, pushed)``."""
    product = campaign.product
    title, body, _context = filled_copy(campaign, product)
    image = campaign_image_url(campaign, product)
    data = notification_data(campaign, product=product, image=image)
    kind = note_kind(campaign)
    recipients = 0
    pushed = 0
    user_ids = list(users.values_list('pk', flat=True))

    for start in range(0, len(user_ids), BATCH):
        chunk_ids = user_ids[start:start + BATCH]
        rows = [
            Notification(
                recipient_id=user_id,
                kind=kind,
                title=title,
                body=body,
                data=data,
                dedupe_key=f'campaign:{campaign.id}:{user_id}',
                campaign=campaign,
            )
            for user_id in chunk_ids
        ]
        created = Notification.objects.bulk_create(rows, ignore_conflicts=True)
        created = list(
            Notification.objects.filter(pk__in=[row.id for row in created if row.id]).select_related('recipient')
        )
        recipients += len(created)
        if not created:
            continue
        for notification in created:
            try:
                publish_created(notification)
            except Exception:
                logger.warning('Socket publish failed for %s', notification.id, exc_info=True)
        try:
            pushed += len(send_push_batch(created))
        except Exception:
            logger.warning('FCM batch failed for campaign %s', campaign.id, exc_info=True)

    return recipients, pushed
