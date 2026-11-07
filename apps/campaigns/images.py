"""Notification-sized product photos. FCM drops images over 1 MB, and phones crop to a square."""
import hashlib
import io
import logging

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from core.mailer import absolute_media

logger = logging.getLogger(__name__)

SIZE = 720
MAX_BYTES = 300 * 1024


def _source(product):
    images = list(product.images.all())
    if not images:
        return None
    primary = next((image for image in images if image.is_primary), None)
    return (primary or images[0]).image or None


def _render(file):
    from PIL import Image, ImageOps

    with file.open('rb') as handle:
        picture = Image.open(handle)
        picture = ImageOps.exif_transpose(picture)
        if picture.mode in ('RGBA', 'LA', 'P'):
            picture = picture.convert('RGBA')
            canvas = Image.new('RGB', picture.size, (255, 255, 255))
            canvas.paste(picture, mask=picture.split()[-1])
            picture = canvas
        else:
            picture = picture.convert('RGB')
    # The whole product stays in view, padded with white like the catalog photos.
    square = ImageOps.pad(picture, (SIZE, SIZE), method=Image.LANCZOS, color=(255, 255, 255))
    for quality in (84, 74, 64):
        buffer = io.BytesIO()
        square.save(buffer, format='JPEG', quality=quality, optimize=True, progressive=True)
        if buffer.tell() <= MAX_BYTES:
            break
    return buffer.getvalue()


def product_thumbnail(product):
    """Storage name of a square JPEG for ``product``, made once per source photo. None without a photo."""
    if product is None:
        return None
    source = _source(product)
    if not source:
        return None
    digest = hashlib.sha1(source.name.encode()).hexdigest()[:12]
    name = f'notifications/products/{product.pk}-{digest}.jpg'
    if default_storage.exists(name):
        return name
    try:
        return default_storage.save(name, ContentFile(_render(source)))
    except Exception:
        logger.warning('Could not make a notification photo for product %s', product.pk, exc_info=True)
        return None


def image_url(name):
    return absolute_media(default_storage.url(name)) if name else ''
