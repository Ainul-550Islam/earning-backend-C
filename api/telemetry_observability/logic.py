"""
Business logic layer for Telemetry Observability.

ARCHITECTURE RULE:
  views/viewsets → services/ → logic.py → metrics.py / alerting.py / tracing.py → models

  - logic.py  : the "what" — business rules, type dispatch, error handling
  - services/ : thin facades — receive validated data from views, call logic.py
  - metrics.py / alerting.py / tracing.py : low-level data operations
  - models    : ORM layer

DRY: Never duplicate logic from here in services/. Services call logic.py.
"""
from typing import Dict, Any, Optional, List
from django.utils import timezone
from datetime import timedelta

from .models.metric_event import MetricEvent
from .models.log_entry import LogEntry
from .models.trace_span import TraceSpan
from .models.alert import Alert
from .models.health_status import HealthStatus
from .models.dashboard_widget import DashboardWidget
from .metrics import MetricsCollector, MetricsAggregator
from .alerting import AlertingService as CoreAlertingService
from .tracing import TracingService as CoreTracingService
from .exceptions import TelemetryException
from .choices import MetricTypeChoices


# ---------------------------------------------------------------------------
# Metric Logic
# ---------------------------------------------------------------------------

class MetricLogic:
    """
    Canonical business logic for metric operations.
    Services must call this; they do NOT re-implement it.
    """

    def __init__(self):
        self.collector  = MetricsCollector()
        self.aggregator = MetricsAggregator()

    def record_metric(self, data: Dict[str, Any]) -> MetricEvent:
        """
        Route and record a metric based on its type.

        Args:
            data: Validated metric dict (from serializer.validated_data)

        Returns:
            Created MetricEvent instance
        """
        metric_type = data.get('metric_type', MetricTypeChoices.COUNTER)
        kwargs = {
            'name':        data['name'],
            'value':       data.get('value', 1.0),
            'unit':        data.get('unit', ''),
            'labels':      data.get('labels', {}),
            'source':      data.get('source', 'application'),
            'service':     data.get('service', 'default'),
            'environment': data.get('environment', 'production'),
        }

        method_map = {
            MetricTypeChoices.COUNTER:   self.collector.record_counter,
            MetricTypeChoices.GAUGE:     self.collector.record_gauge,
            MetricTypeChoices.HISTOGRAM: self.collector.record_histogram,
            MetricTypeChoices.SUMMARY:   self.collector.record_summary,
        }

        method = method_map.get(metric_type)
        if method is None:
            raise TelemetryException(
                f"Invalid metric_type '{metric_type}'. "
                f"Valid: {list(method_map.keys())}"
            )
        return method(**kwargs)

    def batch_record(self, data_list: List[Dict[str, Any]]) -> List[MetricEvent]:
        """
        Batch-record multiple metrics. Each item goes through record_metric().

        Args:
            data_list: List of validated metric dicts

        Returns:
            List of created MetricEvent instances
        """
        return [self.record_metric(item) for item in data_list]

    def get_metrics(
        self,
        name: Optional[str] = None,
        metric_type: Optional[str] = None,
        source: Optional[str] = None,
        service: Optional[str] = None,
        environment: Optional[str] = None,
        limit: int = 100,
    ) -> List[MetricEvent]:
        """Filter and return metric events."""
        return self.collector.get_metrics(
            name=name,
            metric_type=metric_type,
            source=source,
            service=service,
            environment=environment,
            limit=limit,
        )

    def get_statistics(self, name: str, hours: int = 24) -> Dict[str, Any]:
        """
        Compute aggregate statistics for a named metric.

        Args:
            name:  Metric name
            hours: Look-back window

        Returns:
            Stats dict with count, avg, min, max, sum
        """
        since   = timezone.now() - timedelta(hours=hours)
        metrics = self.collector.get_metrics(name=name, since=since)

        if not metrics:
            return {'metric_name': name, 'period_hours': hours,
                    'count': 0, 'avg': 0.0, 'min': 0.0, 'max': 0.0, 'sum': 0.0}

        values = [m.value for m in metrics]
        return {
            'metric_name':  name,
            'period_hours': hours,
            'count': len(values),
            'avg':   round(sum(values) / len(values), 4),
            'min':   round(min(values), 4),
            'max':   round(max(values), 4),
            'sum':   round(sum(values), 4),
        }

    def aggregate_by_time(self, name: str, interval: str, since) -> list:
        """Delegate to MetricsAggregator for time-series aggregation."""
        return self.aggregator.aggregate_by_time(name, interval, since)


# ---------------------------------------------------------------------------
# Log Logic
# ---------------------------------------------------------------------------

class LogLogic:
    """
    Canonical business logic for log entry operations.
    """

    def record_log(self, data: Dict[str, Any]) -> LogEntry:
        """
        Create a log entry.

        Args:
            data: Validated log dict

        Returns:
            Created LogEntry instance
        """
        return LogEntry.objects.create(
            level=data.get('level', 'info'),
            message=data['message'],
            logger_name=data.get('logger_name', ''),
            source=data.get('source', ''),
            service=data.get('service', ''),
            environment=data.get('environment', 'production'),
            stack_trace=data.get('stack_trace', ''),
            context=data.get('context', {}),
            tags=data.get('tags', []),
        )

    def batch_record(self, data_list: List[Dict[str, Any]]) -> List[LogEntry]:
        """Batch-create log entries."""
        return [self.record_log(item) for item in data_list]

    def get_logs(
        self,
        level: Optional[str] = None,
        source: Optional[str] = None,
        service: Optional[str] = None,
        environment: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100,
    ) -> List[LogEntry]:
        """Filter and return log entries."""
        qs = LogEntry.objects.all()
        if level:
            qs = qs.filter(level=level)
        if source:
            qs = qs.filter(source=source)
        if service:
            qs = qs.filter(service=service)
        if environment:
            qs = qs.filter(environment=environment)
        if search:
            qs = qs.filter(message__icontains=search)
        return list(qs.order_by('-timestamp')[:limit])


# ---------------------------------------------------------------------------
# Alert Logic
# ---------------------------------------------------------------------------

class AlertLogic:
    """
    Canonical business logic for alert operations.
    """

    def __init__(self):
        self._core = CoreAlertingService()

    def create_alert(self, data: Dict[str, Any]) -> Alert:
        """
        Create an alert via the core alerting layer.

        Args:
            data: Validated alert dict

        Returns:
            Created Alert instance
        """
        return self._core.create_alert(
            name=data['name'],
            alert_type=data.get('alert_type', 'custom'),
            severity=data.get('severity', 'warning'),
            message=data.get('message', ''),
            condition=data.get('condition', {}),
            source=data.get('source', ''),
            service=data.get('service', ''),
            environment=data.get('environment', 'production'),
            metadata=data.get('metadata', {}),
        )

    def batch_create(self, data_list: List[Dict[str, Any]]) -> List[Alert]:
        """Batch-create alerts."""
        return [self.create_alert(item) for item in data_list]

    def get_alerts(
        self,
        alert_type: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        source: Optional[str] = None,
        service: Optional[str] = None,
        environment: Optional[str] = None,
        limit: int = 100,
    ) -> List[Alert]:
        """Filter and return alerts."""
        return self._core.get_alerts(
            alert_type=alert_type,
            severity=severity,
            status=status,
            source=source,
            service=service,
            environment=environment,
            limit=limit,
        )

    def acknowledge(self, alert_id: int, user: str) -> bool:
        """Acknowledge an alert. Returns True if found, False otherwise."""
        return self._core.acknowledge_alert(alert_id, user)

    def resolve(self, alert_id: int) -> bool:
        """Resolve an alert. Returns True if found, False otherwise."""
        return self._core.resolve_alert(alert_id)

    def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Return alert statistics."""
        return self._core.get_alert_statistics(hours=hours)

    def get_open(self, service: Optional[str] = None) -> List[Alert]:
        """Return all open alerts."""
        return self._core.get_open_alerts(service=service)

    def get_critical(self, service: Optional[str] = None) -> List[Alert]:
        """Return all critical-severity alerts."""
        return self._core.get_critical_alerts(service=service)


# ---------------------------------------------------------------------------
# Trace Logic
# ---------------------------------------------------------------------------

class TraceLogic:
    """
    Canonical business logic for distributed trace operations.
    """

    def __init__(self):
        self._core = CoreTracingService()

    def start_span(self, data: Dict[str, Any]) -> TraceSpan:
        """Start a new trace span via the core tracing layer."""
        return self._core.start_span(
            operation_name=data['operation_name'],
            trace_id=data.get('trace_id'),
            parent_span_id=data.get('parent_span_id'),
            service=data.get('service', 'default'),
            tags=data.get('tags', {}),
        )

    def finish_span(self, span_id: str, data: Dict[str, Any]) -> bool:
        """Finish an existing span. Returns True on success."""
        return self._core.finish_span(
            span_id=span_id,
            status=data.get('status', 'success'),
            logs=data.get('logs', []),
            context=data.get('context', {}),
        )

    def get_trace(self, trace_id: str) -> List[TraceSpan]:
        """Return all spans for a trace_id."""
        return self._core.get_trace(trace_id)

    def get_trace_tree(self, trace_id: str) -> Dict[str, Any]:
        """Return the trace as a nested tree."""
        return self._core.get_trace_tree(trace_id)

    def get_slow_traces(self, threshold_ms: float = 5000, hours: int = 24) -> List[TraceSpan]:
        """Return spans exceeding the duration threshold."""
        return self._core.get_slow_traces(threshold_ms=threshold_ms, hours=hours)

    def get_error_traces(self, hours: int = 24) -> List[TraceSpan]:
        """Return error spans."""
        return self._core.get_error_traces(hours=hours)

    def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Return trace statistics."""
        return self._core.get_trace_statistics(hours=hours)


# ---------------------------------------------------------------------------
# Health Logic
# ---------------------------------------------------------------------------

class HealthLogic:
    """
    Canonical business logic for health status operations.
    """

    def upsert(self, data: Dict[str, Any]):
        """
        Create-or-update a health record.
        This is idempotent — safe to call on every health-check cycle.
        """
        obj, created = HealthStatus.objects.update_or_create(
            service_name=data['service_name'],
            component_name=data.get('component_name', ''),
            environment=data.get('environment', 'production'),
            defaults={
                'status':          data.get('status', 'unknown'),
                'health_score':    data.get('health_score', 100),
                'uptime':          data.get('uptime', 0.0),
                'response_time_ms': data.get('response_time_ms'),
                'error_rate':      data.get('error_rate', 0.0),
                'metadata':        data.get('metadata', {}),
            },
        )
        return obj, created


# ---------------------------------------------------------------------------
# Dashboard Logic
# ---------------------------------------------------------------------------

class DashboardLogic:
    """
    Canonical business logic for dashboard widget operations.
    """

    def create_widget(self, data: Dict[str, Any]) -> DashboardWidget:
        """Create a dashboard widget."""
        return DashboardWidget.objects.create(**data)

    def update_widget(self, widget_id: int, data: Dict[str, Any]) -> bool:
        """
        Update widget fields. Returns True if found, False otherwise.
        """
        updated = DashboardWidget.objects.filter(id=widget_id).update(**data)
        return updated > 0

    def delete_widget(self, widget_id: int) -> bool:
        """Delete a widget. Returns True if found, False otherwise."""
        deleted, _ = DashboardWidget.objects.filter(id=widget_id).delete()
        return deleted > 0

    def get_widget(self, widget_id: int) -> Optional[DashboardWidget]:
        """Return a widget or None."""
        return DashboardWidget.objects.filter(id=widget_id).first()

    def get_widgets(
        self,
        dashboard_id: Optional[int] = None,
        widget_type: Optional[str] = None,
        data_source: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[DashboardWidget]:
        """Filter and return widgets."""
        qs = DashboardWidget.objects.all()
        if dashboard_id is not None:
            qs = qs.filter(dashboard_id=dashboard_id)
        if widget_type:
            qs = qs.filter(widget_type=widget_type)
        if data_source:
            qs = qs.filter(data_source=data_source)
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        return list(qs.order_by('position_y', 'position_x'))
