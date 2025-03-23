import json
import os

from django.core.management.base import BaseCommand

from chesser import importer


class Command(BaseCommand):
    help = "Bulk import variations into the database"  # noqa: A003

    def add_arguments(self, parser):
        parser.add_argument(
            "-f",
            "--file",
            type=str,
            default="/tmp/upload.json",
            help="Path to JSON file (default: /tmp/upload.json)",
        )

    def handle(self, *args, **kwargs):
        file_path = kwargs["file"]

        self.stdout.write(f"Importing from file: {file_path}")

        if not os.path.exists(file_path):
            self.stderr.write("❌ File does not exist")
            return

        with open(file_path, "r") as file:
            try:
                import_data = json.load(file)
            except json.JSONDecodeError as e:
                self.stderr.write(f"❌ Invalid JSON: {e}")
                return

        if not isinstance(import_data, list):
            import_data = [import_data]

        total = len(import_data)
        for count, data in enumerate(import_data, start=1):
            self.stdout.write(f"📥️ {count} of {total}")
            importer.import_variation(data)
        self.stdout.write("✅ Import complete")
