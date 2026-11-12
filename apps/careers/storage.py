import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateMediaStorage(FileSystemStorage):
    """Files outside MEDIA_ROOT. Public /media/ never serves them."""

    def __init__(self):
        super().__init__(base_url=None)

    @property
    def location(self):
        root = os.path.abspath(str(settings.PRIVATE_MEDIA_ROOT))
        os.makedirs(root, exist_ok=True)
        return root

    def url(self, name):
        raise ValueError('This file is not publicly served.')


private_storage = PrivateMediaStorage()
