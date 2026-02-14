import os
import sys
import tempfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from chesser.models import Variation
from chesser.serializers import bulk_export_json_chunks


class Command(BaseCommand):
    help = "Bulk export all variations as a JSON list (ordered by ID)."  # noqa: A003

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
            self._write_chunks(sys.stdout, qs)
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
                self._write_chunks(out, qs)

            os.replace(tmp_name, out_path)

        except Exception as exc:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise CommandError(str(exc)) from exc

    def _write_chunks(self, out, qs):
        for chunk in bulk_export_json_chunks(qs):
            out.write(chunk)
