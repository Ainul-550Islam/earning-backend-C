from django.apps import AppConfig

class DisasterRecoveryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.disaster_recovery'
    verbose_name = 'Disaster Recovery'

    def ready(self):
        try:
            import api.disaster_recovery.signals
        except Exception:
            pass
