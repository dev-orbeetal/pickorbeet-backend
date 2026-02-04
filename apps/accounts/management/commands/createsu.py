from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decouple import config

User = get_user_model()

class Command(BaseCommand):
    help = 'Create superuser from environment variables'

    def handle(self, *args, **options):
        email = config('ADMIN_EMAIL', default='')
        password = config('ADMIN_PASSWORD', default='')
        first_name = config('ADMIN_FIRST_NAME', default='Admin')
        last_name = config('ADMIN_LAST_NAME', default='User')

        if not email or not password:
            self.stdout.write(
                self.style.ERROR('ADMIN_EMAIL and ADMIN_PASSWORD must be set in .env file')
            )
            return

        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            if not user.is_superuser:
                user.is_superuser = True
                user.is_staff = True
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f'Updated existing user {email} to superuser')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Superuser {email} already exists')
                )
            return

        User.objects.create_superuser(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created superuser: {email}')
        )
