from django.apps import AppConfig


class DRIntegrationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.dr_integration'
    verbose_name = 'Disaster Recovery Integration'

    def ready(self):
        import api.dr_integration.signals  # noqa
