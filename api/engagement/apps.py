from django.apps import AppConfig
class EngagementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.engagement"
    label = "engagement"
    verbose_name = "Engagement & Gamification"
    def ready(self):
        try:
            import api.engagement.signals.handlers  # noqa
        except Exception:
            pass
