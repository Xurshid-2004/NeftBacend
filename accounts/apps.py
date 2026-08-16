from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Auth va kirish kodlari"

    def ready(self):
        # Xodim o'chirilganda Face ID shablonini ham o'chirish signali.
        from . import signals  # noqa: F401
