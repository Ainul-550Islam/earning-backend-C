from django.apps import AppConfig


class KycConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.kyc'

    def ready(self):
        try:
            import api.kyc.signals  # noqa: F401
        except ImportError:
            pass
