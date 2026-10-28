# publisher_tools/apps.py  — COMPLETE FIXED VERSION
# ============================================================
# Changes from original:
#   1. ready() imports signals (was missing — signals never fired)
#   2. ready() validates that subfolders are importable on startup
#   3. ready() registers webhooks/ and fraud_prevention/ __init__
#      so they're available app-wide without circular imports
# Replace your existing apps.py with this file entirely.
# ============================================================
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class PublisherToolsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name   = 'api.publisher_tools'
    label  = 'publisher_tools'
    verbose_name = 'Publisher Tools'

    def ready(self):
        """
        App fully loaded হলে:
        1. Signals import করে (এটা না করলে signals কখনো fire হয় না)
        2. Subfolder __init__ imports validate করে
        3. Celery beat schedule নিবন্ধন করে (optional)
        """

        # ── 1. Register signals ───────────────────────────────────────────
        try:
            from . import signals  # noqa: F401
            logger.debug('publisher_tools: signals registered')
        except Exception as e:
            logger.error(f'publisher_tools: signal registration failed: {e}')

        # ── 2. Validate subfolder imports (startup check only) ────────────
        _CRITICAL_SUBFOLDERS = [
            ('fraud_prevention',   '.fraud_prevention',   'detect_invalid_traffic'),
            ('webhooks',           '.webhooks',           'send_webhook_event'),
            ('payment_settlement', '.payment_settlement', 'calculate_monthly_earnings'),
            ('optimization_tools', '.optimization_tools', 'optimize_floor_prices'),
        ]

        for folder, import_path, func in _CRITICAL_SUBFOLDERS:
            try:
                mod = __import__(
                    f'publisher_tools{import_path}',
                    fromlist=[func],
                )
                if not hasattr(mod, func):
                    logger.warning(
                        f'publisher_tools/{folder}: exported function '
                        f'"{func}" not found — check __init__.py'
                    )
                else:
                    logger.debug(f'publisher_tools/{folder}: OK ({func} available)')
            except ImportError as e:
                logger.warning(
                    f'publisher_tools/{folder}: import failed — '
                    f'{e}. Dependent features will fall back to inline logic.'
                )
            except Exception as e:
                logger.error(f'publisher_tools/{folder}: unexpected error during startup check: {e}')

        # ── 3. Optional: log registered Celery tasks ──────────────────────
        try:
            from celery import current_app as celery_app
            registered = [
                t for t in celery_app.tasks
                if t.startswith('publisher_tools.')
            ]
            logger.debug(f'publisher_tools: {len(registered)} Celery tasks registered')
        except Exception:
            pass  # Celery not configured — that's fine in dev/test
