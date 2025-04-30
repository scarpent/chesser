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

        self.stdout.write("\nParsing Stats Summary:\n")
        self.stdout.write(f"subvar total: {stats.subvar_total}")
        self.stdout.write(f"fenseq total: {stats.fenseq_total}")

        self.stdout.write(f"moves attempted: {stats.moves_attempted}")
        self.stdout.write(f"moves resolved: {stats.moves_resolved}")

        self.stdout.write(f"Max subvar depth: {stats.max_subvar_depth}")

        self.stdout.write(
            f"Resolved match explicit: {stats.resolved_matches_raw_explicit}"
        )
        self.stdout.write(
            f"Resolved match implicit: {stats.resolved_matches_raw_implicit}"
        )
        self.stdout.write(
            f"Resolved move distance: {dict(sorted(stats.resolved_move_distance.items()))}"  # noqa: E501
        )

        self.stdout.write(
            f"Resolved on attempt N: {dict(sorted(stats.resolved_on_attempt.items()))}"
        )
        self.stdout.write(f"Matched root san: {stats.matched_root_san}")
        self.stdout.write(f"Discarded: {stats.discarded}")
        self.stdout.write(f"Mainline siblings: {stats.mainline_siblings}")
        self.stdout.write(
            f"Mainline siblings resolved: {stats.mainline_siblings_resolved}"
        )
        self.stdout.write(
            f"First matched root but no next: {stats.first_matched_root_but_no_next}"
        )
        self.stdout.write("\n")
        if stats.failure_blocks:
            self.stdout.write(f"{len(stats.failure_blocks)} failed blocks:")
            for block in stats.failure_blocks[:10]:  # Show first 10
                self.stdout.write(f"  - {block}")

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
