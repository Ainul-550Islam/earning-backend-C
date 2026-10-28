"""
alerts/apps.py
UPDATED: Added initialization for:
  - escalation system (escalation.py was floating)
  - backup system (backup.py was floating)
  - scheduler system (scheduler.py was floating)
  - event bus (events.py was floating)
  - factories (factories.py was floating)
  - querysets (querysets.py now wired into models)
  
Also documents: middleware.py and context_processors.py require
settings.py entries (see comments below).
"""
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


def _ensure_integration_permissions(sender=None, **kwargs):
    """post_migrate hook: create the integration Permission rows once the tables exist."""
    try:
        from api.alerts.integration.auth_bridge import integration_auth_bridge
        integration_auth_bridge._initialize_integration_permissions()
    except Exception as exc:  # never break `migrate`
        logger.warning('alerts: integration permission setup skipped: %s', exc)


class AlertsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.alerts'

    # One-off management commands must not start subsystems (threads, caches, DB reads) -
    # `migrate` in particular runs before the tables exist.
    MAINTENANCE_COMMANDS = frozenset({
        'makemigrations', 'migrate', 'showmigrations', 'sqlmigrate', 'squashmigrations',
        'collectstatic', 'check', 'compilemessages', 'makemessages', 'createcachetable',
        'dbshell', 'inspectdb', 'loaddata', 'dumpdata', 'flush', 'sqlflush',
        'sqlsequencereset', 'diffsettings', 'startapp', 'startproject',
    })

    def ready(self):
        import sys
        running_tests = 'pytest' in sys.modules or 'test' in sys.argv or 'test_coverage' in sys.argv
        maintenance = len(sys.argv) > 1 and sys.argv[1] in self.MAINTENANCE_COMMANDS

        # ── 1. Signals ──────────────────────────────────────────────────────
        try:
            import api.alerts.signals  # noqa: F401
        except ImportError:
            logger.warning('alerts: could not import signals')

        # Integration permissions are created after migrations (never at import time).
        from django.db.models.signals import post_migrate
        post_migrate.connect(_ensure_integration_permissions, sender=self,
                             dispatch_uid='alerts_integration_permissions')

        if maintenance:
            return

        # ── 2. psycopg2 JSON adapter ────────────────────────────────────────
        try:
            import psycopg2.extras
            import psycopg2.extensions
            import json
            import uuid
            from decimal import Decimal
            from datetime import datetime, date

            class SafeJsonEncoder(json.JSONEncoder):
                def default(self, obj):
                    if isinstance(obj, uuid.UUID):
                        return str(obj)
                    if isinstance(obj, (datetime, date)):
                        return obj.isoformat()
                    if isinstance(obj, Decimal):
                        return float(obj)
                    if hasattr(obj, 'pk'):
                        return obj.pk
                    return str(obj)

            def safe_dumps(obj):
                return json.dumps(obj, cls=SafeJsonEncoder)

            psycopg2.extensions.register_adapter(
                dict,
                lambda d: psycopg2.extras.Json(d, dumps=safe_dumps)
            )
            psycopg2.extensions.register_adapter(
                list,
                lambda l: psycopg2.extras.Json(l, dumps=safe_dumps)
            )
        except Exception:
            pass

        # ── 3. Cache manager ────────────────────────────────────────────────
        try:
            from api.alerts.cache_manager import initialize_cache_manager
            initialize_cache_manager()
            logger.debug('alerts: cache_manager initialised')
        except Exception as e:
            logger.warning('alerts: cache_manager init failed: %s', e)

        # ── 4. Circuit breakers ──────────────────────────────────────────────
        try:
            from api.alerts.circuit_breaker import initialize_circuit_breakers
            initialize_circuit_breakers()
            logger.debug('alerts: circuit_breakers initialised')
        except Exception as e:
            logger.warning('alerts: circuit_breaker init failed: %s', e)

        # ── 5. Rate limiter ──────────────────────────────────────────────────
        try:
            from api.alerts.rate_limiter import initialize_rate_limiter
            initialize_rate_limiter()
            logger.debug('alerts: rate_limiter initialised')
        except Exception as e:
            logger.warning('alerts: rate_limiter init failed: %s', e)

        # ── 6. Plugin system ─────────────────────────────────────────────────
        try:
            from api.alerts.plugins import initialize_plugins
            initialize_plugins()
            logger.debug('alerts: plugins initialised')
        except Exception as e:
            logger.warning('alerts: plugins init failed: %s', e)

        # ── 7. Component registry ────────────────────────────────────────────
        try:
            from api.alerts.registry import initialize_registry
            initialize_registry()
            logger.debug('alerts: registry initialised')
        except Exception as e:
            logger.warning('alerts: registry init failed: %s', e)

        # ── 8. Performance monitor ───────────────────────────────────────────
        # Spawns a real background collection thread - skip during tests to
        # avoid cross-thread access to the per-test SQLite transaction.
        if not running_tests:
            try:
                from api.alerts.performance_monitor import initialize_performance_monitoring
                initialize_performance_monitoring()
                logger.debug('alerts: performance_monitor initialised')
            except Exception as e:
                logger.warning('alerts: performance_monitor init failed: %s', e)

        # ── 9. Integration subsystems ────────────────────────────────────────
        try:
            from api.alerts.integration import initialize_integration
            initialize_integration()
            logger.debug('alerts: integration subsystems initialised')
        except Exception as e:
            logger.warning('alerts: integration init failed: %s', e)

        # ── 10. Escalation system (was floating in escalation.py) ────────────
        try:
            from api.alerts.escalation import initialize_escalation_system
            initialize_escalation_system()
            logger.debug('alerts: escalation system initialised')
        except Exception as e:
            logger.warning('alerts: escalation init failed: %s', e)

        # ── 11. Backup system (was floating in backup.py) ────────────────────
        try:
            from api.alerts.backup import initialize_backup_system
            initialize_backup_system()
            logger.debug('alerts: backup system initialised')
        except Exception as e:
            logger.warning('alerts: backup init failed: %s', e)

        # ── 12. Task scheduler (was floating in scheduler.py) ────────────────
        try:
            from api.alerts.scheduler import initialize_task_scheduler
            initialize_task_scheduler()
            logger.debug('alerts: task scheduler initialised')
        except Exception as e:
            logger.warning('alerts: scheduler init failed: %s', e)

        # ── 13. Event handler (was floating in events.py) ────────────────────
        try:
            from api.alerts.events import AlertEventHandler
            _handler = AlertEventHandler()
            logger.debug('alerts: event handler initialised')
        except Exception as e:
            logger.warning('alerts: event handler init failed: %s', e)

        # ── 14. Factory registry (was floating in factories.py) ──────────────
        try:
            from api.alerts.factories import register_factories_from_settings
            register_factories_from_settings()
            logger.debug('alerts: factory registry initialised')
        except Exception as e:
            logger.warning('alerts: factories init failed: %s', e)

        # ── 15. Metrics collector (was floating in metrics_collector.py) ─────
        try:
            from api.alerts.metrics_collector import MetricsCollector
            _collector = MetricsCollector()
            logger.debug('alerts: metrics collector initialised')
        except Exception as e:
            logger.warning('alerts: metrics_collector init failed: %s', e)

        # ─────────────────────────────────────────────────────────────────────
        # SETTINGS REQUIRED (cannot be done in ready()):
        #
        # middleware.py → add to MIDDLEWARE in settings.py:
        #   'api.alerts.middleware.AlertContextMiddleware',
        #   'api.alerts.middleware.AlertRateLimitMiddleware',
        #   'api.alerts.middleware.AlertSecurityMiddleware',
        #   'api.alerts.middleware.AlertLoggingMiddleware',
        #   (or use performance_optimizations.py versions for production)
        #
        # context_processors.py → add to TEMPLATES[0]['OPTIONS']['context_processors']:
        #   'api.alerts.context_processors.alert_counts',
        #   'api.alerts.context_processors.user_alerts',
        #   'api.alerts.context_processors.system_health',
        #   'api.alerts.context_processors.alert_statistics',
        #
        # PLACEMENT AT api/alerts/: this AppConfig's `name` below is 'alerts',
        # matching how this standalone package is laid out (and how
        # test_settings.py's INSTALLED_APPS references it: 'api.alerts.apps.AlertsConfig').
        # Once copied into the real project at api/alerts/, Django resolves apps by
        # their actual Python import path - so `name` needs to become 'api.alerts',
        # and INSTALLED_APPS needs 'api.alerts.apps.AlertsConfig' (or 'api.alerts'),
        # not 'alerts'/'api.alerts.apps.AlertsConfig'. Not changed here since doing so
        # would break this package's own standalone tests; this is an integration-time
        # edit, matching how api/alerts/urls.py is already written to be imported as
        # `from api.alerts.urls import urlpatterns`.
        # ─────────────────────────────────────────────────────────────────────
