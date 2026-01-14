import os

from django.apps import AppConfig
from django.conf import settings


class ChesserConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chesser"

    def ready(self):
        if settings.IS_DEMO:
            return  # No backups in demo mode

        # In development, require explicit opt-in for scheduler
        if settings.IS_DEVELOPMENT:
            if os.getenv("CHESSER_RUN_SCHEDULER", "false").lower() != "true":
                return
            if os.environ.get("RUN_MAIN") != "true":
                # Avoid duplicate scheduler starts in dev autoreloader subprocesses
                return

        print("🕐️ Starting scheduler")
        from chesser.tasks import start_scheduler

        start_scheduler()
