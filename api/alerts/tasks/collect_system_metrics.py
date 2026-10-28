"""
collect_system_metrics — Celery task that runs every minute to collect
CPU, memory, disk, network, and application-level metrics and persist
them to SystemMetrics.
"""
import logging
import time
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_os_metrics() -> dict:
    """
    Collect OS-level metrics using psutil (optional dependency).
    Returns zeros if psutil is not installed so the task never crashes.
    """
    try:
        import psutil

        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net_io = psutil.net_io_counters()

        return {
            'cpu_usage_percent': cpu,
            'memory_usage_percent': mem.percent,
            'memory_used_mb': mem.used / (1024 ** 2),
            'memory_total_mb': mem.total / (1024 ** 2),
            'disk_usage_percent': disk.percent,
            'disk_used_gb': disk.used / (1024 ** 3),
            'disk_total_gb': disk.total / (1024 ** 3),
            'network_bytes_sent': net_io.bytes_sent,
            'network_bytes_recv': net_io.bytes_recv,
            'network_io': {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv,
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv,
                'errin': net_io.errin,
                'errout': net_io.errout,
                'dropin': net_io.dropin,
                'dropout': net_io.dropout,
            },
        }
    except ImportError:
        logger.debug("psutil not installed — OS metrics will be zero")
        return {
            'cpu_usage_percent': 0.0,
            'memory_usage_percent': 0.0,
            'memory_used_mb': 0.0,
            'memory_total_mb': 0.0,
            'disk_usage_percent': 0.0,
            'disk_used_gb': 0.0,
            'disk_total_gb': 0.0,
            'network_bytes_sent': 0,
            'network_bytes_recv': 0,
            'network_io': {},
        }
    except Exception as e:
        logger.error(f"_collect_os_metrics error: {e}")
        return {}


def _collect_db_metrics() -> dict:
    """
    Collect Django DB connection pool stats.
    Works with django-db-geventpool or falls back to a simple query count.
    """
    try:
        from django.db import connections
        db_connections = 0
        for alias in connections:
            conn = connections[alias]
            # Force a connection so we can inspect it
            conn.ensure_connection()
            db_connections += 1
        return {'db_connections': db_connections}
    except Exception as e:
        logger.debug(f"_collect_db_metrics: {e}")
        return {'db_connections': 0}


def _collect_redis_metrics() -> dict:
    """
    Collect Redis memory usage via django-redis or direct redis-py.
    """
    try:
        from django.core.cache import cache
        # django-redis exposes get_client()
        client = cache.client.get_client()
        info = client.info('memory')
        used_memory_mb = info.get('used_memory', 0) / (1024 ** 2)
        return {'redis_memory_mb': round(used_memory_mb, 2)}
    except Exception:
        try:
            import redis as redis_lib
            from django.conf import settings
            cache_url = getattr(settings, 'CACHES', {}).get('default', {}).get('LOCATION', '')
            if cache_url:
                r = redis_lib.from_url(cache_url)
                info = r.info('memory')
                used_memory_mb = info.get('used_memory', 0) / (1024 ** 2)
                return {'redis_memory_mb': round(used_memory_mb, 2)}
        except Exception:
            pass
        return {'redis_memory_mb': 0.0}


def _collect_app_metrics() -> dict:
    """
    Collect application-level metrics from the alerts models.
    Counts users, active sessions, recent alert activity, etc.
    """
    try:
        from django.contrib.auth import get_user_model
        from django.utils import timezone as tz
        from datetime import timedelta
        from ..models.core import AlertLog, AlertRule, SystemHealthCheck

        User = get_user_model()
        now = tz.now()
        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(hours=24)

        total_users = User.objects.count()
        # Active users: users who have logged in within the last hour
        # (requires last_login field on User model)
        try:
            active_users_1h = User.objects.filter(
                last_login__gte=one_hour_ago
            ).count()
            active_users_24h = User.objects.filter(
                last_login__gte=one_day_ago
            ).count()
        except Exception:
            active_users_1h = 0
            active_users_24h = 0

        # Alert activity
        alerts_1h = AlertLog.objects.filter(triggered_at__gte=one_hour_ago).count()
        unresolved_alerts = AlertLog.objects.filter(is_resolved=False).count()
        active_rules = AlertRule.objects.filter(is_active=True).count()

        # Average response time from SystemHealthCheck
        avg_response_time_ms = 0.0
        try:
            from django.db.models import Avg
            result = SystemHealthCheck.objects.filter(
                checked_at__gte=one_hour_ago
            ).aggregate(avg=Avg('response_time_ms'))
            avg_response_time_ms = result['avg'] or 0.0
        except Exception:
            pass

        return {
            'total_users': total_users,
            'active_users_1h': active_users_1h,
            'active_users_24h': active_users_24h,
            'alerts_last_1h': alerts_1h,
            'unresolved_alerts': unresolved_alerts,
            'active_rules': active_rules,
            'avg_response_time_ms': round(avg_response_time_ms, 2),
        }
    except Exception as e:
        logger.error(f"_collect_app_metrics error: {e}")
        return {
            'total_users': 0,
            'active_users_1h': 0,
            'active_users_24h': 0,
            'alerts_last_1h': 0,
            'unresolved_alerts': 0,
            'active_rules': 0,
            'avg_response_time_ms': 0.0,
        }


def _collect_celery_metrics() -> dict:
    """
    Collect Celery queue depth and worker count if inspect is available.
    """
    try:
        from celery import current_app
        inspect = current_app.control.inspect(timeout=2)
        active = inspect.active() or {}
        reserved = inspect.reserved() or {}

        worker_count = len(active)
        active_tasks = sum(len(v) for v in active.values())
        queued_tasks = sum(len(v) for v in reserved.values())

        return {
            'celery_worker_count': worker_count,
            'celery_active_tasks': active_tasks,
            'celery_queued_tasks': queued_tasks,
        }
    except Exception:
        return {
            'celery_worker_count': 0,
            'celery_active_tasks': 0,
            'celery_queued_tasks': 0,
        }


# ---------------------------------------------------------------------------
# Main task
# ---------------------------------------------------------------------------

@shared_task(
    name='alerts.collect_system_metrics',
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    soft_time_limit=55,   # must finish within 1-minute schedule window
    time_limit=60,
)
def collect_system_metrics(self):
    """
    Collect all system metrics and persist to SystemMetrics model.

    Scheduled to run every 1 minute via Celery Beat.
    Celery Beat config example:
        CELERY_BEAT_SCHEDULE = {
            'collect-system-metrics': {
                'task': 'alerts.collect_system_metrics',
                'schedule': 60.0,  # every 60 seconds
            },
        }

    Returns:
        dict with the metrics snapshot that was saved, or None on failure.
    """
    start = time.monotonic()
    try:
        from ..models.core import SystemMetrics

        # Gather all metric groups
        os_metrics = _collect_os_metrics()
        db_metrics = _collect_db_metrics()
        redis_metrics = _collect_redis_metrics()
        app_metrics = _collect_app_metrics()
        celery_metrics = _collect_celery_metrics()

        # Merge into a single flat dict
        snapshot = {
            **os_metrics,
            **db_metrics,
            **redis_metrics,
            **app_metrics,
            **celery_metrics,
            'data_source': 'auto',
            'timestamp': timezone.now(),
        }

        # Build the details JSON (everything that doesn't map to a model field)
        details = {
            'celery': celery_metrics,
            'network_io': os_metrics.get('network_io', {}),
            'memory_detail': {
                'used_mb': os_metrics.get('memory_used_mb', 0),
                'total_mb': os_metrics.get('memory_total_mb', 0),
            },
            'disk_detail': {
                'used_gb': os_metrics.get('disk_used_gb', 0),
                'total_gb': os_metrics.get('disk_total_gb', 0),
            },
            'collection_duration_ms': round((time.monotonic() - start) * 1000, 2),
        }

        # Persist — only pass fields that exist on the model
        metrics_obj = SystemMetrics.objects.create(
            cpu_usage_percent=snapshot.get('cpu_usage_percent', 0.0),
            memory_usage_percent=snapshot.get('memory_usage_percent', 0.0),
            disk_usage_percent=snapshot.get('disk_usage_percent', 0.0),
            network_io=snapshot.get('network_io', {}),
            total_users=snapshot.get('total_users', 0),
            active_users_1h=snapshot.get('active_users_1h', 0),
            active_users_24h=snapshot.get('active_users_24h', 0),
            avg_response_time_ms=snapshot.get('avg_response_time_ms', 0.0),
            data_source='auto',
            details=details,
        )

        elapsed_ms = round((time.monotonic() - start) * 1000, 2)
        logger.info(
            f"collect_system_metrics: saved SystemMetrics id={metrics_obj.id} "
            f"cpu={snapshot.get('cpu_usage_percent', 0):.1f}% "
            f"mem={snapshot.get('memory_usage_percent', 0):.1f}% "
            f"elapsed={elapsed_ms}ms"
        )

        # Trigger alert rules that watch system metrics (e.g. high CPU)
        _check_system_metric_thresholds(snapshot)

        return {
            'metrics_id': metrics_obj.id,
            'cpu_usage_percent': snapshot.get('cpu_usage_percent', 0),
            'memory_usage_percent': snapshot.get('memory_usage_percent', 0),
            'disk_usage_percent': snapshot.get('disk_usage_percent', 0),
            'elapsed_ms': elapsed_ms,
        }

    except Exception as exc:
        logger.error(f"collect_system_metrics failed: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.critical("collect_system_metrics: max retries exceeded")
            return None


# ---------------------------------------------------------------------------
# Threshold check helper
# ---------------------------------------------------------------------------

def _check_system_metric_thresholds(snapshot: dict) -> None:
    """
    Compare collected metrics against active AlertRule thresholds for
    server_down / high CPU / high memory alert types and fire alerts
    if thresholds are breached.
    """
    try:
        from ..models.core import AlertRule
        from ..services.core import LegacyAlertProcessorService as AlertProcessorService

        # Map metric keys to alert types
        metric_alert_map = [
            ('cpu_usage_percent', 'server_error'),
            ('memory_usage_percent', 'server_error'),
            ('disk_usage_percent', 'server_error'),
        ]

        for metric_key, alert_type in metric_alert_map:
            value = snapshot.get(metric_key)
            if value is None:
                continue

            rules = AlertRule.objects.filter(
                alert_type=alert_type,
                is_active=True,
            )
            for rule in rules:
                if value >= rule.threshold_value and rule.can_trigger_now():
                    AlertProcessorService.process_alert(
                        rule_id=rule.id,
                        trigger_value=value,
                        message=(
                            f"System metric '{metric_key}' is {value:.1f}% "
                            f"(threshold: {rule.threshold_value}%)"
                        ),
                        details={
                            'metric_key': metric_key,
                            'metric_value': value,
                            'snapshot': {
                                k: v for k, v in snapshot.items()
                                if k not in ('network_io', 'timestamp')
                            },
                        },
                    )
    except Exception as e:
        logger.error(f"_check_system_metric_thresholds error: {e}")
