from django.apps import AppConfig


class EngagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.engagement'

    def ready(self):
        try:
            import api.engagement.signals  # noqa: F401
        except ImportError:
            pass
        try:
            from api.engagement.admin import _force_register_engagement
            _force_register_engagement()
        except Exception as e:
            pass
