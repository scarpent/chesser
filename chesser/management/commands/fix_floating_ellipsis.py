# chesser/management/commands/fix_floating_ellipsis.py

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Tuple

from django.core.management.base import BaseCommand
from django.db import transaction

from chesser.models import Move, SharedMove

# chessable export process currently leaves some/many "floating ellipses"
# (unanchored by a move number) attached the preceding word,
# e.g. "play...Nf3" instead of "play ...Nf3". Let's fix that, and perhaps
# later we'll deal with it on import

# ---------------------------------------------------------------------
# Goal
# ---------------------------------------------------------------------
# Normalize prose/list cases like:
#   "white wants to play...Nf3"      -> "white wants to play ...Nf3"
#   "Play...g6,...Kg7,...h5-h4"      -> "Play ...g6, ...Kg7, ...h5-h4"
#
# Do NOT touch:
#   "black is thinking ...e5"        (already spaced)
#   "1...e5" / "10...Qxe5"           (move numbers)
#   "(...Nc6)"                       (leading parens structural)
#
# Strategy:
# - Only match when the character BEFORE "..." is a letter or a comma.
#   This automatically excludes move numbers (digit before ellipsis) and "(...".
# - Only apply when the next token AFTER "..." looks "chessy enough" (liberal sniff).
# - Iterate until stable (max MAX_PASSES), and report any objects that hit the max.
# ---------------------------------------------------------------------


# --- ANSI color helpers ------------------------------------------------


class C:
    RESET = "\033[0m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    CYAN = "\033[36m"
    YELLOW = "\033[33m"


def _color(s: str, code: str) -> str:
    return f"{code}{s}{C.RESET}"


# --- highlighting helpers ---------------------------------------------


def _apply_spans(
    text: str, spans: Iterable[Tuple[int, int]], *, color_code: str
) -> str:
    """
    Insert ANSI color for multiple spans (assumed non-overlapping, sorted).
    If spans overlap or are unsorted, we skip overlapping regions defensively.
    """
    spans = sorted(spans, key=lambda x: x[0])
    if not spans:
        return text

    out: List[str] = []
    cur = 0
    for a, b in spans:
        if a < cur:
            continue
        out.append(text[cur:a])
        out.append(_color(text[a:b], color_code))
        cur = b
    out.append(text[cur:])
    return "".join(out)


# --- core matching -----------------------------------------------------

MAX_PASSES = 10

# Only match prose/list: a LETTER or COMMA immediately before "..." and no space after.
# This avoids:
# - move numbers: "10...Qxe5"  (digit before dots)
# - structural parens: "(...Nc6)" ( "(" before dots )
# - already spaced: " ...e5" (space before dots, not letter/comma)
_ELLIPSIS_PROSE_RE = re.compile(r"([A-Za-z,])\.\.\.(?=\S)")


# Token extraction: scan forward from just after "..." until a delimiter.
TOKEN_DELIMS = set(" \t\r\n,.;:)]}>'\"(<[{")  # deliberately broad (HTML-ish safe)


def _next_token(text: str, pos: int) -> str:
    """
    Return the token immediately after pos, stopping at TOKEN_DELIMS.
    """
    if pos >= len(text):
        return ""

    j = pos
    while j < len(text) and text[j] not in TOKEN_DELIMS:
        j += 1

    return text[pos:j]


def _looks_like_chess_token(token: str) -> bool:
    """
    Liberal move sniff:
    - castling: O-O / O-O-O / 0-0 / 0-0-0 (optionally suffixed with +/#/?/!)
    - otherwise:
      - token prefix length >= 2
      - starts with piece letter or pawn file (KQRBN or a-h)
      - contains at least one board digit 1-8 somewhere soon
    """
    t = (token or "").strip()
    if not t:
        return False

    # Castling: accept O-O, O-O-O, 0-0, 0-0-0 with optional suffix noise.
    if t.startswith(("O-O", "0-0")):
        return True

    # Fast reject: needs 2+ chars
    if len(t) < 2:
        return False

    # Starts like a move
    if t[0] not in "KQRBNabcdefgh":
        return False

    # Require a square digit somewhere soon-ish; this filters "...something"
    # but allows "Bxg5", "h6-h7", "a5", "Nbd7" (contains 7), etc.
    window = t[:10]
    if not any(ch in "12345678" for ch in window):
        return False

    return True


@dataclass(frozen=True)
class Change:
    old: str
    new: str
    span_before: Tuple[int, int]  # span of "X..." in BEFORE text
    span_after: Tuple[int, int]  # span of "X ..." in AFTER text


def _find_and_fix(text: str) -> Tuple[str, List[Change], int]:
    """
    Apply X... -> X ... (only when chessy token follows) until stable or MAX_PASSES.

    Returns:
      (new_text, changes, passes_used)
    """
    if not text or "..." not in text:
        return text, [], 0

    current = text
    all_changes: List[Change] = []

    for pass_i in range(1, MAX_PASSES + 1):
        pending: List[Tuple[int, int, str, str]] = []  # (start, end, old, new)

        for m in _ELLIPSIS_PROSE_RE.finditer(current):
            start = m.start()  # at preceding char
            dots_start = start + 1  # at first '.'
            dots_end = dots_start + 3  # after '...'

            token = _next_token(current, dots_end)
            if not _looks_like_chess_token(token):
                continue

            prev = m.group(1)
            old = f"{prev}..."
            new = f"{prev} ..."

            # Sanity check
            if current[start : start + len(old)] != old:
                continue

            pending.append((start, start + len(old), old, new))

        if not pending:
            return current, all_changes, pass_i - 1

        # Apply right-to-left so spans remain valid
        new_text = current
        for start, end, _old, new in sorted(pending, key=lambda x: x[0], reverse=True):
            new_text = new_text[:start] + new + new_text[end:]

        # Record spans for highlighting (per pass)
        # Each replacement inserts exactly 1 char (a space).
        offset = 0
        for start, end, old, new in sorted(pending, key=lambda x: x[0]):
            span_before = (start, end)
            span_after = (start + offset, start + offset + len(new))
            all_changes.append(
                Change(old=old, new=new, span_before=span_before, span_after=span_after)
            )
            offset += 1

        current = new_text

    return current, all_changes, MAX_PASSES


# --- management command ------------------------------------------------


class Command(BaseCommand):
    help = (  # noqa: A003
        "Fix floating ellipsis in Move.text and SharedMove.text: "
        "'play...Nf3' -> 'play ...Nf3' (prose only)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually save changes. Without this flag, runs in dry-run mode.",
        )

    def handle(self, *args, **options):
        apply_changes: bool = bool(options["apply"])
        dry_run = not apply_changes

        total_objs = 0
        total_subs = 0
        total_updated = 0

        maxed_out: List[Tuple[str, int]] = []  # (label, id)

        def process_queryset(qs, label: str):
            nonlocal total_objs, total_subs, total_updated

            for obj in qs.only("id", "text").iterator(chunk_size=2000):
                total_objs += 1
                before = obj.text or ""

                after, changes, passes_used = _find_and_fix(before)
                if not changes:
                    continue

                total_subs += len(changes)

                header = f"{label} id={obj.id}"
                self.stdout.write("")
                self.stdout.write(
                    _color("== ", C.DIM)
                    + _color(header, C.CYAN + C.BOLD)
                    + _color(" ==", C.DIM)
                )

                if passes_used >= MAX_PASSES:
                    maxed_out.append((label, obj.id))
                    self.stdout.write(
                        _color(f"  !! hit MAX_PASSES ({MAX_PASSES})", C.YELLOW + C.BOLD)
                    )

                # Show each substitution
                for ch in changes:
                    self.stdout.write(
                        "  "
                        + _color(ch.old, C.RED + C.BOLD)
                        + _color("  ->  ", C.DIM)
                        + _color(ch.new, C.GREEN + C.BOLD)
                    )

                # Highlight all spans
                # (position-accurate per pass; may skip overlaps defensively)
                before_h = _apply_spans(
                    before, (c.span_before for c in changes), color_code=C.RED + C.BOLD
                )
                after_h = _apply_spans(
                    after, (c.span_after for c in changes), color_code=C.GREEN + C.BOLD
                )

                self.stdout.write("  " + _color("--- before (highlights) ---", C.DIM))
                self.stdout.write(before_h)
                self.stdout.write("  " + _color("--- after  (highlights) ---", C.DIM))
                self.stdout.write(after_h)

                if not dry_run and after != before:
                    obj.text = after
                    obj.save(update_fields=["text"])
                    total_updated += 1

        with transaction.atomic():
            process_queryset(Move.objects.exclude(text=""), "Move")
            process_queryset(SharedMove.objects.exclude(text=""), "SharedMove")

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(_color("--- summary ---", C.DIM))
        self.stdout.write(f"Dry run: {dry_run}")
        self.stdout.write(f"Objects scanned: {total_objs}")
        self.stdout.write(f"Substitutions: {total_subs}")
        self.stdout.write(f"Objects updated: {total_updated}")

        if maxed_out:
            self.stdout.write("")
            self.stdout.write(
                _color(
                    f"Objects that hit MAX_PASSES={MAX_PASSES} "
                    "(may still contain fixable cases):",
                    C.YELLOW + C.BOLD,
                )
            )
            for label, obj_id in maxed_out:
                self.stdout.write(f"  - {label} id={obj_id}")
