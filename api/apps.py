from django.apps import AppConfig


class ApiConfig(AppConfig):
    name = 'api'
    label = 'api'

    def ready(self):
        """Import cache signals so they connect to model post_save/post_delete."""
        try:
            import api.cache.signals  # noqa: F401
        except ImportError:
            pass
