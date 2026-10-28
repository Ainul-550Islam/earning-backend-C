"""
Alert Integration Package
Registers all integration components on app startup.
Called from AlertsConfig.ready() in apps.py.
"""
import logging

logger = logging.getLogger(__name__)

# ── Lazy singleton references (set by initialize_integration()) ───────────────
_circuit_breaker_manager = None
_fallback_handler = None
_audit_logger = None
_integration_registry = None
_message_queue = None


def initialize_integration():
    """
    Initialise all integration subsystems.
    Called once from AlertsConfig.ready().
    """
    global _circuit_breaker_manager, _fallback_handler, _audit_logger
    global _integration_registry, _message_queue

    # 1. Circuit-breaker manager
    try:
        from .circuit_breaker import CircuitBreakerManager
        _circuit_breaker_manager = CircuitBreakerManager()
        logger.info("integration: CircuitBreakerManager initialised")
    except Exception as exc:
        logger.warning("integration: CircuitBreakerManager init failed: %s", exc)

    # 2. Fallback handler
    try:
        from .fallback_logic import FallbackHandler
        _fallback_handler = FallbackHandler()
        logger.info("integration: FallbackHandler initialised")
    except Exception as exc:
        logger.warning("integration: FallbackHandler init failed: %s", exc)

    # 3. Audit logger
    try:
        from .integ_audit_logs import AuditLogger
        _audit_logger = AuditLogger()
        logger.info("integration: AuditLogger initialised")
    except Exception as exc:
        logger.warning("integration: AuditLogger init failed: %s", exc)

    # 4. Integration registry
    try:
        from .integ_registry import IntegrationRegistry
        _integration_registry = IntegrationRegistry()
        # Register channel services so the registry knows what's available
        _register_channel_services(_integration_registry)
        logger.info("integration: IntegrationRegistry initialised")
    except Exception as exc:
        logger.warning("integration: IntegrationRegistry init failed: %s", exc)

    # 5. Message queue (in-memory default; swap for Redis/Kafka in settings)
    try:
        import sys
        running_tests = 'pytest' in sys.modules or 'test' in sys.argv or 'test_coverage' in sys.argv
        from .message_queue import InMemoryQueue
        _message_queue = InMemoryQueue(start_workers=not running_tests)
        logger.info("integration: MessageQueue initialised")
    except Exception as exc:
        logger.warning("integration: MessageQueue init failed: %s", exc)

    logger.info("integration: all subsystems ready")


def _register_channel_services(registry):
    """Register each channel service with the integration registry."""
    channel_map = {
        'email':     'api.alerts.services.channels.EmailAlertService.EmailAlertService',
        'slack':     'api.alerts.services.channels.SlackAlertService.SlackAlertService',
        'telegram':  'api.alerts.services.channels.TelegramAlertService.TelegramAlertService',
        'discord':   'api.alerts.services.channels.DiscordAlertService.DiscordAlertService',
        'webhook':   'api.alerts.services.channels.WebhookAlertService.WebhookAlertService',
        'sms':       'api.alerts.services.channels.SMSAlertService.SMSAlertService',
        'pagerduty': 'api.alerts.services.channels.PagerDutyService.PagerDutyService',
        'opsgenie':  'api.alerts.services.channels.OpsGenieService.OpsGenieService',
    }
    for name, dotted_path in channel_map.items():
        try:
            module_path, cls_name = dotted_path.rsplit('.', 1)
            import importlib
            mod = importlib.import_module(module_path)
            cls = getattr(mod, cls_name)
            registry.register(name, cls)
        except Exception as exc:
            logger.debug("integration: could not register channel '%s': %s", name, exc)


# ── Public accessors ──────────────────────────────────────────────────────────

def get_circuit_breaker_manager():
    return _circuit_breaker_manager


def get_fallback_handler():
    return _fallback_handler


def get_audit_logger():
    return _audit_logger


def get_integration_registry():
    return _integration_registry


def get_message_queue():
    return _message_queue


# ── Public API helpers added for ViewSet access ───────────────────────────────
# Previously the only public interface was the get_*() accessors for the 5 singletons.
# Added below: thin wrappers that the ViewSets call, so no import of internals needed.

def get_all_integration_status():
    """Return a combined status dict for all integration subsystems."""
    return {
        'circuit_breaker_manager': _circuit_breaker_manager is not None,
        'fallback_handler': _fallback_handler is not None,
        'audit_logger': _audit_logger is not None,
        'integration_registry': _integration_registry is not None,
        'message_queue': _message_queue is not None,
    }
