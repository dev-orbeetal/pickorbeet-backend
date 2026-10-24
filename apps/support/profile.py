"""The single support profile, including the avatar shipped with the app."""
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw

from .models import SupportProfile


def avatar_png():
    """A drawn portrait so the header has a face before anyone uploads one."""
    size = 256
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((0, 0, size - 1, size - 1), fill=(237, 243, 254, 255))
    draw.ellipse((46, 28, 210, 188), fill=(42, 32, 56, 255))
    draw.ellipse((70, 78, 186, 206), fill=(224, 176, 146, 255))
    draw.rounded_rectangle((104, 186, 152, 230), radius=8, fill=(224, 176, 146, 255))
    draw.pieslice((18, 198, 238, 360), 200, 340, fill=(0, 64, 238, 255))
    draw.ellipse((96, 122, 114, 140), fill=(32, 36, 64, 255))
    draw.ellipse((142, 122, 160, 140), fill=(32, 36, 64, 255))
    draw.arc((108, 138, 148, 176), 18, 162, fill=(168, 92, 84, 255), width=4)
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def load_profile():
    """Return the one profile, filling the name, reply line, and avatar when blank."""
    profile, _created = SupportProfile.objects.get_or_create(
        pk=1,
        defaults={
            'display_name': 'Nadia Rahman',
            'reply_line': 'Usually replies in 2 min',
            'phone': getattr(settings, 'SUPPORT_PHONE', ''),
            'email': getattr(settings, 'SUPPORT_EMAIL', ''),
        },
    )
    changed = []
    if not profile.display_name:
        profile.display_name = 'Nadia Rahman'
        changed.append('display_name')
    if not profile.reply_line:
        profile.reply_line = 'Usually replies in 2 min'
        changed.append('reply_line')
    if not profile.phone:
        profile.phone = getattr(settings, 'SUPPORT_PHONE', '')
        changed.append('phone')
    if not profile.email:
        profile.email = getattr(settings, 'SUPPORT_EMAIL', '')
        changed.append('email')
    if not profile.avatar:
        profile.avatar.save('nadia.png', ContentFile(avatar_png()), save=False)
        changed.append('avatar')
    if changed:
        profile.save(update_fields=changed)
    return profile
