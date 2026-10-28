# api/support/apps.py  — WORLD #1 FINAL
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class SupportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'api.support'
    verbose_name       = 'Support Management'

    def ready(self):
        # 1. Load signals
        try:
            import api.support.signals  # noqa
        except Exception as e:
            logger.debug(f'Support signals: {e}')

        # 2. Load CPA signals
        try:
            import api.support.singals_cap  # noqa
        except Exception as e:
            logger.debug(f'CPA signals: {e}')

        # 3. Setup integration adapters
        try:
            from api.support.integrations.integ_adapter import setup_adapters
            setup_adapters()
        except Exception as e:
            logger.debug(f'Integration adapters: {e}')

        # 4. Connect integration signals (other apps → support)
        try:
            from api.support.integrations.integ_signals import connect_all_signals
            connect_all_signals()
        except Exception as e:
            logger.debug(f'Integration signals: {e}')

        # 5. Register on custom admin if available
        try:
            from api.support.admin import _force_register_support
            _force_register_support()
        except Exception:
            pass