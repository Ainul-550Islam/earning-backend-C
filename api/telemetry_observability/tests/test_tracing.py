"""
Tracing tests for Telemetry Observability.
"""
import pytest
from django.utils import timezone
from datetime import timedelta

from ..services.trace_service import TraceService
from ..tracing import TracingService, TraceContext


@pytest.mark.django_db
class TestTraceService:
    """Tests for TraceService."""
    
    def test_start_trace(self):
        """Test starting a trace."""
        service = TraceService()
        
        trace = service.start_trace({
            'operation_name': 'test-operation',
            'service': 'test-service'
        })
        
        assert trace.operation_name == 'test-operation'
        assert trace.service == 'test-service'
        assert trace.status == 'success'
    
    def test_finish_trace(self):
        """Test finishing a trace."""
        service = TraceService()
        
        trace = service.start_trace({
            'operation_name': 'test-operation',
            'service': 'test-service'
        })
        
        service.finish_trace(trace.span_id, {'status': 'success'})
        
        trace.refresh_from_db()
        assert trace.status == 'success'
        assert trace.end_time is not None
        assert trace.duration_ms is not None
    
    def test_get_trace(self):
        """Test getting a trace."""
        service = TraceService()
        
        trace = service.start_trace({
            'operation_name': 'test-operation',
            'service': 'test-service'
        })
        
        traces = service.get_trace(trace.trace_id)
        
        assert len(traces) == 1
        assert traces[0].span_id == trace.span_id
    
    def test_get_trace_tree(self):
        """Test getting a trace tree."""
        service = TraceService()
        
        # Create parent span
        parent = service.start_trace({
            'operation_name': 'parent-operation',
            'service': 'test-service'
        })
        
        # Create child span
        child = service.start_trace({
            'operation_name': 'child-operation',
            'service': 'test-service',
            'trace_id': parent.trace_id,
            'parent_span_id': parent.span_id
        })
        
        tree = service.get_trace_tree(parent.trace_id)
        
        assert tree['trace_id'] == parent.trace_id
        assert tree['total_spans'] == 2


@pytest.mark.django_db
class TestTracingService:
    """Tests for TracingService."""
    
    def test_start_span(self):
        """Test starting a span."""
        service = TracingService()
        
        span = service.start_span(
            operation_name='test-operation',
            service='test-service'
        )
        
        assert span.operation_name == 'test-operation'
        assert span.service == 'test-service'
        assert span.status == 'success'
    
    def test_finish_span(self):
        """Test finishing a span."""
        service = TracingService()
        
        span = service.start_span(
            operation_name='test-operation',
            service='test-service'
        )
        
        service.finish_span(span.span_id, status='success')
        
        span.refresh_from_db()
        assert span.status == 'success'
        assert span.end_time is not None
    
    def test_get_trace_statistics(self):
        """Test getting trace statistics."""
        service = TracingService()
        
        # Create some traces
        for i in range(5):
            span = service.start_span(
                operation_name=f'operation-{i}',
                service='test-service'
            )
            service.finish_span(span.span_id, status='success')
        
        stats = service.get_trace_statistics(hours=24)
        
        assert 'total_spans' in stats
        assert 'success_spans' in stats
        assert 'error_spans' in stats


@pytest.mark.django_db
class TestTraceContext:
    """Tests for TraceContext."""
    
    def test_create_context(self):
        """Test creating a trace context."""
        context = TraceContext('trace-id-123', 'span-id-456')
        
        assert context.trace_id == 'trace-id-123'
        assert context.span_id == 'span-id-456'
    
    def test_add_baggage(self):
        """Test adding baggage to context."""
        context = TraceContext('trace-id-123', 'span-id-456')
        
        context.add_baggage('key1', 'value1')
        context.add_baggage('key2', 'value2')
        
        assert context.get_baggage('key1') == 'value1'
        assert context.get_baggage('key2') == 'value2'
    
    def test_to_dict(self):
        """Test converting context to dictionary."""
        context = TraceContext('trace-id-123', 'span-id-456')
        context.add_baggage('key1', 'value1')
        
        context_dict = context.to_dict()
        
        assert context_dict['trace_id'] == 'trace-id-123'
        assert context_dict['span_id'] == 'span-id-456'
        assert context_dict['baggage']['key1'] == 'value1'
