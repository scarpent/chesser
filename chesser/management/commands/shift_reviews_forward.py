from datetime import datetime
from datetime import timezone as dt_timezone

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from chesser.models import Variation
from chesser.util import END_OF_TIME

END_OF_TIME_DT = datetime.fromtimestamp(END_OF_TIME, tz=dt_timezone.utc)


class Command(BaseCommand):
    help = """Shift all next_review times forward so that the earliest becomes
        <now + minutes> (default: 10)"""  # noqa: A003

    def add_arguments(self, parser):
        parser.add_argument(
            "-m",
            "--minutes",
            type=int,
            default=10,
            help="""Number of minutes to shift the earliest review
                to from now (default: 10)""",
        )

    def handle(self, *args, **options):
        minutes = options["minutes"]

        oldest = (
            Variation.objects.exclude(next_review=END_OF_TIME_DT)
            .order_by("next_review")
            .first()
        )

        if not oldest:
            self.stdout.write(
                self.style.ERROR("❌ No variations with a valid next_review found.")
            )
            return

        target = timezone.now() + timezone.timedelta(minutes=minutes)
        delta = target - oldest.next_review

        count = 0
        with transaction.atomic():
            for var in Variation.objects.exclude(next_review=END_OF_TIME_DT):
                var.next_review += delta
                var.save(update_fields=["next_review"])
                count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Shifted next_review on {count} variations by {delta}."
            )
        )
