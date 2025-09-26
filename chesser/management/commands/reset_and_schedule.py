from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Deque, Dict, List

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from chesser.models import Variation


@dataclass
class Item:
    id: int  # noqa: A003
    chapter_id: int
    chapter_title: str
    color: str
    title: str
    mainline_moves_str: str | None


def _fetch_ordered_queue(color: str) -> Deque[Item]:
    """
    Build a per-color queue sorted by chapter title asc, then mainline text length asc.
    Color is stored on Chapter.
    """
    qs = (
        Variation.objects.select_related("chapter")
        .only("id", "title", "chapter_id", "mainline_moves_str", "chapter__title")
        .filter(chapter__isnull=False, chapter__color=color)
    )

    rows: List[Item] = []
    for v in qs:
        rows.append(
            Item(
                id=v.id,
                chapter_id=v.chapter_id,
                chapter_title=v.chapter.title,
                color=color,
                title=v.title,
                mainline_moves_str=v.mainline_moves_str or "",
            )
        )

    rows.sort(key=lambda r: (r.chapter_title.lower(), len(r.mainline_moves_str), r.id))

    # Round-robin interleave by chapter to avoid draining one chapter at a time
    by_ch: Dict[int, Deque[Item]] = defaultdict(deque)
    for it in rows:
        by_ch[it.chapter_id].append(it)

    interleaved: Deque[Item] = deque()
    chapter_ids = sorted(
        by_ch.keys(), key=lambda ch: rows[0].chapter_title.lower() if rows else ""
    )
    chapter_cycle = deque(chapter_ids)

    while by_ch and chapter_cycle:
        ch = chapter_cycle.popleft()
        q = by_ch.get(ch)
        if not q:
            by_ch.pop(ch, None)
            continue
        interleaved.append(q.popleft())
        if q:
            chapter_cycle.append(ch)
        else:
            by_ch.pop(ch, None)

    return interleaved


def compute_start_dt(start_date_str: str | None, hour: int) -> datetime:
    """
    Always build a naive local datetime and then make it aware.
    """
    tz = timezone.get_current_timezone()
    if start_date_str:
        y, m, d = map(int, start_date_str.split("-"))
        local_naive = datetime.combine(date(y, m, d), time(hour, 0, 0))
    else:
        # Use *local* calendar date, then make naive HH:00
        today_local = timezone.localdate()
        local_naive = datetime.combine(today_local, time(hour, 0, 0))

    # Ensure it's naive before we make it aware
    assert timezone.is_naive(local_naive), "expected naive datetime"
    return timezone.make_aware(local_naive, tz)


def _evenly_spread_extra(total_days: int, extra_count: int) -> List[bool]:
    """
    For i in [0..total_days-1], mark day i as True if it should receive an "extra Black"
    (i.e., 3B/1W instead of 2B/2W). This spreads 'extra_count' days evenly.
    Uses a balanced rounding / largest-remainder style rule.
    """
    flags = []
    prev = 0
    for i in range(1, total_days + 1):
        # target extras up to this day:
        target = (i * extra_count) // total_days
        flags.append(target > prev)  # True when we increment
        prev = target
    return flags


class Command(BaseCommand):
    help = "Reset all levels to 0 and pre-schedule next_review 4/day, balancing colors so both finish together."  # noqa: E501, A003

    def add_arguments(self, parser):
        parser.add_argument(
            "--start-date",
            type=str,
            default=None,
            help="YYYY-MM-DD (local) start date for scheduling. Default: today.",
        )
        parser.add_argument(
            "--hour",
            type=int,
            default=9,
            help="Hour of day (local) to set next_review times (default 9).",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Do everything except write changes."
        )
        parser.add_argument("--verbose", action="store_true", help="Print daily picks.")

    @transaction.atomic
    def handle(self, *args, **opts):
        # Config
        per_day = 4
        # actual counts (we’ll also compute from DB in case they changed)
        # Example: White 556, Black 697
        hour = opts["hour"]
        dry_run = opts["dry_run"]
        verbose = opts["verbose"]

        start_dt = compute_start_dt(opts["start_date"], opts["hour"])

        # Build queues
        whites = _fetch_ordered_queue("white")
        blacks = _fetch_ordered_queue("black")

        nW, nB = len(whites), len(blacks)
        total = nW + nB
        if total == 0:
            self.stdout.write("No variations found.")
            return

        full_days = total // per_day  # number of 4-item days
        leftover = total % per_day  # last day items (0..3)

        # Base plan: 2W + 2B per full day.
        # Required extra Blacks to hit total blacks:
        base_B = 2 * full_days
        extra_B_days = max(0, nB - base_B)
        if extra_B_days > full_days:
            # If we ever change per_day or ratio, handle impossibility
            raise SystemExit(
                f"""Impossible to schedule: need {extra_B_days} extra-Black days
                across only {full_days} full days."""
            )

        extra_black_flags = _evenly_spread_extra(full_days, extra_B_days)

        # For the leftover day, choose the remaining color(s)
        # With your numbers this will be 1 White.
        # In general, we’ll compute after consuming the full days.

        # 1) Reset levels for all first (so partial writes don’t leave mixed states)
        if not dry_run:
            Variation.objects.all().update(level=0)

        # 2) Walk the calendar and assign next_review
        day = 0

        # Helpers to pop N items from a deque
        def pop_n(q: Deque[Item], n: int) -> List[Item]:
            picked = []
            for _ in range(n):
                if not q:
                    break
                picked.append(q.popleft())
            return picked

        # Full 4-item days
        cur_date = start_dt
        for flag3B in extra_black_flags:
            want_B = 3 if flag3B else 2
            want_W = per_day - want_B
            take_B = pop_n(blacks, want_B)
            take_W = pop_n(whites, want_W)

            # If one color ran short unexpectedly, fill from the other color
            short_B = want_B - len(take_B)
            short_W = want_W - len(take_W)
            if short_B > 0:
                take_W += pop_n(whites, short_B)
            if short_W > 0:
                take_B += pop_n(blacks, short_W)

            todays = (
                take_B + take_W
            )  # order doesn’t matter for storage; it’s a “due today” set
            if verbose:
                w_ids = [str(it.id) for it in take_W]
                b_ids = [str(it.id) for it in take_B]
                self.stdout.write(
                    f"{cur_date.date()}  B:{len(b_ids)} [{', '.join(b_ids)}]  "
                    f"W:{len(w_ids)} [{', '.join(w_ids)}]"
                )

            if not dry_run:
                ids = [it.id for it in todays]
                Variation.objects.filter(id__in=ids).update(
                    next_review=cur_date, level=0
                )

            day += 1
            cur_date = start_dt + timedelta(days=day)

        # Leftover day (0..3)
        remaining = list(blacks) + list(whites)
        if leftover and remaining:
            # Prefer to keep color proportions: compute remaining counts
            rB, rW = len(blacks), len(whites)
            # Greedy: fill leftover slots choosing whichever color remains larger
            picks: List[Item] = []
            for _ in range(leftover):
                color_to_take = "Black" if rB > rW else "White"
                if color_to_take == "Black" and blacks:
                    picks.append(blacks.popleft())
                    rB -= 1
                elif color_to_take == "White" and whites:
                    picks.append(whites.popleft())
                    rW -= 1
                elif blacks:
                    picks.append(blacks.popleft())
                    rB -= 1
                elif whites:
                    picks.append(whites.popleft())
                    rW -= 1
                else:
                    break

            if verbose:
                ids = [str(it.id) for it in picks]
                self.stdout.write(
                    f"{cur_date.date()}  leftover:{len(ids)} [{', '.join(ids)}]"
                )

            if not dry_run and picks:
                Variation.objects.filter(id__in=[it.id for it in picks]).update(
                    next_review=cur_date, level=0
                )

        # Summary
        self.stdout.write(
            f"Planned {full_days} full days (4/day) + {leftover} on final day. "
            f"Extra-Black days: {extra_B_days}. "
            f"Start date {start_dt.date()} @ {hour:02d}:00 local. Dry-run={dry_run}."
        )
