import os

from django.apps import AppConfig
from django.conf import settings

from chesser.tasks import start_scheduler


class ChesserConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chesser"

    def ready(self):
        import chesser.signals  # Ensure signals are loaded  # noqa: F401

        if os.environ.get("RUN_MAIN") == "true":  # Prevent running more than once
            if settings.DEBUG:
                print("DEBUG mode is on; not running scheduler 🕐️")
            else:
                print("Starting scheduler")
                start_scheduler()
