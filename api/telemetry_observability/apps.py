"""
Django AppConfig for Telemetry Observability.

ready() is the single initialization point for:
  - Django signals
  - EventBus subscriptions (webhooks, notifications)
  - HookManager default hooks
  - PluginRegistry loading

DRY: no initialization code anywhere else — everything starts here.
"""
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class TelemetryObservabilityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'api.telemetry_observability'
    label              = 'telemetry_observability'
    verbose_name       = 'Telemetry & Observability'

    def ready(self) -> None:
        """
        Called once when Django starts.
        Order matters: signals → events → hooks → webhooks.
        """
        self._connect_signals()
        self._register_event_subscribers()
        self._register_default_hooks()
        self._init_webhooks()

    # ------------------------------------------------------------------
    # 1. Django signals
    # ------------------------------------------------------------------

    @staticmethod
    def _connect_signals() -> None:
        """Import signals module so all @receiver decorators are registered."""
        from . import signals  # noqa: F401
        logger.debug('Telemetry signals connected.')

    # ------------------------------------------------------------------
    # 2. EventBus subscriptions
    # ------------------------------------------------------------------

    @staticmethod
    def _register_event_subscribers() -> None:
        """
        Subscribe internal listeners to the EventBus.
        Add new app-wide event reactions here — never in individual modules.
        """
        from .events import event_bus, EventType

        def log_alert_event(event):
            logger.info(
                'Event %s: alert_id=%s',
                event.event_type.value,
                event.data.get('alert_id'),
            )

        event_bus.subscribe(EventType.ALERT_TRIGGERED,    log_alert_event)
        event_bus.subscribe(EventType.ALERT_ACKNOWLEDGED, log_alert_event)
        event_bus.subscribe(EventType.ALERT_RESOLVED,     log_alert_event)

        logger.debug('EventBus subscribers registered.')

    # ------------------------------------------------------------------
    # 3. Default hooks
    # ------------------------------------------------------------------

    @staticmethod
    def _register_default_hooks() -> None:
        """
        Register default hooks that run on every metric/alert/health operation.
        Add cross-cutting concerns (audit trail, enrichment) here.
        """
        from .hooks import hook_manager, HookType

        def enrich_metric_context(context: dict) -> None:
            """Add app version to every metric's labels."""
            from django.conf import settings
            data = context.get('data', {})
            labels = data.get('labels', {})
            labels.setdefault('app_version', getattr(settings, 'APP_VERSION', 'unknown'))
            data['labels'] = labels

        def log_critical_alerts(context: dict) -> None:
            """Log critical alerts at ERROR level for visibility."""
            data = context.get('data', {})
            if data.get('severity') == 'critical':
                logger.error(
                    'Critical alert triggered: %s — %s',
                    data.get('name'), data.get('message'),
                )

        hook_manager.register(
            HookType.BEFORE_METRIC_RECORD,
            enrich_metric_context,
            name='enrich_metric_labels',
            priority=10,
        )
        hook_manager.register(
            HookType.AFTER_ALERT_TRIGGER,
            log_critical_alerts,
            name='log_critical_alerts',
            priority=5,
        )

        logger.debug('Default hooks registered.')

    # ------------------------------------------------------------------
    # 4. Webhook dispatcher
    # ------------------------------------------------------------------

    @staticmethod
    def _init_webhooks() -> None:
        """
        Subscribe WebhookDispatcher to alert EventBus events.
        URLs come from settings.TELEMETRY_WEBHOOK_URLS (list of strings).
        """
        from django.conf import settings
        from .events import event_bus, EventType
        from .webhooks import WebhookDispatcher

        webhook_urls = getattr(settings, 'TELEMETRY_WEBHOOK_URLS', [])
        if not webhook_urls:
            logger.debug('No TELEMETRY_WEBHOOK_URLS configured — webhooks disabled.')
            return

        dispatcher = WebhookDispatcher(
            urls       = webhook_urls,
            timeout    = getattr(settings, 'TELEMETRY_WEBHOOK_TIMEOUT', 5),
            secret     = getattr(settings, 'TELEMETRY_WEBHOOK_SECRET', ''),
            max_retries= getattr(settings, 'TELEMETRY_WEBHOOK_MAX_RETRIES', 2),
        )

        event_bus.subscribe(EventType.ALERT_TRIGGERED,    dispatcher.on_alert_triggered)
        event_bus.subscribe(EventType.ALERT_ACKNOWLEDGED, dispatcher.on_alert_acknowledged)
        event_bus.subscribe(EventType.ALERT_RESOLVED,     dispatcher.on_alert_resolved)
        event_bus.subscribe(EventType.HEALTH_STATUS_CHANGED, dispatcher.on_health_changed)

        logger.info(
            'WebhookDispatcher registered for %d URL(s).', len(webhook_urls)
        )
