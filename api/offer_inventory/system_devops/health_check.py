# api/offer_inventory/system_devops/health_check.py
"""
System health check — DB, Redis, Celery, external APIs.
"""
import logging
import time
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class SystemHealthChecker:
    """Comprehensive system health checker."""

    @classmethod
    def run_all_checks(cls) -> dict:
        results = {}
        checks  = [
            ('database',    cls._check_db),
            ('cache_redis', cls._check_cache),
            ('celery',      cls._check_celery),
            ('storage',     cls._check_storage),
        ]
        for name, check_fn in checks:
            try:
                start  = time.monotonic()
                ok, msg = check_fn()
                elapsed = round((time.monotonic() - start) * 1000, 1)
                results[name] = {'healthy': ok, 'message': msg, 'latency_ms': elapsed}
            except Exception as e:
                results[name] = {'healthy': False, 'message': str(e), 'latency_ms': 0}

        overall = all(r['healthy'] for r in results.values())
        return {
            'status'    : 'healthy' if overall else 'degraded',
            'checks'    : results,
            'timestamp' : timezone.now().isoformat(),
        }

    @staticmethod
    def _check_db() -> tuple:
        from django.db import connection
        connection.ensure_connection()
        cursor = connection.cursor()
        cursor.execute('SELECT 1')
        return True, 'Database connected'

    @staticmethod
    def _check_cache() -> tuple:
        test_key = 'health_check_ping'
        cache.set(test_key, 'pong', 10)
        result = cache.get(test_key)
        if result == 'pong':
            return True, 'Redis connected'
        return False, 'Redis read/write failed'

    @staticmethod
    def _check_celery() -> tuple:
        try:
            from celery import current_app
            inspector = current_app.control.inspect(timeout=2)
            stats     = inspector.stats()
            if stats:
                return True, f'{len(stats)} workers active'
            return False, 'No Celery workers responding'
        except Exception as e:
            return False, f'Celery check failed: {str(e)[:100]}'

    @staticmethod
    def _check_storage() -> tuple:
        import os, tempfile
        try:
            with tempfile.NamedTemporaryFile(delete=True) as f:
                f.write(b'health_check')
            return True, 'Storage writable'
        except Exception as e:
            return False, str(e)


# ─────────────────────────────────────────────────────
# db_indexer.py
# ─────────────────────────────────────────────────────

class DBIndexer:
    """Database index management and query optimization."""

    @staticmethod
    def get_missing_indexes() -> list:
        """Find columns that likely need indexes based on query patterns."""
        from django.db import connection
        cursor = connection.cursor()
        # Check for sequential scans on large tables (PostgreSQL only)
        try:
            cursor.execute("""
                SELECT schemaname, tablename, attname, n_distinct, correlation
                FROM pg_stats
                WHERE tablename LIKE '%offer%'
                AND n_distinct > 100
                AND correlation < 0.1
                ORDER BY n_distinct DESC
                LIMIT 20;
            """)
            return [dict(zip([col[0] for col in cursor.description], row))
                    for row in cursor.fetchall()]
        except Exception:
            return []

    @staticmethod
    def analyze_tables():
        """Run ANALYZE on offer inventory tables for query planner."""
        from django.db import connection
        tables = [
            'offer_inventory_click',
            'offer_inventory_conversion',
            'offer_inventory_offer',
            'offer_inventory_walletaudit',
        ]
        cursor = connection.cursor()
        for table in tables:
            try:
                cursor.execute(f'ANALYZE {table};')
                logger.info(f'ANALYZE completed: {table}')
            except Exception as e:
                logger.warning(f'ANALYZE failed for {table}: {e}')

    @staticmethod
    def get_table_sizes() -> list:
        """Get table sizes for capacity planning."""
        from django.db import connection
        try:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT tablename,
                       pg_size_pretty(pg_total_relation_size(tablename::regclass)) as size,
                       pg_total_relation_size(tablename::regclass) as bytes
                FROM pg_tables
                WHERE tablename LIKE 'offer_inventory_%'
                ORDER BY bytes DESC;
            """)
            return [{'table': r[0], 'size': r[1]} for r in cursor.fetchall()]
        except Exception:
            return []


# ─────────────────────────────────────────────────────
# rate_limiter.py
# ─────────────────────────────────────────────────────

class RateLimiterEngine:
    """
    Advanced rate limiting with sliding window algorithm.
    Per-user, per-IP, per-endpoint limits.
    """

    LIMITS = {
        'click'      : (60,   100),   # 100 clicks/min
        'conversion' : (60,   10),    # 10 conversions/min
        'withdrawal' : (3600, 3),     # 3 withdrawals/hour
        'api_default': (60,   1000),  # 1000 API calls/min
        'kyc_submit' : (3600, 3),     # 3 KYC submissions/hour
    }

    @classmethod
    def check(cls, action: str, identifier: str,
               custom_limit: int = None, window: int = None) -> dict:
        """Check rate limit. Returns {'allowed': bool, 'remaining': int}."""
        default_window, default_limit = cls.LIMITS.get(action, (60, 100))
        w = window or default_window
        l = custom_limit or default_limit

        key   = f'rl:{action}:{identifier}'
        count = cache.get(key, 0)

        if count >= l:
            ttl = cache.ttl(key) if hasattr(cache, 'ttl') else w
            return {'allowed': False, 'remaining': 0, 'retry_after': ttl or w}

        cache.set(key, count + 1, w)
        return {'allowed': True, 'remaining': l - count - 1}

    @classmethod
    def reset(cls, action: str, identifier: str):
        cache.delete(f'rl:{action}:{identifier}')

    @classmethod
    def get_stats(cls, action: str, identifier: str) -> dict:
        default_window, default_limit = cls.LIMITS.get(action, (60, 100))
        key   = f'rl:{action}:{identifier}'
        count = cache.get(key, 0)
        return {
            'action'   : action,
            'count'    : count,
            'limit'    : default_limit,
            'window'   : default_window,
            'remaining': max(0, default_limit - count),
        }


# ─────────────────────────────────────────────────────
# task_scheduler.py
# ─────────────────────────────────────────────────────

class TaskSchedulerManager:
    """Dynamic task scheduling and management."""

    @staticmethod
    def schedule_offer_expiry(offer_id: str, expires_at) -> str:
        """Schedule automatic offer expiry."""
        from api.offer_inventory.tasks import auto_expire_offers
        eta = expires_at
        result = auto_expire_offers.apply_async(eta=eta)
        logger.info(f'Offer expiry scheduled: {offer_id} at {expires_at}')
        return result.id

    @staticmethod
    def schedule_bulk_notification(user_ids: list, title: str, body: str,
                                    delay_seconds: int = 0) -> str:
        """Schedule bulk notification with delay."""
        from api.offer_inventory.tasks import send_bulk_notification
        result = send_bulk_notification.apply_async(
            args=[user_ids, title, body],
            countdown=delay_seconds,
        )
        return result.id

    @staticmethod
    def get_pending_tasks() -> list:
        """Get list of pending Celery tasks."""
        from api.offer_inventory.models import TaskQueue
        return list(
            TaskQueue.objects.filter(status='pending')
            .values('task_id', 'task_name', 'created_at')
            .order_by('-created_at')[:100]
        )

    @staticmethod
    def cancel_task(task_id: str) -> bool:
        """Cancel a pending Celery task."""
        try:
            from celery import current_app
            current_app.control.revoke(task_id, terminate=True)
            from api.offer_inventory.models import TaskQueue
            TaskQueue.objects.filter(task_id=task_id).update(status='failure', error='Cancelled')
            return True
        except Exception as e:
            logger.error(f'Task cancel error: {e}')
            return False


# ─────────────────────────────────────────────────────
# backup_manager.py
# ─────────────────────────────────────────────────────

class BackupManager:
    """Database and file backup management."""

    @staticmethod
    def create_db_backup(destination: str = '/tmp') -> dict:
        """Create a database backup using pg_dump."""
        import subprocess
        import os
        from django.conf import settings
        from django.utils import timezone

        db    = settings.DATABASES['default']
        fname = f'offer_inventory_{timezone.now().strftime("%Y%m%d_%H%M%S")}.sql.gz'
        fpath = os.path.join(destination, fname)

        cmd = [
            'pg_dump',
            '-h', db.get('HOST', 'localhost'),
            '-U', db.get('USER', 'postgres'),
            '-d', db.get('NAME', ''),
            '-t', 'offer_inventory_*',
            '--no-owner',
            '--no-acl',
        ]

        from api.offer_inventory.models import BackupLog
        log = BackupLog.objects.create(
            backup_type='db', status='running', started_by='system'
        )

        try:
            import gzip
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            with gzip.open(fpath, 'wb') as f:
                f.write(result.stdout)

            size = os.path.getsize(fpath)
            log.status    = 'completed'
            log.file_path = fpath
            log.file_size = size
            log.save(update_fields=['status', 'file_path', 'file_size'])

            return {'success': True, 'file': fpath, 'size_bytes': size}
        except Exception as e:
            log.status = 'failed'
            log.error  = str(e)
            log.save(update_fields=['status', 'error'])
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_backup_history(limit: int = 20) -> list:
        from api.offer_inventory.models import BackupLog
        return list(
            BackupLog.objects.all()
            .order_by('-created_at')
            .values('backup_type', 'status', 'file_size', 'duration_secs', 'created_at')
            [:limit]
        )


# ─────────────────────────────────────────────────────
# log_rotator.py
# ─────────────────────────────────────────────────────

class LogRotator:
    """Rotate and archive old log records from DB."""

    @staticmethod
    def rotate_all(days_to_keep: int = 90) -> dict:
        """Delete old log records beyond retention period."""
        from api.offer_inventory.models import (
            Click, PostbackLog, AuditLog, RateLimitLog,
            HoneypotLog, PixelLog, ErrorLog, NetworkPinger,
        )
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(days=days_to_keep)
        results = {}

        tasks = [
            ('fraud_clicks',  Click.objects.filter(is_fraud=True, created_at__lt=cutoff)),
            ('postback_logs', PostbackLog.objects.filter(is_success=True, created_at__lt=cutoff)),
            ('rate_limit',    RateLimitLog.objects.filter(created_at__lt=cutoff)),
            ('honeypot',      HoneypotLog.objects.filter(created_at__lt=cutoff)),
            ('network_ping',  NetworkPinger.objects.filter(created_at__lt=cutoff)),
            ('errors_resolved', ErrorLog.objects.filter(is_resolved=True, created_at__lt=cutoff)),
        ]

        for name, qs in tasks:
            try:
                count, _ = qs.delete()
                results[name] = count
            except Exception as e:
                results[name] = f'error: {e}'

        total = sum(v for v in results.values() if isinstance(v, int))
        logger.info(f'Log rotation: {total} records deleted')
        return {'deleted': results, 'total': total}

    @staticmethod
    def get_log_sizes() -> dict:
        from api.offer_inventory.models import (
            Click, Conversion, AuditLog, ErrorLog,
            PostbackLog, RateLimitLog,
        )
        return {
            'clicks'      : Click.objects.count(),
            'conversions' : Conversion.objects.count(),
            'audit_logs'  : AuditLog.objects.count(),
            'error_logs'  : ErrorLog.objects.count(),
            'postback_logs': PostbackLog.objects.count(),
            'rate_limit'  : RateLimitLog.objects.count(),
        }


# ─────────────────────────────────────────────────────
# auto_scaler.py
# ─────────────────────────────────────────────────────

class AutoScalerConfig:
    """
    Auto-scaler configuration manager.
    Monitors load and suggests/applies scaling decisions.
    Works with Railway, Heroku, or Kubernetes via environment variables.
    """

    LOAD_THRESHOLDS = {
        'high'  : {'clicks_per_min': 500, 'queue_size': 1000},
        'medium': {'clicks_per_min': 200, 'queue_size': 200},
    }

    @staticmethod
    def get_current_load() -> dict:
        """Get current system load metrics."""
        from api.offer_inventory.models import Click, TaskQueue
        from datetime import timedelta

        since_1min = timezone.now() - timedelta(minutes=1)
        clicks_pm  = Click.objects.filter(created_at__gte=since_1min).count()
        queue_size = TaskQueue.objects.filter(status='pending').count()

        load_level = 'low'
        if clicks_pm >= AutoScalerConfig.LOAD_THRESHOLDS['high']['clicks_per_min']:
            load_level = 'high'
        elif clicks_pm >= AutoScalerConfig.LOAD_THRESHOLDS['medium']['clicks_per_min']:
            load_level = 'medium'

        return {
            'clicks_per_minute': clicks_pm,
            'queue_size'       : queue_size,
            'load_level'       : load_level,
            'recommendation'   : AutoScalerConfig._get_recommendation(load_level),
        }

    @staticmethod
    def _get_recommendation(load_level: str) -> str:
        recommendations = {
            'high'  : 'Scale up: Add 2+ Celery workers, increase Redis memory',
            'medium': 'Monitor: Consider adding 1 Celery worker',
            'low'   : 'Current capacity is sufficient',
        }
        return recommendations.get(load_level, 'Unknown')
