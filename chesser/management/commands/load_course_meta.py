from django.core.management.base import BaseCommand

from chesser.models import Chapter, Course

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
