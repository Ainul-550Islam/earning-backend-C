from django.apps import AppConfig


class KycConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.kyc'

    def ready(self):
        try:
            import api.kyc.signals  # noqa: F401
        except ImportError:
            pass
        try:
            from api.kyc.admin import _force_register_kyc
            _force_register_kyc()
        except Exception as e:
            pass
