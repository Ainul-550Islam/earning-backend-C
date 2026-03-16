from django.apps import AppConfig


class AdminPanelConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.admin_panel'
    verbose_name = 'Admin Panel'

    def ready(self):
        try:
            import api.admin_panel.signals  # noqa: F401
        except ImportError:
            pass