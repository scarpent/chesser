from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from chesser.models import Variation
from chesser.util import END_OF_TIME_DT


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

        qs = Variation.objects.active().exclude(next_review=END_OF_TIME_DT)

        oldest = qs.order_by("next_review").first()
        if not oldest:
            self.stdout.write(
                self.style.ERROR("❌ No variations with a valid next_review found.")
            )
            return

        target = timezone.now() + timezone.timedelta(minutes=minutes)
        delta = target - oldest.next_review

        with transaction.atomic():
            updated = qs.update(next_review=F("next_review") + delta)

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Shifted next_review on {updated} variations by {delta}."
            )
        )
