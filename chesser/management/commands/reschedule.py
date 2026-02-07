from __future__ import annotations

from datetime import datetime, time, timedelta
from datetime import timezone as dt_timezone
from typing import List

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from chesser.models import Variation

# ---------------------------------------------------------------------
# Constants – tweak here, not in logic
# ---------------------------------------------------------------------

PER_DAY = 10
START_HOUR = 7  # 07:00 local
TARGET_LEVEL = 8

# If you already have this defined elsewhere, import it instead
END_OF_TIME = 253402300799  # 9999-12-31T23:59:59
END_OF_TIME_DT = datetime.fromtimestamp(END_OF_TIME, tz=dt_timezone.utc)

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


def day_hour_schedule(start_dt: datetime, count: int) -> List[datetime]:
    """
    Produce `count` datetimes, 10/day, one per hour starting at START_HOUR.
    """
    out: List[datetime] = []

    cur = start_dt
    for i in range(count):
        out.append(cur)
        cur += timedelta(hours=1)

        # After PER_DAY items, advance to next day at START_HOUR
        if (i + 1) % PER_DAY == 0:
            next_day = cur.date() + timedelta(days=1)  # <-- FIX
            cur = datetime.combine(next_day, time(START_HOUR, 0, 0), tzinfo=cur.tzinfo)

    return out


class Command(BaseCommand):
    help = (  # noqa: A003
        "Reschedule active variations: "
        "levels>0 first, then level=0; "
        "set level=8 and spread 10/day starting 07:00 local."
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

        total_active = Variation.objects.active().count()

        self.stdout.write(
            f"This will reschedule {total_active} active variations:\n"
            f"  • Set level → {TARGET_LEVEL}\n"
            f"  • Rewrite next_review dates\n"
        )

        confirm_or_exit(
            prompt="Are you sure you want to continue?",
            assume_yes=dry_run,  # skip confirmation if dry-run
        )

        # ------------------------------------------------------------------
        # STEP 2: level > 0
        # ------------------------------------------------------------------

        step2_qs = (
            Variation.objects.active()
            .filter(level__gt=0)
            .order_by("level", "next_review")
            .only("id", "level", "next_review", "title")
        )

        step2 = list(step2_qs)
        self.stdout.write(f"Step 2: {len(step2)} variations (level > 0)")

        if step2:
            start_dt = timezone.make_aware(
                datetime.combine(
                    timezone.localdate(),
                    time(START_HOUR, 0, 0),
                ),
                tz,
            )

            step2_dates = day_hour_schedule(start_dt, len(step2))

            for v, new_dt in zip(step2, step2_dates):
                old_dt = v.next_review

                # If the existing next_review is already later than our new schedule,
                # keep it (but still set the level).
                keep_old_next_review = old_dt > new_dt

                if dry_run:
                    if keep_old_next_review:
                        self.stdout.write(
                            f"[DRY] #{v.id:<5} "
                            f"lvl {v.level} → {TARGET_LEVEL}, "
                            f"next_review unchanged ({old_dt}) (new would be {new_dt})"
                        )
                    else:
                        self.stdout.write(
                            f"[DRY] #{v.id:<5} "
                            f"lvl {v.level} → {TARGET_LEVEL}, "
                            f"{old_dt} → {new_dt}"
                        )
                    continue

                v.level = TARGET_LEVEL
                if keep_old_next_review:
                    v.save(update_fields=["level"])
                else:
                    v.next_review = new_dt
                    v.save(update_fields=["level", "next_review"])

            last_dt = step2_dates[-1]
        else:
            last_dt = None

        # ------------------------------------------------------------------
        # STEP 3: level == 0
        # ------------------------------------------------------------------

        step3_qs = (
            Variation.objects.active()
            .filter(level=0)
            .order_by("next_review")
            .only("id", "level", "next_review", "title")
        )

        step3 = list(step3_qs)
        self.stdout.write(f"Step 3: {len(step3)} variations (level == 0)")

        if step3:
            # Warn about END_OF_TIME
            # offenders = [v.id for v in step3 if v.next_review == END_OF_TIME_DT]
            # if offenders:
            #     self.stdout.write(
            #         self.style.WARNING(
            #             f"Warning: {len(offenders)} level-0 variations "
            #             f"have END_OF_TIME next_review: {offenders}"
            #         )
            #     )

            # Start the day *after* step 2 finishes
            if last_dt:
                start_date = last_dt.date() + timedelta(days=1)
            else:
                start_date = timezone.localdate()

            start_dt = timezone.make_aware(
                datetime.combine(start_date, time(START_HOUR, 0, 0)),
                tz,
            )

            step3_dates = day_hour_schedule(start_dt, len(step3))

            for v, new_dt in zip(step3, step3_dates):
                if dry_run:
                    self.stdout.write(
                        f"[DRY] #{v.id:<5} "
                        f"lvl 0 → {TARGET_LEVEL}, "
                        f"{v.next_review} → {new_dt}"
                    )
                else:
                    v.level = TARGET_LEVEL
                    v.next_review = new_dt
                    v.save(update_fields=["level", "next_review"])

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------

        self.stdout.write(
            f"Done. "
            f"Updated {len(step2)} (level>0) + {len(step3)} (level=0). "
            f"Dry-run={dry_run}."
        )
