import logging
import uuid
from pathlib import Path

from django.db import models

from .storage import private_storage

logger = logging.getLogger(__name__)

_PICTURE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


def cv_upload_to(instance, filename):
    return f'careers/cv/{instance.pk}.pdf'


def picture_upload_to(instance, filename):
    ext = Path(filename).suffix.lower()
    if ext not in _PICTURE_EXTENSIONS:
        ext = '.jpg'
    if ext == '.jpeg':
        ext = '.jpg'
    return f'careers/photos/{instance.pk}{ext}'


class CareerApplication(models.Model):
    """A student application submitted from the public careers page."""

    STATUS_CHOICES = [
        ('new', 'New'),
        ('reviewing', 'Reviewing'),
        ('shortlisted', 'Shortlisted'),
        ('rejected', 'Rejected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    university = models.CharField(max_length=200)
    session = models.CharField(max_length=200)
    department = models.CharField(max_length=200)
    student_id = models.CharField(max_length=32)
    cv = models.FileField(storage=private_storage, upload_to=cv_upload_to)
    picture = models.ImageField(storage=private_storage, upload_to=picture_upload_to)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='new')
    admin_notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Career application'
        verbose_name_plural = 'Career applications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f'{self.name} - {self.university}'


def delete_application_files(sender, instance, **kwargs):
    """Remove the CV and portrait when the row goes away, including bulk deletes."""
    for field in (instance.cv, instance.picture):
        name = getattr(field, 'name', '') or ''
        if not name:
            continue
        try:
            field.storage.delete(name)
        except Exception:
            logger.exception('Could not delete files for career application %s', instance.pk)
