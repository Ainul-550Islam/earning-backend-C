# api/rate_limit/metrics.py
"""
Metrics collection for rate limit module.
Re-exports from monitoring for backwards compatibility.
"""
from api.rate_limit.monitoring import MetricsCollector, Metric, MetricType

# Alias for test compatibility
RateLimitMetricsCollector = MetricsCollector

__all__ = [
    'RateLimitMetricsCollector',
    'MetricsCollector',
    'Metric',
    'MetricType',
]
