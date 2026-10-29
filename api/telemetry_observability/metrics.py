"""
Metrics collection for Telemetry Observability.
"""
from typing import Dict, Any, Optional, List
from django.utils import timezone

from .models.metric_event import MetricEvent
from .exceptions import MetricException, InvalidMetricTypeError


class MetricsCollector:
    """
    Collector for metrics.
    """
    
    def __init__(self):
        """
        Initialize the metrics collector.
        """
        pass
    
    def record_counter(
        self,
        name: str,
        value: float = 1.0,
        unit: str = "",
        labels: Optional[Dict[str, Any]] = None,
        source: str = "application",
        service: str = "default",
        environment: str = "production"
    ) -> MetricEvent:
        """
        Record a counter metric.
        
        Args:
            name: Metric name
            value: Metric value
            unit: Unit of measurement
            labels: Additional labels
            source: Source of the metric
            service: Service name
            environment: Environment name
            
        Returns:
            Created MetricEvent instance
        """
        return MetricEvent.objects.create(
            name=name,
            metric_type='counter',
            value=value,
            unit=unit,
            labels=labels or {},
            source=source,
            service=service,
            environment=environment
        )
    
    def record_gauge(
        self,
        name: str,
        value: float,
        unit: str = "",
        labels: Optional[Dict[str, Any]] = None,
        source: str = "application",
        service: str = "default",
        environment: str = "production"
    ) -> MetricEvent:
        """
        Record a gauge metric.
        
        Args:
            name: Metric name
            value: Metric value
            unit: Unit of measurement
            labels: Additional labels
            source: Source of the metric
            service: Service name
            environment: Environment name
            
        Returns:
            Created MetricEvent instance
        """
        return MetricEvent.objects.create(
            name=name,
            metric_type='gauge',
            value=value,
            unit=unit,
            labels=labels or {},
            source=source,
            service=service,
            environment=environment
        )
    
    def record_histogram(
        self,
        name: str,
        value: float,
        unit: str = "",
        labels: Optional[Dict[str, Any]] = None,
        source: str = "application",
        service: str = "default",
        environment: str = "production"
    ) -> MetricEvent:
        """
        Record a histogram metric.
        
        Args:
            name: Metric name
            value: Metric value
            unit: Unit of measurement
            labels: Additional labels
            source: Source of the metric
            service: Service name
            environment: Environment name
            
        Returns:
            Created MetricEvent instance
        """
        return MetricEvent.objects.create(
            name=name,
            metric_type='histogram',
            value=value,
            unit=unit,
            labels=labels or {},
            source=source,
            service=service,
            environment=environment
        )
    
    def record_summary(
        self,
        name: str,
        value: float,
        unit: str = "",
        labels: Optional[Dict[str, Any]] = None,
        source: str = "application",
        service: str = "default",
        environment: str = "production"
    ) -> MetricEvent:
        """
        Record a summary metric.
        
        Args:
            name: Metric name
            value: Metric value
            unit: Unit of measurement
            labels: Additional labels
            source: Source of the metric
            service: Service name
            environment: Environment name
            
        Returns:
            Created MetricEvent instance
        """
        return MetricEvent.objects.create(
            name=name,
            metric_type='summary',
            value=value,
            unit=unit,
            labels=labels or {},
            source=source,
            service=service,
            environment=environment
        )
    
    def get_metrics(
        self,
        name: Optional[str] = None,
        metric_type: Optional[str] = None,
        source: Optional[str] = None,
        service: Optional[str] = None,
        environment: Optional[str] = None,
        since: Optional[timezone.datetime] = None,
        limit: Optional[int] = None
    ) -> List[MetricEvent]:
        """
        Get metrics with optional filters.
        
        Args:
            name: Optional metric name filter
            metric_type: Optional metric type filter
            source: Optional source filter
            service: Optional service filter
            environment: Optional environment filter
            since: Optional start time filter
            limit: Optional max number of results (most recent first)
            
        Returns:
            List of MetricEvent instances
        """
        queryset = MetricEvent.objects.all()
        
        if name:
            queryset = queryset.filter(name=name)
        
        if metric_type:
            queryset = queryset.filter(metric_type=metric_type)
        
        if source:
            queryset = queryset.filter(source=source)
        
        if service:
            queryset = queryset.filter(service=service)
        
        if environment:
            queryset = queryset.filter(environment=environment)
        
        if since:
            queryset = queryset.filter(timestamp__gte=since)
        
        queryset = queryset.order_by('-timestamp')
        if limit is not None:
            queryset = queryset[:limit]
        return list(queryset)
    
    def get_metric_aggregation(
        self,
        name: str,
        metric_type: str,
        aggregation: str = 'avg',
        since: Optional[timezone.datetime] = None
    ) -> float:
        """
        Get aggregated metric value.
        
        Args:
            name: Metric name
            metric_type: Metric type
            aggregation: Aggregation type (avg, sum, min, max, count)
            since: Optional start time filter
            
        Returns:
            Aggregated value
        """
        from django.db.models import Avg, Sum, Min, Max, Count
        
        queryset = MetricEvent.objects.filter(name=name, metric_type=metric_type)
        
        if since:
            queryset = queryset.filter(timestamp__gte=since)
        
        aggregation_map = {
            'avg': Avg('value'),
            'sum': Sum('value'),
            'min': Min('value'),
            'max': Max('value'),
            'count': Count('value')
        }
        
        if aggregation not in aggregation_map:
            raise MetricException(f"Invalid aggregation: {aggregation}")
        
        result = queryset.aggregate(aggregation=aggregation_map[aggregation])
        return result['aggregation'] or 0.0


class MetricsAggregator:
    """
    Aggregator for metrics.
    """
    
    def __init__(self):
        """
        Initialize the metrics aggregator.
        """
        pass
    
    def aggregate_by_time(
        self,
        name: str,
        interval: str = 'hour',
        since: Optional[timezone.datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Aggregate metrics by time interval.
        
        Args:
            name: Metric name
            interval: Time interval (hour, day, week, month)
            since: Optional start time
            
        Returns:
            List of aggregated data points
        """
        from django.db.models import Avg, Count
        from django.db.models.functions import Trunc
        
        queryset = MetricEvent.objects.filter(name=name)
        
        if since:
            queryset = queryset.filter(timestamp__gte=since)
        
        # Truncate timestamp based on interval
        trunc_map = {
            'hour': Trunc('timestamp', 'hour'),
            'day': Trunc('timestamp', 'day'),
            'week': Trunc('timestamp', 'week'),
            'month': Trunc('timestamp', 'month')
        }
        
        if interval not in trunc_map:
            raise MetricException(f"Invalid interval: {interval}")
        
        aggregated = queryset.annotate(
            time_period=trunc_map[interval]
        ).values('time_period').annotate(
            avg_value=Avg('value'),
            count=Count('id')
        ).order_by('time_period')
        
        return [
            {
                'time_period': item['time_period'].isoformat() if item['time_period'] else None,
                'avg_value': item['avg_value'] or 0.0,
                'count': item['count']
            }
            for item in aggregated
        ]
    
    def aggregate_by_labels(
        self,
        name: str,
        label_key: str,
        since: Optional[timezone.datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Aggregate metrics by label.
        
        Args:
            name: Metric name
            label_key: Label key to aggregate by
            since: Optional start time
            
        Returns:
            List of aggregated data by label
        """
        from django.db.models import Avg, Count
        
        queryset = MetricEvent.objects.filter(name=name)
        
        if since:
            queryset = queryset.filter(timestamp__gte=since)
        
        # Filter by label and aggregate
        results = []
        for metric in queryset:
            if label_key in metric.labels:
                results.append({
                    'label_value': metric.labels[label_key],
                    'value': metric.value
                })
        
        # Aggregate by label value
        from collections import defaultdict
        aggregated = defaultdict(list)
        for item in results:
            aggregated[item['label_value']].append(item['value'])
        
        return [
            {
                'label_value': label,
                'avg_value': sum(values) / len(values) if values else 0.0,
                'count': len(values)
            }
            for label, values in aggregated.items()
        ]
