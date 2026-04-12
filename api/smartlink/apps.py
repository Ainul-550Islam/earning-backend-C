from django.apps import AppConfig


class SmartLinkConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.smartlink'
    verbose_name = 'SmartLink System'

    def ready(self):
        import api.smartlink.signals  # noqa: F401
