from django.apps import AppConfig


class EngagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.engagement'

    def ready(self):
        try:
            import api.engagement.signals  # noqa: F401
        except ImportError:
            pass
