from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from chesser.demo import resolve_demo_variations
from chesser.models import QuizResult

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

        Uses demo keys + shared resolver in chesser.demo (no title matching here).

        Safe to re-run: we wipe existing quiz_results for the targeted variations and
        recreate the scripted history.
        """
        now = timezone.now()

        # key, next_review, label, level, quiz_result_specs
        # quiz_result_specs: list of (dt, level, passed)
        rules = [
            (
                "italian_ng5",
                now - timedelta(minutes=1),
                "due now",
                1,
                [
                    (now - timedelta(hours=7), 1, True),
                ],
            ),
            (
                "alekhine_osullivan",
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

        resolved = resolve_demo_variations(strict=False)

        with transaction.atomic():
            for key, next_review, label, variation_level, quiz_specs in rules:
                v = resolved.get(key)

                if not v:
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠️ Demo setup: no variation resolved for key={key!r}"
                        )
                    )
                    continue

                v.next_review = next_review
                v.level = variation_level
                v.save(update_fields=["next_review", "level"])

                # Make rerunnable: clear existing quiz results for this variation
                QuizResult.objects.filter(variation_id=v.id).delete()

                # Create scripted quiz results
                quiz_results: list[QuizResult] = [
                    QuizResult(
                        variation_id=v.id,
                        datetime=dt,
                        level=lvl,
                        passed=passed,
                    )
                    for dt, lvl, passed in quiz_specs
                ]
                QuizResult.objects.bulk_create(quiz_results)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"🕒 Demo review setup: set key={key!r} (id={v.id}) to {label}"
                        f", level={variation_level}, quiz_results={len(quiz_specs)}"
                    )
                )
