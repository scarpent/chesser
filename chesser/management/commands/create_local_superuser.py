from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


# TODO: goes away before we ever go live 🚀💥
class Command(BaseCommand):
    help = (  # noqa: A003
        "Create a superuser with predefined username and "
        "password for local dev, if the database is SQLite"
    )

    def handle(self, *args, **kwargs):
        if "sqlite3" not in settings.DATABASES["default"]["ENGINE"]:
            self.stdout.write(
                self.style.WARNING("superuser creation only for local dev with sqlite")
            )
            return
        if not User.objects.filter(username="root").exists():
            User.objects.create_superuser(
                username="root",
                password="root",
                email="root@example.com",
            )
            self.stdout.write(self.style.SUCCESS("created root superuser"))
        else:
            self.stdout.write(self.style.WARNING("root superuser already exists"))
