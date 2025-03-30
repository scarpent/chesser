import os

from django.apps import AppConfig
from django.conf import settings


class ChesserConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chesser"

    def ready(self):
        import chesser.signals  # Ensure signals are loaded  # noqa: F401

        # Avoid duplicate scheduler starts in dev autoreloader subprocesses
        if not settings.IS_PRODUCTION and os.environ.get("RUN_MAIN") != "true":
            return

        print("🕐️ Starting scheduler")
        from chesser.tasks import start_scheduler

        start_scheduler()
