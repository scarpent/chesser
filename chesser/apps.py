import os

from django.apps import AppConfig
from django.conf import settings

from chesser.tasks import start_scheduler


class ChesserConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chesser"

    def ready(self):
        import chesser.signals  # Ensure signals are loaded  # noqa: F401

        if settings.IS_PRODUCTION:
            print("🕐️ Starting scheduler (production)")
            start_scheduler()
        elif os.environ.get("RUN_MAIN") == "true":
            # RUN_MAIN prevents running more than once in dev
            print("Starting scheduler")
            start_scheduler()
