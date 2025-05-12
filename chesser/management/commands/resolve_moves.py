from datetime import datetime

import chess
from django.core.management.base import BaseCommand

from chesser.models import Move, Variation
from chesser.move_resolver import (
    PathFinder,
    ResolveStats,
    extract_ordered_chunks,
    get_parsed_blocks_first_pass,
)


class Command(BaseCommand):
    help = "Gather basic subvar and fenseq parsing statistics."  # noqa: A003

    def add_arguments(self, parser):
        parser.add_argument(
            "-e",
            "--variation",
            type=int,
            help="Specific Variation ID to test (optional).",
        )
        parser.add_argument(
            "-m",
            "--move",
            type=int,
            help="Specific Move ID to test (optional).",
        )

    def handle(self, *args, **options):
        variation_id = options.get("variation")
        move_id = options.get("move")
        stats = self.move_resolver_runner(variation_id=variation_id, move_id=move_id)
        stats.print_stats()
        return 0

    def move_resolver_runner(self, variation_id=None, move_id=None):
        show_progress = False
        if move_id:
            move = Move.objects.filter(id=move_id).first()
            if move:
                variation_id = move.variation.id
        if variation_id:
            variations = Variation.objects.filter(id=variation_id)
        else:
            variations = Variation.objects.all().order_by("id")
            show_progress = True

        stats = ResolveStats()

        start = datetime.now()

        # have to push all the mainline moves to maintain the board state
        for variation in variations.iterator():
            if show_progress:
                print(f"🏵️  Variation {variation.id}", end="\r")
            board = chess.Board()
            # print(f"🏵️  Variation {variation}")
            for move in variation.moves.iterator():
                board.push_san(move.san)  # Mainline moves better be valid
                if not move.text:
                    continue
                elif move_id and move.id != move_id:
                    continue

                chunks = extract_ordered_chunks(move.text)
                parsed_blocks = get_parsed_blocks_first_pass(chunks)
                path_finder = PathFinder(
                    parsed_blocks,
                    move.id,
                    move.move_verbose,
                    board.copy(),
                    stats,
                )
                resolved_moves = path_finder.resolve_moves()

                # in general we're trying to keep all resolver messages
                # attached to block logs so we can print out here and
                # read the whole story in sequence

                if variation_id and resolved_moves:
                    print(f"🪵 Block Log, Mainline: {move.move_verbose}")
                    for resolved_move in resolved_moves:
                        resolved_move.debug()
                    print(f"🪦 End {move.move_verbose}")

        end = datetime.now()
        print(f"\n➡️  Start: {start.isoformat()}")
        print(f"⏱️  Duration: {(end - start).total_seconds():.1f} seconds")

        return stats
