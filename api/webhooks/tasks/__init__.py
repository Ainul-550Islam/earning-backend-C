# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhooks Tasks Package
tasks/__init__.py

FIX APPLIED:
    - Added import for integration_sync_tasks (new — was missing entirely)
    - Added import for distributed_lock utilities
    - All task names match their @shared_task(name=...) declarations

Beat schedule entries (add to your celery.py CELERY_BEAT_SCHEDULE):

    # Core
    "webhooks-retry-failed":           retry_failed_dispatch           every 5 min
    "webhooks-auto-suspend":           auto_suspend_endpoints          every 1 hour
    "webhooks-reap-exhausted":         reap_exhausted_logs             every 12 hours

    # Aging
    "webhooks-aging-sweep":            aging_full_sweep                every 6 hours
    "webhooks-aging-archive":          aging_archive_due               every 12 hours
    "webhooks-aging-purge-dry":        aging_purge_dry_run             daily
    "webhooks-aging-purge-exec":       aging_purge_execute             weekly

    # Health
    "webhooks-health-check":           health_check_all_endpoints      every 1 hour

    # Analytics
    "webhooks-analytics-daily":        generate_daily_analytics_all_endpoints   daily
    "webhooks-event-stats":            generate_event_statistics_all_endpoints  daily
    "webhooks-perf-metrics":           calculate_performance_metrics_all_endpoints  daily

    # Rate limiting
    "webhooks-rate-limit-reset":       reset_rate_limits               hourly
    "webhooks-rate-limit-cleanup":     cleanup_expired_rate_limits     daily

    # Cleanup
    "webhooks-cleanup-logs":           cleanup_all_old_data            weekly

    # Integration (enable in settings: WEBHOOKS['INTEGRATION_ENABLED'] = True)
    "webhooks-integration-sync":       sync_all_endpoints_with_integration  every 6 hours
"""

# ── Core tasks ────────────────────────────────────────────────────────────────
from .retry_failed_dispatch import retry_failed_dispatch
from .dispatch_event import dispatch_event
from .reap_exhausted_logs import reap_exhausted_logs
from .auto_suspend_endpoints import auto_suspend_endpoints

# ── Health tasks ──────────────────────────────────────────────────────────────
from .health_check_tasks import (
    health_check_all_endpoints,
    health_check_endpoint,
)

# ── Aging tasks ───────────────────────────────────────────────────────────────
from .aging_tasks import (
    aging_full_sweep,
    aging_archive_due,
    aging_purge_dry_run,
    aging_purge_execute,
    aging_evaluate_endpoint,
)

# ── Analytics tasks ───────────────────────────────────────────────────────────
from .analytics_tasks import (
    generate_daily_analytics,
    generate_daily_analytics_all_endpoints,
    generate_event_statistics,
    generate_event_statistics_all_endpoints,
    calculate_performance_metrics,
    calculate_performance_metrics_all_endpoints,
)

# ── Rate-limit tasks ──────────────────────────────────────────────────────────
from .rate_limit_reset_tasks import (
    reset_rate_limits,
    reset_rate_limit,
    cleanup_expired_rate_limits,
)

# ── Replay tasks ──────────────────────────────────────────────────────────────
from .replay_tasks import (
    process_replay,
    process_replay_batch,
    create_replay_batch,
    cleanup_old_replays,
    cleanup_old_replay_batches,
)

# ── Cleanup tasks ─────────────────────────────────────────────────────────────
from .cleanup_tasks import (
    cleanup_old_delivery_logs,
    cleanup_old_health_logs,
    cleanup_old_analytics,
    cleanup_all_old_data,
    archive_old_data,
)

# ── Integration sync tasks (NEW) ──────────────────────────────────────────────
from .integration_sync_tasks import (
    sync_all_endpoints_with_integration,
    sync_single_endpoint_with_integration,
)

# ── Batch tasks (NEW — was imported but never existed, see batch_tasks.py) ────
from .batch_tasks import process_batch

# ── Lock utility (importable for custom tasks) ────────────────────────────────
from .distributed_lock import DistributedLock, LockNotAcquired

__all__ = [
    # Core
    "retry_failed_dispatch", "dispatch_event",
    "reap_exhausted_logs", "auto_suspend_endpoints",
    # Health
    "health_check_all_endpoints", "health_check_endpoint",
    # Aging
    "aging_full_sweep", "aging_archive_due",
    "aging_purge_dry_run", "aging_purge_execute", "aging_evaluate_endpoint",
    # Analytics
    "generate_daily_analytics", "generate_daily_analytics_all_endpoints",
    "generate_event_statistics", "generate_event_statistics_all_endpoints",
    "calculate_performance_metrics", "calculate_performance_metrics_all_endpoints",
    # Rate limiting
    "reset_rate_limits", "reset_rate_limit", "cleanup_expired_rate_limits",
    # Replay
    "process_replay", "process_replay_batch", "create_replay_batch",
    "cleanup_old_replays", "cleanup_old_replay_batches",
    # Cleanup
    "cleanup_old_delivery_logs", "cleanup_old_health_logs",
    "cleanup_old_analytics", "cleanup_all_old_data", "archive_old_data",
    # Integration (NEW)
    "sync_all_endpoints_with_integration", "sync_single_endpoint_with_integration",
    # Batch (NEW)
    "process_batch",
    # Lock
    "DistributedLock", "LockNotAcquired",
]
