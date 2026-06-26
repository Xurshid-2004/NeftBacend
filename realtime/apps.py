from django.apps import AppConfig


class RealtimeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "realtime"
    verbose_name = "Real-time (WebSocket)"

    def ready(self):
        # Signal handlerlarni ulash
        from . import signals  # noqa: F401
