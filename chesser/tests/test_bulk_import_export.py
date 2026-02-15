# chesser/tests/test_bulk_import_export.py

import json
from pathlib import Path

import pytest
from django.core.management import call_command


def _normalize_variation_dict(v: dict) -> dict:
    """
    Normalize a variation dict for stable import/export comparisons.

    Now that created_at is honored on import, we KEEP created_at.
    Variation IDs are expected to round-trip too (sample file is sequential).
    """
    out = dict(v)

    # Normalize common scalar shapes/types (without dropping fields)
    if "variation_id" in out and out["variation_id"] is not None:
        out["variation_id"] = int(out["variation_id"])

    out["is_intro"] = bool(out.get("is_intro", False))
    out["archived"] = bool(out.get("archived", False))
    out["start_move"] = int(out.get("start_move") or 0)
    out["level"] = int(out.get("level") or 0)

    # Preserve created_at exactly (string compare), but strip whitespace if any
    if "created_at" in out and out["created_at"] is not None:
        out["created_at"] = str(out["created_at"]).strip()

    # Normalize a few strings (safe if import/export are already clean)
    out["variation_title"] = (out.get("variation_title") or "").strip()
    out["chapter_title"] = (out.get("chapter_title") or "").strip()
    out["color"] = (out.get("color") or "").strip().lower()
    out["mainline"] = (out.get("mainline") or "").strip()

    # Normalize move dicts (defaults, stable types)
    moves = []
    for m in out.get("moves") or []:
        md = dict(m)
        md["move_num"] = int(md.get("move_num") or 0)
        md["san"] = (md.get("san") or "").strip()
        md["annotation"] = (md.get("annotation") or "").strip()
        md["text"] = (md.get("text") or "").replace("\r\n", "\n")

        # Might be list or string depending on serializer choices; normalize lightly
        md["alt"] = md.get("alt") or ""
        md["alt_fail"] = md.get("alt_fail") or ""

        md["shapes"] = md.get("shapes") or []
        moves.append(md)
    out["moves"] = moves

    return out


def _sort_key(v: dict) -> tuple:
    # Prefer variation_id if present, since we expect it to be stable, initially
    vid = v.get("variation_id")
    if vid is not None:
        return (int(vid),)
    return (
        v.get("color", ""),
        v.get("chapter_title", ""),
        v.get("mainline", ""),
        v.get("variation_title", ""),
        v.get("start_move", 0),
    )


@pytest.mark.django_db
def test_bulk_import_then_bulk_export_roundtrip_sample_repertoire(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]

    sample_path = repo_root / "examples" / "sample_repertoire.json"
    assert sample_path.exists(), f"Missing sample file: {sample_path}"

    export_path = tmp_path / "export.json"

    call_command("bulk_import", file=str(sample_path))
    call_command("bulk_export", file=str(export_path))

    original = json.loads(sample_path.read_text(encoding="utf-8"))
    exported = json.loads(export_path.read_text(encoding="utf-8"))

    # Basic sanity
    assert len(exported) == len(original)

    original_norm = sorted(
        (_normalize_variation_dict(v) for v in original), key=_sort_key
    )
    exported_norm = sorted(
        (_normalize_variation_dict(v) for v in exported), key=_sort_key
    )

    assert original_norm == exported_norm
