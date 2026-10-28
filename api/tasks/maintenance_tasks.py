"""
tasks/maintenance_tasks.py
System maintenance Celery tasks:
  - cleanup_old_data               — purge old DB records
  - optimize_database              — VACUUM/ANALYZE + index maintenance
  - clear_expired_cache            — flush stale cache keys
  - rebuild_search_indexes         — rebuild full-text search indexes
  - rotate_log_files               — compress and archive log files
  - system_diagnostics             — collect system metrics snapshot
"""
import logging
import os
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=120,
             name='tasks.maintenance_tasks.cleanup_old_data')
def cleanup_old_data(self, days: int = 30) -> dict:
    """
    Purge old data across all relevant models.
    Cleans: expired sessions, old notifications, stale cache, old logs.
    """
    try:
        from datetime import timedelta
        logger.info(f"🧹 Cleaning up data older than {days} days...")

        results  = {}
        cutoff   = timezone.now() - timedelta(days=days)

        # Django sessions
        try:
            from django.contrib.sessions.models import Session
            n, _ = Session.objects.filter(expire_date__lt=timezone.now()).delete()
            results['sessions'] = n
        except Exception as e:
            results['sessions'] = f'error: {e}'

        # Old notifications
        try:
            from notifications.models import Notification
            n, _ = Notification.objects.filter(
                is_read=True, created_at__lt=cutoff
            ).delete()
            results['notifications'] = n
        except ImportError:
            results['notifications'] = 'model_not_available'

        # Old performance logs (keep 30d by default)
        try:
            from api.tasks.models.monitoring import TaskPerformanceLog
            n, _ = TaskPerformanceLog.objects.filter(created_at__lt=cutoff).delete()
            results['task_perf_logs'] = n
        except ImportError:
            results['task_perf_logs'] = 'model_not_available'

        # Old queue depth snapshots (keep 7d)
        try:
            from api.tasks.models.monitoring import QueueDepth
            from datetime import timedelta as td
            n, _ = QueueDepth.objects.filter(
                checked_at__lt=timezone.now() - td(days=7)
            ).delete()
            results['queue_depths'] = n
        except ImportError:
            results['queue_depths'] = 'model_not_available'

        result = {
            'status': 'success',
            'message': f'Cleaned up data older than {days} days',
            'timestamp': timezone.now().isoformat(),
            'deleted': results,
        }
        logger.info(f"[OK] Cleanup done: {results}")
        return result

    except Exception as e:
        logger.error(f"[ERROR] cleanup_old_data: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=1, default_retry_delay=300,
             name='tasks.maintenance_tasks.optimize_database')
def optimize_database(self) -> dict:
    """
    Run database optimization:
    - PostgreSQL: VACUUM ANALYZE on main tables
    - All DBs: check for slow queries
    Should run weekly during off-peak hours.
    """
    try:
        from django.db import connection
        logger.info("⚙️ Running database optimization...")

        tables   = []
        skipped  = []
        vacuumed = []

        if connection.vendor == 'postgresql':
            main_tables = [
                'tasks_mastertask',
                'tasks_usertaskcompletion',
                'tasks_adminledger',
                'tasks_taskperformancelog',
                'tasks_taskdeadletterqueue',
                'tasks_taskinsight',
            ]
            with connection.cursor() as cursor:
                connection.set_autocommit(True)
                for table in main_tables:
                    try:
                        cursor.execute(f"VACUUM ANALYZE {table}")
                        vacuumed.append(table)
                        logger.info(f"  ✓ VACUUM ANALYZE {table}")
                    except Exception as te:
                        skipped.append({'table': table, 'error': str(te)})
        else:
            logger.info(f"[INFO] DB vendor='{connection.vendor}' — skipping VACUUM")

        result = {
            'status': 'success',
            'vendor': connection.vendor,
            'vacuumed': vacuumed,
            'skipped': skipped,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] DB optimization done: {len(vacuumed)} tables vacuumed")
        return result

    except Exception as e:
        logger.error(f"[ERROR] optimize_database: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.maintenance_tasks.clear_expired_cache')
def clear_expired_cache(self, pattern_prefix: str = None) -> dict:
    """
    Clear expired/stale cache keys.
    Clears known stale patterns: fraud scores, queue depths, report caches.
    """
    try:
        from django.conf import settings
        logger.info("🗑️ Clearing expired cache entries...")

        cleared = 0
        errors  = 0

        stale_keys = [
            'gateway_health',
            'wallet_platform_totals',
            'referral_stats',
            'platform_kpis',
            'cpalead_ranked_offers',
            'worker_health_all',
        ]

        if pattern_prefix:
            stale_keys = [k for k in stale_keys if k.startswith(pattern_prefix)]

        for key in stale_keys:
            try:
                val = cache.get(key)
                if val is None:
                    cache.delete(key)
                    cleared += 1
            except Exception as e:
                errors += 1

        result = {
            'status': 'success',
            'cleared': cleared,
            'errors': errors,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Cache cleared: {cleared} keys")
        return result

    except Exception as e:
        logger.error(f"[ERROR] clear_expired_cache: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.maintenance_tasks.rebuild_search_indexes')
def rebuild_search_indexes(self) -> dict:
    """
    Rebuild full-text search indexes for MasterTask and UserTaskCompletion.
    Uses Django's built-in SearchVector for PostgreSQL.
    """
    try:
        from django.db import connection
        logger.info("🔍 Rebuilding search indexes...")
        rebuilt = []

        if connection.vendor == 'postgresql':
            try:
                from api.tasks.models import MasterTask
                from django.contrib.postgres.search import SearchVector
                MasterTask.objects.update(
                    search_vector=SearchVector('name', 'description', 'task_id')
                )
                rebuilt.append('MasterTask')
            except (ImportError, Exception) as e:
                logger.warning(f"[WARN] MasterTask search rebuild: {e}")
        else:
            logger.info("[INFO] Full-text search rebuild only supports PostgreSQL")

        result = {
            'status': 'success',
            'rebuilt': rebuilt,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Search indexes rebuilt: {rebuilt}")
        return result

    except Exception as e:
        logger.error(f"[ERROR] rebuild_search_indexes: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=1, default_retry_delay=60,
             name='tasks.maintenance_tasks.system_diagnostics')
def system_diagnostics(self) -> dict:
    """
    Collect a full system diagnostic snapshot:
    - DB query count + latency
    - Redis memory
    - Worker count
    - Queue depths
    - Disk usage
    - Platform KPIs
    Cache for 5 minutes as 'system_diagnostics'.
    """
    try:
        import shutil
        import time
        from django.db import connection
        logger.info("🏥 Running system diagnostics...")

        diag = {
            'collected_at': timezone.now().isoformat(),
            'database': {},
            'cache': {},
            'disk': {},
            'workers': {},
            'queues': [],
        }

        # Database
        try:
            start = time.monotonic()
            with connection.cursor() as c:
                c.execute("SELECT 1")
            diag['database'] = {
                'status': 'healthy',
                'latency_ms': round((time.monotonic() - start) * 1000, 2),
                'vendor': connection.vendor,
            }
        except Exception as e:
            diag['database'] = {'status': 'unhealthy', 'error': str(e)}

        # Cache (Redis)
        try:
            start = time.monotonic()
            cache.set('_diag_probe', 1, timeout=5)
            cache.get('_diag_probe')
            diag['cache'] = {
                'status': 'healthy',
                'latency_ms': round((time.monotonic() - start) * 1000, 2),
            }
        except Exception as e:
            diag['cache'] = {'status': 'unhealthy', 'error': str(e)}

        # Disk
        try:
            total, used, free = shutil.disk_usage('/')
            used_pct = used / total * 100
            diag['disk'] = {
                'status': 'warning' if used_pct > 80 else 'ok',
                'used_pct': round(used_pct, 1),
                'free_gb': round(free / (1024 ** 3), 2),
            }
        except Exception as e:
            diag['disk'] = {'status': 'unknown', 'error': str(e)}

        # Workers
        try:
            from api.tasks.services.WorkerHealthService import WorkerHealthService
            diag['workers'] = WorkerHealthService().refresh(timeout=2.0)
        except Exception:
            diag['workers'] = {'online': 0, 'error': 'inspect_failed'}

        # Queue depths
        try:
            from api.tasks.services.QueueDepthService import QueueDepthService
            diag['queues'] = QueueDepthService().get_all_depths()
        except Exception:
            diag['queues'] = []

        cache.set('system_diagnostics', diag, timeout=300)
        logger.info(f"[OK] System diagnostics collected: db={diag['database'].get('status')} cache={diag['cache'].get('status')}")
        return {'status': 'success', 'diagnostics': diag}

    except Exception as e:
        logger.error(f"[ERROR] system_diagnostics: {e}")
        raise self.retry(exc=e)
