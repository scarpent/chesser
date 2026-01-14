import os

from django.apps import AppConfig
from django.conf import settings


class ChesserConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chesser"

    def ready(self):
        """
        Start the Chesser background scheduler. (Used for backups.)

        The scheduler is intentionally started only in the long-running web
        process (e.g. gunicorn or runserver) and is gated by the
        CHESSER_START_SCHEDULER environment variable. This prevents it from
        running during short-lived management commands such as migrate,
        collectstatic, or shell.

        Demo mode disables the scheduler entirely.

        Note:
        If switching back to Django's built-in autoreloader (instead of
        watchmedo), a RUN_MAIN guard may be required to avoid starting the
        scheduler twice in development.
        """
        if settings.IS_DEMO:
            return  # No backups needed

        if os.getenv("CHESSER_START_SCHEDULER", "false").lower() != "true":
            return

        print("🕐️ Starting scheduler")
        from chesser.tasks import start_scheduler

        start_scheduler()
