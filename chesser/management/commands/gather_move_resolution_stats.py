import chess
from django.core.management.base import BaseCommand

from chesser.models import Variation
from chesser.serializers import (
    ActiveFenseq,
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
        stats = self.gather_subvar_and_fenseq_basic_stats(variation_id=variation_id)

        self.stdout.write("\nParsing Stats Summary:\n")
        self.stdout.write(f"Subvar moves attempted: {stats.subvar_moves_attempted}")
        self.stdout.write(f"Subvar moves resolved: {stats.subvar_moves_resolved}")
        self.stdout.write(f"Max subvar nesting depth: {stats.max_subvar_depth}")
        self.stdout.write(f"Rebranch attempts: {stats.rebranch_attempts}")
        self.stdout.write("\n")
        self.stdout.write(f"Fenseqs total: {stats.fenseq_total}")
        self.stdout.write(f"Fenseq moves attempted: {stats.fenseq_moves_attempted}")
        self.stdout.write(f"Fenseq moves resolved: {stats.fenseq_moves_resolved}")
        self.stdout.write("\n")
        if stats.failure_blocks:
            self.stdout.write(f"{len(stats.failure_blocks)} failed blocks:")
            for block in stats.failure_blocks[:10]:  # Show first 10
                self.stdout.write(f"  - {block}")

        return 0

    def gather_subvar_and_fenseq_basic_stats(self, variation_id=None):
        """
        Gathers statistics on the resolution of moves in variations. Just see
        what works out of the box so we an get a handle on the data.
        """
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

                active_fenseq = None

                for block in parsed_blocks:
                    if block.type_ == "comment":
                        continue  # ignore comments in this validation
                    elif block.type_ == "start" and block.fen_before:
                        active_fenseq = ActiveFenseq(fen_start=block.fen_before)
                        continue
                    elif block.type_ == "end" and active_fenseq:
                        valid = active_fenseq.validate(stats)
                        if not valid:
                            print(
                                f"Invalid fenseq: var# {variation.id}, move# {move.id}"
                            )
                        active_fenseq = None
                        continue
                    elif block.type_ in ["start", "end"]:
                        # skipping regular subvar blocks for now
                        continue

                    if block.type_ != "move":
                        raise ValueError(f"Unexpected block type: {block.type_}")

                    if active_fenseq:
                        active_fenseq.blocks.append(block)
                        continue

                    # TODO: look at regular subvars

        return stats
