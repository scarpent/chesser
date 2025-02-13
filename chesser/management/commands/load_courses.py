from django.core.management.base import BaseCommand

from chesser.models import Chapter, Course, Move, Variation


class Command(BaseCommand):
    help = "Load courses and variations into the database"  # noqa: A003

    def print_object_info(self, obj):
        self.stdout.write(f"{obj.title} <{obj.id}>")

    def create_course(self, title, color):
        course, _ = Course.objects.get_or_create(title=title, color=color)
        self.print_object_info(course)
        return course

    def create_chapter(self, title, course):
        chapter, _ = Chapter.objects.get_or_create(title=title, course=course)
        self.print_object_info(chapter)
        return chapter

    def create_variation(self, title, chapter, start, moves=None):
        variation, _ = Variation.objects.get_or_create(
            title=title, chapter=chapter, start=start
        )
        self.print_object_info(variation)
        if moves:
            sequence = -1
            for move in moves:
                sequence += 1
                move["sequence"] = sequence
                move["variation"] = variation
                move_obj, _ = Move.objects.get_or_create(**move)
            self.stdout.write(f"    {variation.mainline_moves}")
        return variation

    def handle(self, *args, **kwargs):

        white_course = self.create_course("White", "white")
        black_course = self.create_course("Black", "black")

        white_e4_sundry = self.create_chapter("1.e4 Sundry", white_course)
        moves = [
            {"move_num": 1, "san": "e4"},
            {"move_num": 1, "san": "Nc6"},
            {"move_num": 2, "san": "Nf3", "alt": ["Nc3"], "alt_fail": ["d4", "Bb5"]},
            {"move_num": 2, "san": "d5"},
            {"move_num": 3, "san": "exd5"},
            {"move_num": 3, "san": "Qxd5"},
            {"move_num": 4, "san": "Nc3"},
            {"move_num": 4, "san": "Qh5"},
            {"move_num": 5, "san": "Nb5"},
        ]
        self.create_variation("Nimzowitsch 1...Nc6", white_e4_sundry, 2, moves)

        white_e4_e5_misc = self.create_chapter("1.e4 e5 Misc", white_course)
        moves = [
            {"move_num": 1, "san": "e4"},
            {"move_num": 1, "san": "e5"},
            {"move_num": 2, "san": "Nf3"},
            {"move_num": 2, "san": "Nf6"},
            {"move_num": 3, "san": "Nc3"},
            {"move_num": 3, "san": "d6"},
            {"move_num": 4, "san": "d4"},
            {"move_num": 4, "san": "exd4"},
            {"move_num": 5, "san": "Nxd4"},
        ]
        self.create_variation(
            "Petroff Transposition to Philidor", white_e4_e5_misc, 3, moves
        )

        black_bishops_game = self.create_chapter("Bishop's Game", black_course)
        moves = [
            {"move_num": 1, "san": "e4"},
            {"move_num": 1, "san": "e5"},
            {"move_num": 2, "san": "Bc4"},
            {"move_num": 2, "san": "Nf6"},
            {"move_num": 3, "san": "Nc3"},
            {"move_num": 3, "san": "Nc6"},
            {"move_num": 4, "san": "d3"},
            {"move_num": 4, "san": "Na5"},
        ]
        self.create_variation("Bishop's Game", black_bishops_game, 3, moves)

        black_others = self.create_chapter("Others", black_course)
        moves = [
            {"move_num": 1, "san": "b4"},
            {
                "move_num": 1,
                "san": "e5",
                "alt": [],
                "alt_fail": ["d5", "Nf6", "e6", "c6"],
            },
            {"move_num": 2, "san": "Bb2"},
            {"move_num": 2, "san": "Bxb4"},
            {"move_num": 3, "san": "Bxe5"},
            {"move_num": 3, "san": "Nf6"},
        ]
        self.create_variation("Orangutan / Polish", black_others, 1, moves)
