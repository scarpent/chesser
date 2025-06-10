import datetime
import random
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils.timezone import localtime, now

from chesser.models import REPETITION_INTERVALS, QuizResult, Variation


class Command(BaseCommand):
    help = "Forecast review volume and show historical review stats"  # noqa: A003

    def handle(self, *args, **options):
        start_date = datetime.date(2025, 3, 20)
        quiz_results = QuizResult.objects.filter(datetime__date__gte=start_date)

        # Count reviews per day (historical)
        counts = defaultdict(int)
        for quiz_result in quiz_results:
            day = localtime(quiz_result.datetime).date()
            counts[day] += 1

        # Forecast
        forecast_counts = simulate_forecast()
        for day, count in forecast_counts.items():
            counts[day] += count

        for day_ in counts:
            count = counts.get(day_, 0)
            print(f"{day_.strftime('%Y/%m/%d')}\t{count}")
            day_ += datetime.timedelta(days=1)


def get_level_success_rates():
    # TODO: later we should use a sliding window of last N days per level
    qs = QuizResult.objects.all()
    level_data = qs.values("level").annotate(
        total_count=Count("id"),
        passed_count=Count("id", filter=Q(passed=True)),
    )

    return {
        entry["level"]: entry["passed_count"] / entry["total_count"]
        for entry in level_data
        if entry["total_count"] > 0
    }


def simulate_forecast():
    level_success_rate = get_level_success_rates()
    review_schedule = {}
    review_counts = defaultdict(int)

    # Build forecast input: next_review -> {'level': int}
    cutoff = now() + datetime.timedelta(days=365)
    for var in Variation.objects.filter(next_review__lte=cutoff):
        dt = var.next_review
        while dt in review_schedule:  # unlikely, but just in case
            dt += datetime.timedelta(seconds=1)  # prevent overwrite
        review_schedule[dt] = {"level": var.level}

    # Process queue up to N days out
    forecast_end = now() + datetime.timedelta(days=90)

    queue = list(review_schedule.items())

    while True:
        queue.sort()
        if not queue:
            break

        dt, entry = queue.pop(0)
        if dt > forecast_end:
            break

        level = entry["level"]
        day_key = dt.date()
        review_counts[day_key] += 1

        success_chance = level_success_rate.get(level, 0.5)
        success = random.random() < success_chance
        # see what better memory looks like (spoiler alert: way less work!)
        # success = True

        new_level = level + 1 if success else 1
        interval_hours = REPETITION_INTERVALS.get(new_level, 720)
        next_dt = dt + datetime.timedelta(hours=interval_hours)

        while next_dt in review_schedule:
            next_dt += datetime.timedelta(seconds=1)

        review_schedule[next_dt] = {"level": new_level}
        queue.append((next_dt, {"level": new_level}))

    return review_counts
