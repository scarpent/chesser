from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from chesser.models import QuizResult, Variation

# Keep in sync with static/js/demo-login-autofill.js
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo"


class Command(BaseCommand):
    help = "Seed demo data (demo mode only)"  # noqa: A003

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default=str(
                Path(settings.BASE_DIR) / "examples" / "sample_repertoire.json"
            ),
            help="Path to demo JSON (default: examples/sample_repertoire.json)",
        )
        parser.add_argument(
            "--username",
            type=str,
            default=DEMO_USERNAME,
            help=f"Demo username (default: {DEMO_USERNAME})",
        )
        parser.add_argument(
            "--password",
            type=str,
            default=None,
            help=f"Demo password (default: {DEMO_PASSWORD})",
        )
        parser.add_argument(
            "--skip-user",
            action="store_true",
            help="Skip creating/updating the demo user",
        )
        parser.add_argument(
            "--skip-import",
            action="store_true",
            help="Skip importing demo repertoire data",
        )

    def handle(self, *args, **kwargs):
        if not getattr(settings, "IS_DEMO", False):
            raise CommandError(
                "Refusing to run: seed_demo is only allowed when CHESSER_ENV=demo."
            )

        file_path = Path(kwargs["file"])
        username = kwargs["username"]
        password = kwargs["password"] or DEMO_PASSWORD
        skip_user = kwargs["skip_user"]
        skip_import = kwargs["skip_import"]

        if not skip_user:
            self._ensure_demo_user(username=username, password=password)

        if not skip_import:
            self._import_demo_data(file_path=file_path)
            self._simulate_demo_reviews()

        self.stdout.write(self.style.SUCCESS("✅ Demo seed complete"))

    def _ensure_demo_user(self, username: str, password: str) -> None:
        User = get_user_model()
        user, created = User.objects.get_or_create(username=username)

        # Make it explicitly non-privileged.
        user.is_staff = False
        user.is_superuser = False
        user.set_password(password)
        user.save()

        if created:
            self.stdout.write(f"👤 Created demo user: {username!r}")
        else:
            self.stdout.write(f"👤 Updated demo user: {username!r}")

    def _import_demo_data(self, file_path: Path) -> None:
        self.stdout.write(f"📥 Importing demo data from: {file_path}")

        if not file_path.exists():
            raise CommandError(f"Demo JSON file not found: {file_path}")

        # bulk_import expects a string path, and --update maps to update=True.
        call_command(
            "bulk_import",
            file=str(file_path),
            update=True,
            stdout=self.stdout,
            stderr=self.stderr,
        )

        self.stdout.write(self.style.SUCCESS("✅ Demo data imported"))

    def _simulate_demo_reviews(self) -> None:
        """
        After importing the sample repertoire, tweak a couple variations so the
        demo review queue looks "alive" immediately (one due now, one due soon),
        and seed some QuizResult history.

        We match by exact title first, then fall back to icontains so small title
        edits don't silently break demo behavior.

        Safe to re-run: we wipe existing quiz_results for matched variations and
        recreate the scripted history.
        """
        now = timezone.now()

        # title, next_review, label, level, quiz_result_specs
        # quiz_result_specs: list of (dt, level, passed)
        rules = [
            (
                "Italian 4.Ng5 Knight Attack",
                now - timedelta(minutes=1),
                "due now",
                1,
                [
                    (now - timedelta(hours=7), 1, True),
                ],
            ),
            (
                "Alekhine’s - O’Sullivan Gambit",
                now + timedelta(days=1),
                "due in 1 day",
                2,
                [
                    (now, 1, True),
                    (now - timedelta(hours=7), 1, False),
                    (now - timedelta(hours=15), 0, False),
                ],
            ),
        ]

        with transaction.atomic():
            for title, next_review, label, variation_level, quiz_specs in rules:
                qs = Variation.objects.filter(title=title)
                if not qs.exists():
                    qs = Variation.objects.filter(title__icontains=title)

                variations = list(qs)
                if not variations:
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠️ Demo setup: no variation found matching {title!r}"
                        )
                    )
                    continue

                # Update variations (next_review + level)
                updated = qs.update(next_review=next_review, level=variation_level)

                # Make rerunnable: clear existing quiz results for these variations
                QuizResult.objects.filter(variation__in=variations).delete()

                # Create scripted quiz results for each matched variation
                quiz_results: list[QuizResult] = []
                for v in variations:
                    for dt, lvl, passed in quiz_specs:
                        quiz_results.append(
                            QuizResult(
                                variation=v,
                                datetime=dt,
                                level=lvl,
                                passed=passed,
                            )
                        )
                QuizResult.objects.bulk_create(quiz_results)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"🕒 Demo review setup: set {updated} variation(s) matching "
                        f"{title!r} to {label}, level={variation_level}, quiz_results="
                        f"{len(quiz_specs)}"
                    )
                )
