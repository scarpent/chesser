import json
import os

from django.core.management.base import BaseCommand

from chesser import importer


class Command(BaseCommand):
    help = "Import variation into the database"  # noqa: A003

    def add_arguments(self, parser):
        parser.add_argument(
            "variation_id", type=int, help="ID of the variation to import"
        )

    def handle(self, *args, **kwargs):
        variation_id = kwargs["variation_id"]

        # get shared project root with schess
        project_root = os.path.abspath(os.path.join(__file__, "../../../../.."))
        import_path = os.path.join(project_root, "chess", "chesser", "import")
        file_path = os.path.join(import_path, f"{variation_id}.json")

        self.stdout.write(f"Importing variation with ID {variation_id}:")
        self.stdout.write(file_path)

        if not os.path.exists(file_path):
            self.stderr.write("File does not exist")
            return

        with open(file_path, "r") as file:
            import_data = json.load(file)

        importer.import_variation(import_data)
