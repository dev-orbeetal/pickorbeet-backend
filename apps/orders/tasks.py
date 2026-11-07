"""Order mail sent after the request that changed the order has replied."""
import logging
from smtplib import SMTPException

from celery import shared_task

from .models import Order

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5)
def send_order_status_email_task(self, order_id, status):
    from .emails import send_order_status_email

    order = Order.objects.filter(pk=order_id).first()
    # A later status queues its own mail; this one would describe the wrong step.
    if order is None or order.order_status != status:
        return False
    try:
        return send_order_status_email(order)
    except (SMTPException, OSError) as exc:
        logger.warning('The %s email for %s failed; retrying', status, order_id, exc_info=True)
        raise self.retry(exc=exc, countdown=min(900, 60 * 2 ** self.request.retries))


@shared_task(bind=True, max_retries=5)
def send_invoice_email_task(self, order_id):
    from .emails import send_invoice_email

    order = Order.objects.filter(pk=order_id).first()
    if order is None:
        return False
    try:
        return send_invoice_email(order)
    except (SMTPException, OSError) as exc:
        logger.warning('The invoice email for %s failed; retrying', order_id, exc_info=True)
        raise self.retry(exc=exc, countdown=min(900, 60 * 2 ** self.request.retries))
