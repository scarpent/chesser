from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone

from chesser.models import QuizResult


class Command(BaseCommand):
    help = "Print daily quiz result stats and grand totals by level"  # noqa: A003

    def handle(self, *args, **options):
        start_date = date(2025, 3, 20)
        today = timezone.localtime(timezone.now()).date()

        def local_day_bounds(day):
            start = timezone.localtime(
                timezone.make_aware(datetime.combine(day, datetime.min.time()))
            )
            end = timezone.localtime(
                timezone.make_aware(
                    datetime.combine(day + timedelta(days=1), datetime.min.time())
                )
            )
            return start, end

        grand_totals = {}

        current = start_date
        while current <= today:
            start, end = local_day_bounds(current)
            qs = QuizResult.objects.filter(datetime__gte=start, datetime__lt=end)
            total = qs.count()
            passed = qs.filter(passed=True).count()
            percent = int((passed / total) * 100) if total else 0

            self.stdout.write(f"{current.isoformat()}: {passed}/{total} ({percent}%)")

            for level, total_count, passed_count in (
                qs.values("level")
                .annotate(
                    total_count=Count("id"),
                    passed_count=Count("id", filter=Q(passed=True)),
                )
                .values_list("level", "total_count", "passed_count")
            ):
                grand_totals.setdefault(level, {"total": 0, "passed": 0})
                grand_totals[level]["total"] += total_count
                grand_totals[level]["passed"] += passed_count

            current += timedelta(days=1)

        self.stdout.write("\nGrand totals by level:")
        for level in sorted(grand_totals):
            data = grand_totals[level]
            percent = (
                int((data["passed"] / data["total"]) * 100) if data["total"] else 0
            )
            self.stdout.write(
                f"  L{level:>2}: {data['passed']:>3}/{data['total']:>3} ({percent}%)"
            )
