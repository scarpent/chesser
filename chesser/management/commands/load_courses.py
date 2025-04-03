from django.core.management.base import BaseCommand
from django.utils import timezone

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

    def create_variation(
        self, title, chapter, start_move, moves=None, mainline_moves_str=None
    ):
        variation, _ = Variation.objects.get_or_create(
            mainline_moves_str=mainline_moves_str,
            course=chapter.course,
            defaults={
                "title": title,
                "chapter": chapter,
                "start_move": start_move,
                "created_at": timezone.now(),
            },
        )
        self.print_object_info(variation)
        if moves:
            sequence = -1
            for move in moves:
                sequence += 1
                move_defaults = {
                    key: value
                    for key, value in move.items()
                    if key not in ["sequence", "variation"]
                }
                move["sequence"] = sequence
                move["variation"] = variation
                Move.objects.get_or_create(
                    sequence=sequence,
                    variation=variation,
                    defaults=move_defaults,
                )
            assert variation.mainline_moves == mainline_moves_str, (
                f"Mainline moves do not match: {variation.mainline_moves} != "
                f"{mainline_moves_str}"
            )
            self.stdout.write(f"    {variation.mainline_moves}")

        return variation

    def handle(self, *args, **kwargs):

        white_course = self.create_course("White", "white")
        black_course = self.create_course("Black", "black")

        white_e4_sundry = self.create_chapter("1.e4 Sundry", white_course)
        white_e4_e5_misc = self.create_chapter("1.e4 e5 Misc", white_course)
        black_bishops_game = self.create_chapter("Bishop's Game", black_course)
        black_others = self.create_chapter("Others", black_course)
        black_italian = self.create_chapter("Italian 4.Ng5", black_course)

        moves = [
            {
                "move_num": 1,
                "san": "e4",
                "shapes": '[{"orig":"g1","dest":"f3","brush":"green"},{"orig":"d5","brush":"green"},{"orig":"f5","brush":"green"},{"orig":"d4","brush":"green"},{"orig":"e5","brush":"green"}]',  # noqa: E501
            },
            {
                "move_num": 1,
                "san": "Nc6",
                "text": "{The Nimzovich Defence. It is not that bad if you use it just as a transpositional tool to reach 1 e4 e5 positions - the independent lines, however, are not that reliable for Black, or just downright bad.}",  # noqa: E501
            },
            {
                "move_num": 2,
                "san": "Nf3",
                "alt": "Nc3",
                "alt_fail": "d4, Bb5",
                "text": "{Instead, 2.d4 is good as well. But 2.Nf3 is logical and easier to handle.} (2.d4 h5)",  # noqa: E501
            },
            {
                "move_num": 2,
                "san": "d5",
                "text": "{Scandi style play - it is very questionable though.}",
            },
            {"move_num": 3, "san": "exd5"},
            {"move_num": 3, "san": "Qxd5"},
            {"move_num": 4, "san": "Nc3"},
            {"move_num": 4, "san": "Qh5"},
            {
                "move_num": 5,
                "san": "Nb5",
                "text": "{Quite an embarrassing moment for Black - now ...Kd8 is the only move and it is not pretty.}",  # noqa: E501
            },
        ]
        mainline_moves = "1.e4 Nc6 2.Nf3 d5 3.exd5 Qxd5 4.Nc3 Qh5 5.Nb5"
        self.create_variation(
            "Nimzowitsch 1...Nc6",
            white_e4_sundry,
            2,
            moves=moves,
            mainline_moves_str=mainline_moves,
        )

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
        mainline_moves = "1.e4 e5 2.Nf3 Nf6 3.Nc3 d6 4.d4 exd4 5.Nxd4"
        self.create_variation(
            "Petroff Transposition to Philidor",
            white_e4_e5_misc,
            3,
            moves=moves,
            mainline_moves_str=mainline_moves,
        )

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
        mainline_moves = "1.e4 e5 2.Bc4 Nf6 3.Nc3 Nc6 4.d3 Na5"
        self.create_variation(
            "Bishop's Opening - Vienna Hybrid",
            black_bishops_game,
            3,
            moves=moves,
            mainline_moves_str=mainline_moves,
        )

        moves = [
            {"move_num": 1, "san": "b4"},
            {
                "move_num": 1,
                "san": "e5",
                "alt": "",
                "alt_fail": "d5, Nf6, e6, c6",
            },
            {"move_num": 2, "san": "Bb2"},
            {"move_num": 2, "san": "Bxb4"},
            {"move_num": 3, "san": "Bxe5"},
            {"move_num": 3, "san": "Nf6"},
        ]
        mainline_moves = "1.b4 e5 2.Bb2 Bxb4 3.Bxe5 Nf6"
        self.create_variation(
            "Orangutan / Polish",
            black_others,
            1,
            moves=moves,
            mainline_moves_str=mainline_moves,
        )

        moves = [
            {"move_num": 1, "san": "e4"},
            {"move_num": 1, "san": "e5"},
            {"move_num": 2, "san": "Nf3"},
            {"move_num": 2, "san": "Nc6"},
            {"move_num": 3, "san": "Bc4"},
            {"move_num": 3, "san": "Nf6"},
            {"move_num": 4, "san": "Ng5"},
            {"move_num": 4, "san": "d5"},
            {"move_num": 5, "san": "exd5"},
            {"move_num": 5, "san": "Na5"},
            {"move_num": 6, "san": "Bb5+"},
            {"move_num": 6, "san": "c6"},
            {"move_num": 7, "san": "dxc6"},
            {"move_num": 7, "san": "bxc6"},
        ]
        mainline_moves = (
            "1.e4 e5 2.Nf3 Nc6 3.Bc4 Nf6 4.Ng5 d5 5.exd5 Na5 6.Bb5+ c6 7.dxc6 bxc6"
        )
        self.create_variation(
            "Italian 4.Ng5 (Intro)",
            black_italian,
            3,
            moves=moves,
            mainline_moves_str=mainline_moves,
        )
