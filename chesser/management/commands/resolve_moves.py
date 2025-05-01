import chess
from django.core.management.base import BaseCommand

from chesser.models import Variation
from chesser.serializers import (
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

    def handle(self, *args, **options):
        variation_id = options.get("variation")
        stats = self.move_resolver_runner(variation_id=variation_id)
        stats.print_stats()
        return 0

    def move_resolver_runner(self, variation_id=None):
        if variation_id:
            variations = Variation.objects.filter(id=variation_id)
        else:
            variations = Variation.objects.all()

        stats = ResolveStats()

        for variation in variations.iterator():
            board = chess.Board()
            for move in variation.moves.iterator():
                board.push_san(move.san)  # Mainline moves better be valid
                if not move.text:
                    continue

                chunks = extract_ordered_chunks(move.text)
                parsed_blocks = get_parsed_blocks_first_pass(chunks)
                path_finder = PathFinder(
                    parsed_blocks,
                    move,
                    board.copy(),
                    stats,
                )
                path_finder.resolve_moves()

        return stats
