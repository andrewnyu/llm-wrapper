from django.apps import AppConfig


class UsageConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api_key_wrapper.usage"

    def ready(self):
        from . import signals  # noqa: F401
