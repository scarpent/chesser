from django.core.management.base import BaseCommand

from chesser.models import Chapter, Course, Move, Variation

WHITE = 1
BLACK = 2


class Command(BaseCommand):
    help = "Load course metadata into the database"  # noqa: A003

    def handle(self, *args, **kwargs):
        courses = [
            {"course_id": WHITE, "title": "My White", "color": "white"},
            {"course_id": BLACK, "title": "My Black", "color": "black"},
        ]

        chapters = [
            {"chapter_id": 1, "title": "1.e4 Sundry", "course_id": WHITE},
            {"chapter_id": 2, "title": "1.e4 e5 Misc", "course_id": WHITE},
            {"chapter_id": 101, "title": "1.e4 e5 Misc", "course_id": BLACK},
            {"chapter_id": 102, "title": "Bishop's Game", "course_id": BLACK},
        ]

        for course in courses:
            course_obj, created = Course.objects.get_or_create(**course)
            was_created = " 💾" if created else ""
            self.stdout.write(f"{course_obj.title}{was_created}")

        for chapter in chapters:
            course_id = chapter["course_id"]
            course = Course.objects.get(course_id=course_id)
            chapter["course"] = course
            chapter_obj, created = Chapter.objects.get_or_create(**chapter)
            was_created = " 💾" if created else ""
            course_and_chapter = f"{chapter_obj.course.title}: {chapter_obj.title}"
            self.stdout.write(f"{course_and_chapter}{was_created}")

        variation, created = Variation.objects.get_or_create(
            chapter=Chapter.objects.get(chapter_id=1),
            variation_id=10000,
            title="Nimzowitsch 1...Nc6",
            start_move=2,
        )

        moves = [
            {"move_id": 40000, "move_num": 1, "san": "e4"},
            {"move_id": 40001, "move_num": 1, "san": "Nc6"},
            {"move_id": 40002, "move_num": 2, "san": "Nf3"},
            {"move_id": 40003, "move_num": 2, "san": "d5"},
            {"move_id": 40004, "move_num": 3, "san": "exd5"},
            {"move_id": 40005, "move_num": 3, "san": "Qxd5"},
            {"move_id": 40006, "move_num": 4, "san": "Nc3"},
            {"move_id": 40007, "move_num": 4, "san": "Qh5"},
            {"move_id": 40008, "move_num": 5, "san": "Nb5"},
        ]
        for move in moves:
            move["variation"] = variation
            move_obj, created = Move.objects.get_or_create(**move)
            was_created = " 💾" if created else ""
            course = variation.chapter.course.title
            chapter = variation.chapter.title
            title = variation.title
            self.stdout.write(
                f"{course}: {chapter}: {title} "
                f"{move_obj.move_num} {move_obj.san}{was_created}"
            )
