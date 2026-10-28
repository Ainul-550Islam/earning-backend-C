"""
Distributed tracing for Telemetry Observability.
"""
from typing import Dict, Any, Optional, List
from django.utils import timezone
import uuid

from .models.trace_span import TraceSpan
from .exceptions import TraceException


class TracingService:
    """
    Service for distributed tracing.
    """
    
    def __init__(self):
        """
        Initialize the tracing service.
        """
        pass
    
    def start_span(
        self,
        operation_name: str,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        service: str = "default",
        tags: Optional[Dict[str, Any]] = None
    ) -> TraceSpan:
        """
        Start a new trace span.
        
        Args:
            operation_name: Name of the operation
            trace_id: Optional trace ID (generates new if not provided)
            parent_span_id: Optional parent span ID
            service: Service name
            tags: Optional tags
            
        Returns:
            Created TraceSpan instance
        """
        if not trace_id:
            trace_id = str(uuid.uuid4())
        
        span_id = str(uuid.uuid4())
        start_time = timezone.now()
        
        return TraceSpan.objects.create(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            service=service,
            start_time=start_time,
            status='success',
            tags=tags or {}
        )
    
    def finish_span(
        self,
        span_id: str,
        status: str = 'success',
        logs: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Finish a trace span.
        
        Args:
            span_id: Span ID
            status: Status of the span
            logs: Optional logs
            context: Optional context
            
        Returns:
            True if successful
        """
        try:
            span = TraceSpan.objects.get(span_id=span_id)
            end_time = timezone.now()
            
            # Calculate duration
            duration_ms = (end_time - span.start_time).total_seconds() * 1000
            
            span.end_time = end_time
            span.duration_ms = duration_ms
            span.status = status
            span.logs = logs or []
            span.context = context or {}
            span.save(update_fields=['end_time', 'duration_ms', 'status', 'logs', 'context'])
            
            return True
        except TraceSpan.DoesNotExist:
            return False
    
    def get_trace(self, trace_id: str) -> List[TraceSpan]:
        """
        Get all spans for a trace.
        
        Args:
            trace_id: Trace ID
            
        Returns:
            List of TraceSpan instances
        """
        return list(TraceSpan.objects.filter(trace_id=trace_id).order_by('start_time'))
    
    def get_span(self, span_id: str) -> Optional[TraceSpan]:
        """
        Get a specific span.
        
        Args:
            span_id: Span ID
            
        Returns:
            TraceSpan instance or None
        """
        try:
            return TraceSpan.objects.get(span_id=span_id)
        except TraceSpan.DoesNotExist:
            return None
    
    def get_service_traces(
        self,
        service: str,
        since: Optional[timezone.datetime] = None
    ) -> List[TraceSpan]:
        """
        Get traces for a specific service.
        
        Args:
            service: Service name
            since: Optional start time filter
            
        Returns:
            List of TraceSpan instances
        """
        queryset = TraceSpan.objects.filter(service=service)
        
        if since:
            queryset = queryset.filter(start_time__gte=since)
        
        return list(queryset.order_by('-start_time'))
    
    def get_trace_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get trace statistics for the last N hours.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Dictionary with trace statistics
        """
        since = timezone.now() - timezone.timedelta(hours=hours)
        
        total_spans = TraceSpan.objects.filter(start_time__gte=since).count()
        success_spans = TraceSpan.objects.filter(
            start_time__gte=since,
            status='success'
        ).count()
        error_spans = TraceSpan.objects.filter(
            start_time__gte=since,
            status='error'
        ).count()
        
        # Calculate average duration
        from django.db.models import Avg
        avg_duration = TraceSpan.objects.filter(
            start_time__gte=since,
            duration_ms__isnull=False
        ).aggregate(avg=Avg('duration_ms'))['avg'] or 0.0
        
        return {
            'period_hours': hours,
            'total_spans': total_spans,
            'success_spans': success_spans,
            'error_spans': error_spans,
            'error_rate': round((error_spans / total_spans * 100) if total_spans > 0 else 0, 2),
            'avg_duration_ms': round(avg_duration, 2)
        }


class TraceContext:
    """
    Context for a trace.
    """
    
    def __init__(self, trace_id: str, span_id: str):
        """
        Initialize the trace context.
        
        Args:
            trace_id: Trace ID
            span_id: Span ID
        """
        self.trace_id = trace_id
        self.span_id = span_id
        self.baggage: Dict[str, Any] = {}
    
    def add_baggage(self, key: str, value: Any):
        """
        Add baggage to the trace context.
        
        Args:
            key: Baggage key
            value: Baggage value
        """
        self.baggage[key] = value
    
    def get_baggage(self, key: str, default: Any = None) -> Any:
        """
        Get baggage value.
        
        Args:
            key: Baggage key
            default: Default value if key not found
            
        Returns:
            Baggage value or default
        """
        return self.baggage.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert trace context to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            'trace_id': self.trace_id,
            'span_id': self.span_id,
            'baggage': self.baggage
        }


class TraceDecorator:
    """
    Decorator for tracing function calls.
    """
    
    def __init__(self, service: str = "default"):
        """
        Initialize the trace decorator.
        
        Args:
            service: Service name
        """
        self.service = service
        self.tracing_service = TracingService()
    
    def __call__(self, func):
        """
        Decorator function.
        
        Args:
            func: Function to decorate
            
        Returns:
            Wrapped function
        """
        def wrapper(*args, **kwargs):
            # Start span
            span = self.tracing_service.start_span(
                operation_name=func.__name__,
                service=self.service
            )
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Finish span with success
                self.tracing_service.finish_span(span.span_id, status='success')
                
                return result
            except Exception as e:
                # Finish span with error
                self.tracing_service.finish_span(
                    span.span_id,
                    status='error',
                    logs=[{'error': str(e)}]
                )
                raise
        
        return wrapper


def trace(service: str = "default"):
    """
    Decorator for tracing function calls.
    
    Args:
        service: Service name
        
    Returns:
        Decorator function
    """
    return TraceDecorator(service)
