# api/publisher_tools/apps.py
from django.apps import AppConfig
class PublisherToolsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.publisher_tools'
    label = 'publisher_tools'
    verbose_name = 'Publisher Tools'
    def ready(self):
        try:
            import api.publisher_tools.signals
            print('[OK] Publisher Tools signals loaded')
        except ImportError:
            pass
        try:
            from api.publisher_tools.admin import _force_register_publisher_tools
            _force_register_publisher_tools()
        except Exception as e:
            print(f'[WARN] Publisher Tools admin: {e}')
