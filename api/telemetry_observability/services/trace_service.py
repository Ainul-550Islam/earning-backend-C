"""
TraceService — thin facade over logic.TraceLogic.

DRY RULE: Zero business logic here.
All implementation lives in logic.TraceLogic → tracing.TracingService.
"""
from typing import Any, Dict, List, Optional

from ..logic import TraceLogic
from ..models.trace_span import TraceSpan
from ..decorators import trace_operation


class TraceService:
    """
    Public service interface for trace operations.
    All methods delegate to TraceLogic — never re-implemented here.
    """

    def __init__(self):
        self._logic = TraceLogic()

    @trace_operation(service='trace-service', operation_name='start_trace')
    def start_trace(self, data: Dict[str, Any]) -> TraceSpan:
        """Start a new trace span. Delegates to TraceLogic."""
        return self._logic.start_span(data)

    def finish_trace(self, span_id: str, data: Dict[str, Any]) -> bool:
        """Finish a span. Returns True on success."""
        return self._logic.finish_span(span_id, data)

    def get_trace(self, trace_id: str) -> List[TraceSpan]:
        """Return all spans for a trace_id."""
        return self._logic.get_trace(trace_id)

    def get_trace_tree(self, trace_id: str) -> Dict[str, Any]:
        """Return the full trace as a nested tree."""
        return self._logic.get_trace_tree(trace_id)

    def get_slow_traces(self, threshold_ms: float = 5000, hours: int = 24) -> List[TraceSpan]:
        """Return spans exceeding the duration threshold."""
        return self._logic.get_slow_traces(threshold_ms=threshold_ms, hours=hours)

    def get_error_traces(self, hours: int = 24) -> List[TraceSpan]:
        """Return error-status spans."""
        return self._logic.get_error_traces(hours=hours)

    def get_trace_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Return aggregate trace statistics."""
        return self._logic.get_statistics(hours=hours)
