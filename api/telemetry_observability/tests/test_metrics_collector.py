"""
Metrics collector tests for Telemetry Observability.
"""
import pytest
from django.utils import timezone
from datetime import timedelta

from ..services.metrics_collector import MetricsCollectorService


@pytest.mark.django_db
class TestMetricsCollectorService:
    """Tests for MetricsCollectorService."""
    
    def test_collect_counter_metric(self):
        """Test collecting a counter metric."""
        service = MetricsCollectorService()
        
        metric = service.collect_metric({
            'name': 'test-counter',
            'metric_type': 'counter',
            'value': 1.0,
            'unit': 'count',
            'source': 'test',
            'service': 'test-service'
        })
        
        assert metric.name == 'test-counter'
        assert metric.metric_type == 'counter'
        assert metric.value == 1.0
    
    def test_collect_gauge_metric(self):
        """Test collecting a gauge metric."""
        service = MetricsCollectorService()
        
        metric = service.collect_metric({
            'name': 'test-gauge',
            'metric_type': 'gauge',
            'value': 123.45,
            'unit': 'ms',
            'source': 'test',
            'service': 'test-service'
        })
        
        assert metric.name == 'test-gauge'
        assert metric.metric_type == 'gauge'
        assert metric.value == 123.45
    
    def test_get_metrics_with_filters(self):
        """Test getting metrics with filters."""
        service = MetricsCollectorService()
        
        # Create some metrics
        service.collect_metric({
            'name': 'metric1',
            'metric_type': 'counter',
            'value': 1.0,
            'service': 'service1'
        })
        service.collect_metric({
            'name': 'metric2',
            'metric_type': 'gauge',
            'value': 2.0,
            'service': 'service2'
        })
        
        # Get filtered metrics
        metrics = service.get_metrics(service='service1')
        
        assert len(metrics) == 1
        assert metrics[0].service == 'service1'
    
    def test_get_metric_statistics(self):
        """Test getting metric statistics."""
        service = MetricsCollectorService()
        
        # Create some metrics
        for i in range(5):
            service.collect_metric({
                'name': 'test-metric',
                'metric_type': 'gauge',
                'value': float(i + 1),
                'service': 'test-service'
            })
        
        stats = service.get_metric_statistics('test-metric', hours=24)
        
        assert stats['metric_name'] == 'test-metric'
        assert stats['count'] == 5
        assert stats['avg'] == 3.0
