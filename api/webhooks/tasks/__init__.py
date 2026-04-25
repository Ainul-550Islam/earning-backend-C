"""Webhooks Tasks Configuration

This module contains the configuration for all webhook-related background tasks.
"""

from .retry_failed_dispatch import retry_failed_dispatch
from .dispatch_event import dispatch_event
from .reap_exhausted_logs import reap_exhausted_logs
from .auto_suspend_endpoints import auto_suspend_endpoints
from .health_check_tasks import health_check_all_endpoints, health_check_endpoint
from .analytics_tasks import (
    generate_daily_analytics,
    generate_daily_analytics_all_endpoints,
    generate_event_statistics,
    generate_event_statistics_all_endpoints,
    calculate_performance_metrics,
    calculate_performance_metrics_all_endpoints
)
from .rate_limit_reset_tasks import reset_rate_limits, reset_rate_limit, cleanup_expired_rate_limits
from .replay_tasks import (
    process_replay,
    process_replay_batch,
    create_replay_batch,
    cleanup_old_replays,
    cleanup_old_replay_batches
)
from .cleanup_tasks import (
    cleanup_old_delivery_logs,
    cleanup_old_health_logs,
    cleanup_old_analytics,
    cleanup_all_old_data,
    archive_old_data
)

__all__ = [
    # Existing tasks (kept from tasks.py)
    'retry_failed_dispatch',
    'dispatch_event',
    'reap_exhausted_logs',
    'auto_suspend_endpoints',
    
    # New tasks
    'health_check_all_endpoints',
    'health_check_endpoint',
    'generate_daily_analytics',
    'generate_daily_analytics_all_endpoints',
    'generate_event_statistics',
    'generate_event_statistics_all_endpoints',
    'calculate_performance_metrics',
    'calculate_performance_metrics_all_endpoints',
    'reset_rate_limits',
    'reset_rate_limit',
    'cleanup_expired_rate_limits',
    'process_replay',
    'process_replay_batch',
    'create_replay_batch',
    'cleanup_old_replays',
    'cleanup_old_replay_batches',
    'cleanup_old_delivery_logs',
    'cleanup_old_health_logs',
    'cleanup_old_analytics',
    'cleanup_all_old_data',
    'archive_old_data',
]
