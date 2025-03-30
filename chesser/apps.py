import os
import socket

from django.apps import AppConfig
from django.conf import settings

_scheduler_socket = None  # global socket handle


class ChesserConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chesser"

    def ready(self):
        import chesser.signals  # Ensure signals are loaded  # noqa: F401

        # Avoid duplicate scheduler starts in dev autoreloader subprocesses
        if not settings.IS_PRODUCTION and os.environ.get("RUN_MAIN") != "true":
            return

        try:
            sock = socket.socket()
            sock.bind(("127.0.0.1", 65432))  # Use a high-numbered loopback port
            _scheduler_socket = sock  # noqa: F841 # Keep socket open to prevent dupes
            print("🕐️ Starting scheduler (acquired socket lock)")
            from chesser.tasks import start_scheduler

            start_scheduler()
        except OSError:
            print("🚫 Scheduler already running in another process (socket lock)")
