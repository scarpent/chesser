import json
import os

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware

from chesser.models import Course, Move, QuizResult, Variation

# 23124550 (source + text), 21090319, 17709033 EG


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

    def get_timezone_aware_datetime(self, date_string):
        if parsed_datetime := parse_datetime(date_string):
            return make_aware(parsed_datetime)
        else:
            self.stderr.write(f"Invalid format for date_string: {date_string}")

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
        variation.next_review = self.get_timezone_aware_datetime(
            import_data["next_review"]
        )

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
            move.shapes = (
                json.dumps(move_import["shapes"]) if move_import["shapes"] else ""
            )

            move.save()

        if not variation.quizresult_set.first():
            self.stdout.write("Creating QuizResult")
            quiz_result = QuizResult.objects.create(
                variation=variation, passed=True, level=variation.level
            )
            quiz_result.datetime = self.get_timezone_aware_datetime(
                import_data["last_review"]
            )
            quiz_result.save()
