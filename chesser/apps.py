from django.apps import AppConfig


class ChesserConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chesser"

    def ready(self):
        import chesser.signals  # Ensure signals are loaded  # noqa: F401
