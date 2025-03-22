from django.core.management.base import BaseCommand

from chesser.tasks import backup_and_upload


class Command(BaseCommand):
    help = "Backup the database and upload to S3"  # noqa: A003

    def handle(self, *args, **kwargs):
        success = backup_and_upload()
        if success:
            self.stdout.write(self.style.SUCCESS("✅ Backup uploaded successfully"))
        else:
            self.stderr.write(self.style.ERROR("❌ Backup failed"))
