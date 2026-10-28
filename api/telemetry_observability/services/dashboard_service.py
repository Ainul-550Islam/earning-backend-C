"""
DashboardService — thin facade over logic.DashboardLogic.

DRY RULE: Zero business logic here.
All CRUD logic lives in logic.DashboardLogic.
Only get_widget_data() lives here — it orchestrates multiple data sources
and belongs at the service layer, not in logic.py.
"""
from typing import Any, Dict, List, Optional

from ..logic import DashboardLogic
from ..models.dashboard_widget import DashboardWidget


class DashboardService:
    """
    Public service interface for dashboard operations.
    CRUD delegates to DashboardLogic.
    Data retrieval (per-widget live data) is orchestrated here.
    """

    def __init__(self):
        self._logic = DashboardLogic()

    def create_widget(self, data: Dict[str, Any]) -> DashboardWidget:
        return self._logic.create_widget(data)

    def update_widget(self, widget_id: int, data: Dict[str, Any]) -> bool:
        return self._logic.update_widget(widget_id, data)

    def delete_widget(self, widget_id: int) -> bool:
        return self._logic.delete_widget(widget_id)

    def get_widget(self, widget_id: int) -> Optional[DashboardWidget]:
        return self._logic.get_widget(widget_id)

    def get_widgets(
        self,
        dashboard_id: Optional[int] = None,
        widget_type: Optional[str] = None,
        data_source: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[DashboardWidget]:
        return self._logic.get_widgets(
            dashboard_id=dashboard_id,
            widget_type=widget_type,
            data_source=data_source,
            is_active=is_active,
        )

    def get_widget_data(self, widget: DashboardWidget, hours: int = 24) -> Dict[str, Any]:
        """
        Retrieve live data for a widget based on its data_source and query config.
        This orchestration logic stays in the service layer (not in logic.py).
        """
        source    = widget.data_source
        query_cfg = widget.query or {}

        DATA_HANDLERS = {
            'metric': self._fetch_metric_data,
            'log':    self._fetch_log_data,
            'trace':  self._fetch_trace_data,
            'alert':  self._fetch_alert_data,
            'health': self._fetch_health_data,
        }

        handler = DATA_HANDLERS.get(source)
        if handler is None:
            return {'data_source': source, 'data': [], 'message': 'Custom data source'}

        return handler(query_cfg, hours)

    # ------------------------------------------------------------------
    # Private data fetchers — each delegates to the appropriate model
    # ------------------------------------------------------------------

    def _fetch_metric_data(self, query: Dict, hours: int) -> Dict[str, Any]:
        from ..metrics import MetricsCollector, MetricsAggregator
        from django.utils import timezone
        from datetime import timedelta

        name      = query.get('metric_name')
        interval  = query.get('interval', 'hour')
        since     = timezone.now() - timedelta(hours=hours)

        if name:
            data = MetricsAggregator().aggregate_by_time(name, interval, since)
        else:
            data = list(
                MetricsCollector().get_metrics(limit=100)
                .values('name', 'value', 'metric_type', 'timestamp')
            )
        return {'data_source': 'metric', 'data': data}

    def _fetch_log_data(self, query: Dict, hours: int) -> Dict[str, Any]:
        from ..models.log_entry import LogEntry
        from django.utils import timezone
        from datetime import timedelta

        since = timezone.now() - timedelta(hours=hours)
        qs    = LogEntry.objects.filter(timestamp__gte=since)
        level = query.get('level')
        if level:
            qs = qs.filter(level=level)
        data = list(qs.order_by('-timestamp')[:100].values('level', 'message', 'service', 'timestamp'))
        return {'data_source': 'log', 'data': data}

    def _fetch_trace_data(self, query: Dict, hours: int) -> Dict[str, Any]:
        from ..models.trace_span import TraceSpan
        from django.utils import timezone
        from datetime import timedelta

        since = timezone.now() - timedelta(hours=hours)
        qs    = TraceSpan.objects.filter(start_time__gte=since)
        data  = list(qs.order_by('-start_time')[:100].values('operation_name', 'duration_ms', 'status', 'service'))
        return {'data_source': 'trace', 'data': data}

    def _fetch_alert_data(self, query: Dict, hours: int) -> Dict[str, Any]:
        from ..models.alert import Alert
        from django.utils import timezone
        from datetime import timedelta

        since    = timezone.now() - timedelta(hours=hours)
        qs       = Alert.objects.filter(triggered_at__gte=since)
        severity = query.get('severity')
        if severity:
            qs = qs.filter(severity=severity)
        data = list(qs.order_by('-triggered_at')[:100].values('name', 'severity', 'status', 'service'))
        return {'data_source': 'alert', 'data': data}

    def _fetch_health_data(self, query: Dict, hours: int) -> Dict[str, Any]:
        from ..models.health_status import HealthStatus

        qs   = HealthStatus.objects.all()
        env  = query.get('environment')
        if env:
            qs = qs.filter(environment=env)
        data = list(qs.order_by('-last_check')[:100].values('service_name', 'status', 'health_score', 'last_check'))
        return {'data_source': 'health', 'data': data}
