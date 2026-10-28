"""
Django signals for Telemetry Observability.

Each signal receiver does THREE things (in order):
  1. Run pre/post hooks via HookManager (synchronous, can veto)
  2. Publish an Event to EventBus (fan-out to subscribers like webhooks)
  3. Any model-specific business logic (alert auto-resolution, etc.)

DRY: no duplicated queryset logic here — use model methods or logic.py.
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models.metric_event import MetricEvent
from .models.log_entry import LogEntry
from .models.trace_span import TraceSpan
from .models.alert import Alert
from .models.health_status import HealthStatus
from .models.dashboard_widget import DashboardWidget
from .events import publish_event, EventType
from .hooks import hook_manager, HookType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MetricEvent signals
# ---------------------------------------------------------------------------

@receiver(post_save, sender=MetricEvent)
def on_metric_saved(sender, instance: MetricEvent, created: bool, **kwargs) -> None:
    """Fire hooks and publish event when a MetricEvent is created."""
    if not created:
        return

    context = {
        'data': {
            'id':          instance.pk,
            'name':        instance.name,
            'metric_type': instance.metric_type,
            'value':       instance.value,
            'service':     instance.service,
        }
    }

    hook_manager.run_safe(HookType.AFTER_METRIC_RECORD, context)
    publish_event(
        EventType.METRIC_RECORDED,
        data={'metric_id': instance.pk, 'name': instance.name, 'service': instance.service},
    )


# ---------------------------------------------------------------------------
# LogEntry signals
# ---------------------------------------------------------------------------

@receiver(post_save, sender=LogEntry)
def on_log_saved(sender, instance: LogEntry, created: bool, **kwargs) -> None:
    """Fire hooks and publish event when a LogEntry is created."""
    if not created:
        return

    context = {
        'data': {
            'id':      instance.pk,
            'level':   instance.level,
            'service': instance.service,
        }
    }

    hook_manager.run_safe(HookType.AFTER_LOG_RECORD, context)
    publish_event(
        EventType.LOG_RECORDED,
        data={'log_id': instance.pk, 'level': instance.level, 'service': instance.service},
    )


# ---------------------------------------------------------------------------
# TraceSpan signals
# ---------------------------------------------------------------------------

@receiver(post_save, sender=TraceSpan)
def on_trace_span_saved(sender, instance: TraceSpan, created: bool, **kwargs) -> None:
    """Publish trace events for span creation and completion."""
    if created:
        hook_manager.run_safe(HookType.AFTER_TRACE_START, {
            'data': {'span_id': instance.span_id, 'trace_id': instance.trace_id}
        })
        publish_event(
            EventType.TRACE_STARTED,
            data={'span_id': instance.span_id, 'trace_id': instance.trace_id,
                  'operation': instance.operation_name, 'service': instance.service},
        )
    elif instance.end_time is not None:
        hook_manager.run_safe(HookType.AFTER_TRACE_FINISH, {
            'data': {'span_id': instance.span_id, 'status': instance.status,
                     'duration_ms': instance.duration_ms}
        })
        publish_event(
            EventType.TRACE_FINISHED,
            data={'span_id': instance.span_id, 'trace_id': instance.trace_id,
                  'status': instance.status, 'duration_ms': instance.duration_ms},
        )


# ---------------------------------------------------------------------------
# Alert signals
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Alert)
def on_alert_saved(sender, instance: Alert, created: bool, **kwargs) -> None:
    """
    Publish alert lifecycle events.
    Maps Alert.status to the correct EventType.
    """
    context_data = {
        'alert_id':  instance.pk,
        'name':      instance.name,
        'severity':  instance.severity,
        'status':    instance.status,
        'service':   instance.service,
        'message':   instance.message,
    }

    if created:
        hook_manager.run_safe(HookType.AFTER_ALERT_TRIGGER, {'data': context_data})
        publish_event(EventType.ALERT_TRIGGERED, data=context_data)

    elif instance.status == 'acknowledged':
        publish_event(EventType.ALERT_ACKNOWLEDGED, data={
            **context_data, 'acknowledged_by': instance.acknowledged_by
        })

    elif instance.status == 'resolved':
        publish_event(EventType.ALERT_RESOLVED, data={
            **context_data, 'resolved_at': (
                instance.resolved_at.isoformat() if instance.resolved_at else None
            )
        })


# ---------------------------------------------------------------------------
# HealthStatus signals
# ---------------------------------------------------------------------------

@receiver(post_save, sender=HealthStatus)
def on_health_status_saved(sender, instance: HealthStatus, created: bool, **kwargs) -> None:
    """
    Publish health change event and run hooks.
    Triggers AFTER_HEALTH_CHECK hook and HEALTH_STATUS_CHANGED event.
    """
    context = {
        'data': {
            'service_name': instance.service_name,
            'status':       instance.status,
            'health_score': instance.health_score,
            'environment':  instance.environment,
        }
    }

    hook_manager.run_safe(HookType.AFTER_HEALTH_CHECK, context)
    publish_event(EventType.HEALTH_STATUS_CHANGED, data=context['data'])

    # Auto-trigger critical alert when health score drops below 30
    if instance.health_score < 30 and instance.status == 'unhealthy':
        _auto_alert_unhealthy_service(instance)


def _auto_alert_unhealthy_service(instance: HealthStatus) -> None:
    """
    Auto-create a critical alert when a service becomes critically unhealthy.
    Uses update_or_create to avoid duplicate alerts per service.
    """
    try:
        Alert.objects.update_or_create(
            name=f'service_unhealthy_{instance.service_name}',
            status='open',
            defaults={
                'alert_type':  'health',
                'severity':    'critical',
                'message':     (
                    f'Service {instance.service_name} is unhealthy '
                    f'(score={instance.health_score}).'
                ),
                'service':     instance.service_name,
                'environment': instance.environment,
                'condition':   {'health_score': instance.health_score},
            },
        )
    except Exception:
        logger.exception(
            'Failed to auto-create alert for unhealthy service %s',
            instance.service_name,
        )


# ---------------------------------------------------------------------------
# DashboardWidget signals
# ---------------------------------------------------------------------------

@receiver(post_save, sender=DashboardWidget)
def on_dashboard_widget_saved(sender, instance: DashboardWidget, created: bool, **kwargs) -> None:
    """Publish dashboard update event."""
    publish_event(
        EventType.DASHBOARD_UPDATED,
        data={
            'widget_id':   instance.pk,
            'name':        instance.name,
            'widget_type': instance.widget_type,
            'action':      'created' if created else 'updated',
        },
    )
