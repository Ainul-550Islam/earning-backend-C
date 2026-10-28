"""
MetricsCollectorService — thin facade over logic.MetricLogic.

DRY RULE: This class contains NO business logic of its own.
It delegates EVERYTHING to logic.MetricLogic.
Views/ViewSets call this; they never call logic.py directly.
"""
from typing import Any, Dict, List, Optional

from ..logic import MetricLogic
from ..models.metric_event import MetricEvent
from ..decorators import record_metric, trace_operation


class MetricsCollectorService:
    """
    Public service interface for metric operations.
    One method per use-case; all implementation in logic.py.
    """

    def __init__(self):
        self._logic = MetricLogic()

    @trace_operation(service='metrics-service', operation_name='collect_metric')
    def collect_metric(self, data: Dict[str, Any]) -> MetricEvent:
        """
        Record a single metric event.
        Delegates to MetricLogic.record_metric() — no duplication.
        """
        return self._logic.record_metric(data)

    def batch_collect_metrics(self, data_list: List[Dict[str, Any]]) -> List[MetricEvent]:
        """Batch-record multiple metrics."""
        return self._logic.batch_record(data_list)

    def get_metrics(
        self,
        name: Optional[str] = None,
        metric_type: Optional[str] = None,
        source: Optional[str] = None,
        service: Optional[str] = None,
        environment: Optional[str] = None,
        limit: int = 100,
        since=None,
    ) -> List[MetricEvent]:
        """Filter and return metric events."""
        return self._logic.get_metrics(
            name=name,
            metric_type=metric_type,
            source=source,
            service=service,
            environment=environment,
            limit=limit,
        )

    def get_metric_statistics(self, name: str, hours: int = 24) -> Dict[str, Any]:
        """Return aggregate statistics for a metric name."""
        return self._logic.get_statistics(name, hours=hours)

    def aggregate_by_time(self, name: str, interval: str, since) -> list:
        """Delegate time-series aggregation to MetricLogic."""
        return self._logic.aggregate_by_time(name, interval, since)
