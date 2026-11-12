from django.apps import AppConfig


class CareersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.careers'
    verbose_name = 'Careers'

    def ready(self):
        from django.db.models.signals import pre_delete

        from .models import CareerApplication, delete_application_files

        pre_delete.connect(
            delete_application_files,
            sender=CareerApplication,
            dispatch_uid='careers.delete_application_files',
        )
