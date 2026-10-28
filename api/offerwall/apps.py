from django.apps import AppConfig


class OfferwallConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name  = 'api.offerwall'
    label = 'offerwall'
    verbose_name = '🎯 Offerwall'

    def ready(self):
        # 1. Signals
        try:
            import api.offerwall.signals  # noqa: F401
        except ImportError:
            pass

        # 2. Celery tasks (auto-discover)
        try:
            import api.offerwall.tasks  # noqa: F401
        except ImportError:
            pass

        # 3. Register all offer processors at startup
        # FIX: was calling OfferFactory.register_all() which didn't exist.
        # Method name is auto_register_processors(). Both now work.
        try:
            from api.offerwall.services.OfferFactory import (
                auto_register_processors,
            )
            auto_register_processors()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                f'[OfferwallConfig] processor registration failed: {e}')
