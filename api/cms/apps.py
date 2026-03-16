# api/cms/apps.py
from django.apps import AppConfig

class CMSConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.cms'

    def ready(self):
        try:
            import api.cms.signals  # noqa: F401
        except ImportError:
            pass
        import api.cms.admin  # noqa: F401
        print("[OK] CMS Admin successfully loaded!")