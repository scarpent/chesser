import json
import os

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware

from chesser.models import Course, Move, Variation

# 23124550, 17709033, 21090319, 17709033 EG


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

        self.import_variation(import_data)

    def import_variation(self, import_data):
        course = Course.objects.get(color=import_data["color"])
        chapter, created = course.chapter_set.get_or_create(
            course=course, title=import_data["chapter_title"]
        )
        label = "Creating" if created else "Getting"
        self.stdout.write(f"{label} chapter: {chapter}")
        variation, created = Variation.objects.get_or_create(
            course=course,
            chapter=chapter,
            move_sequence=import_data["mainline"],
        )
        label = "Creating" if created else "Updating"
        self.stdout.write(f"{label} variation: {variation.mainline_moves}")

        variation.source = import_data["source"]
        variation.title = import_data["variation_title"]
        variation.start = import_data["start_move"]
        variation.level = import_data["level"]
        next_review = parse_datetime(import_data["next_review"])
        if next_review is not None:
            variation.next_review = make_aware(next_review)
        else:
            self.stderr.write("Invalid date format for next_review")

        variation.save()

        for idx, move_import in enumerate(import_data["moves"]):
            move, created = Move.objects.get_or_create(
                variation=variation,
                move_num=move_import["move_num"],
                sequence=idx,
            )
            move.move_num = move_import["move_num"]
            move.san = move_import["san"]
            move.annotation = move_import["annotation"]
            move.text = move_import["text"]
            # move.alt = move_import["alt"]
            # move.alt_fail = move_import["alt_fail"]
            # move.shapes = move_import["shapes"]

            move.save()
