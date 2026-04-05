from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import List

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from chesser.models import Variation

# ---------------------------------------------------------------------
# Constants – tweak here, not in logic
# ---------------------------------------------------------------------

SLOT_HOURS = [7, 17]  # 07:00 and 17:00 local
TARGET_LEVEL = 8

# ---------------------------------------------------------------------


def confirm_or_exit(
    *,
    prompt: str,
    assume_yes: bool = False,
):
    """
    Prompt for confirmation. Default is No.
    """
    if assume_yes:
        return

    answer = input(f"{prompt} [y/N]: ").strip().lower()
    if answer not in {"y", "yes"}:
        raise SystemExit("Aborted.")


def slot_schedule(start_dt: datetime, count: int) -> List[datetime]:
    """
    Produce `count` datetimes using SLOT_HOURS slots per day, starting at
    the first slot on or after start_dt.
    """
    out: List[datetime] = []
    date = start_dt.date()
    slot_idx = next(
        (i for i, h in enumerate(SLOT_HOURS) if h >= start_dt.hour),
        None,
    )
    if slot_idx is None:
        date += timedelta(days=1)
        slot_idx = 0

    while len(out) < count:
        if date.weekday() == 5:  # Saturday — skip to Sunday
            date += timedelta(days=1)
            slot_idx = 0
            continue
        out.append(
            datetime.combine(
                date, time(SLOT_HOURS[slot_idx], 0, 0), tzinfo=start_dt.tzinfo
            )
        )
        slot_idx += 1
        if slot_idx >= len(SLOT_HOURS):
            slot_idx = 0
            date += timedelta(days=1)

    return out


class Command(BaseCommand):
    help = (  # noqa: A003
        "Reschedule level-8 variations: "
        "preserve current order, spread two per day at 07:00 and 17:00 local."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print planned changes without writing to DB.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        dry_run = opts["dry_run"]
        tz = timezone.get_current_timezone()

        qs = (
            Variation.objects.active()
            .filter(level=TARGET_LEVEL)
            .order_by("next_review")
            .only("id", "level", "next_review", "title")
        )

        variations = list(qs)
        count = len(variations)

        slots_str = " and ".join(f"{h:02d}:00" for h in SLOT_HOURS)
        self.stdout.write(
            f"Found {count} active level-{TARGET_LEVEL} variations.\n"
            f"Will schedule {len(SLOT_HOURS)} per day at {slots_str} starting today.\n"
        )

        if not count:
            return

        confirm_or_exit(
            prompt="Are you sure you want to continue?",
            assume_yes=dry_run,
        )

        start_dt = timezone.make_aware(
            datetime.combine(timezone.localdate(), time(SLOT_HOURS[0], 0, 0)),
            tz,
        )

        dates = slot_schedule(start_dt, count)

        for v, new_dt in zip(variations, dates):
            old_dt = v.next_review
            if dry_run:
                self.stdout.write(f"[DRY] #{v.id:<5} {old_dt} → {new_dt}  ({v.title})")
                continue

            v.next_review = new_dt
            v.save(update_fields=["next_review"])

        self.stdout.write(f"Done. Updated {count} variations. Dry-run={dry_run}.")
