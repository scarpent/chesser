import json
import os
import sys
import tempfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from chesser.models import Variation
from chesser.serializers import serialize_variation_to_import_format


def _write_iterencoded_with_line_indent(out, chunks, prefix="    "):
    """
    Write iterencoded JSON chunks, adding `prefix` only at the start of each line.
    This avoids inserting spaces mid-token (iterencode yields small chunks).
    """
    at_line_start = True

    for chunk in chunks:
        if not chunk:
            continue

        parts = chunk.split("\n")

        for i, part in enumerate(parts):
            if i > 0:
                out.write("\n")
                at_line_start = True

            if part:
                if at_line_start:
                    out.write(prefix)
                    at_line_start = False
                out.write(part)


class Command(BaseCommand):
    help = "Bulk export all variations as a JSON list (ordered by ID)."  # noqa: A003

    CHUNK_SIZE = 2000

    def add_arguments(self, parser):
        parser.add_argument(
            "-f",
            "--file",
            type=str,
            default="/tmp/export.json",
            help="Output JSON file path (default: /tmp/export.json). Use '-' for stdout.",  # noqa: E501
        )

    def handle(self, *args, **kwargs):
        file_path = kwargs["file"]

        qs = (
            Variation.objects.select_related("chapter")
            .prefetch_related("moves")
            .order_by("id")
        )

        if file_path == "-":
            count = self._write_json_list(sys.stdout, qs)
            self._report_count(count)
            return

        out_path = Path(file_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        tmp_fd, tmp_name = tempfile.mkstemp(
            prefix=f".{out_path.name}.",
            dir=str(out_path.parent),
            text=True,
        )

        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as out:
                count = self._write_json_list(out, qs)

            os.replace(tmp_name, out_path)
            self._report_count(count)

        except Exception as exc:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise CommandError(str(exc)) from exc

    def _write_json_list(self, out, qs):
        """
        Stream a JSON list and return the number of variations written.
        """
        encoder = json.JSONEncoder(indent=4, ensure_ascii=False)

        out.write("[\n")
        first = True
        count = 0

        for variation in qs.iterator(chunk_size=self.CHUNK_SIZE):
            data = serialize_variation_to_import_format(variation)

            if not first:
                out.write(",\n")
            first = False

            _write_iterencoded_with_line_indent(
                out, encoder.iterencode(data), prefix="    "
            )
            count += 1

        out.write("\n]\n")
        return count

    def _report_count(self, count):
        sys.stderr.write(f"➡️  Exported {count} variations\n")
