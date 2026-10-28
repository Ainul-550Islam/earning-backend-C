"""
tasks/cleanup_tasks.py
Data cleanup & archival Celery tasks:
  - cleanup_old_task_performance_logs  — purge old TaskPerformanceLog rows
  - cleanup_old_queue_depth_snapshots  — purge old QueueDepth rows
  - archive_old_completions            — archive old UserTaskCompletion rows
  - cleanup_expired_sessions           — purge expired Django sessions
  - cleanup_stale_worker_records       — remove offline WorkerHealth records
  - cleanup_old_workflow_instances     — remove completed workflow instances
  - vacuum_analytics_tables            — PostgreSQL VACUUM ANALYZE
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# cleanup_old_task_performance_logs
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.cleanup_tasks.cleanup_old_task_performance_logs',
)
def cleanup_old_task_performance_logs(self, days_to_keep: int = 30, batch_size: int = 1000) -> dict:
    """
    Delete TaskPerformanceLog records older than `days_to_keep` days.
    Runs in batches to avoid long-running DELETE queries.
    """
    try:
        from datetime import timedelta
        logger.info(f"🧹 Cleaning up old TaskPerformanceLogs (keep={days_to_keep}d)...")

        cutoff      = timezone.now() - timedelta(days=days_to_keep)
        total_deleted = 0

        try:
            from api.tasks.models.monitoring import TaskPerformanceLog

            while True:
                ids_to_delete = list(
                    TaskPerformanceLog.objects.filter(
                        created_at__lt=cutoff
                    ).values_list('id', flat=True)[:batch_size]
                )
                if not ids_to_delete:
                    break
                deleted_count, _ = TaskPerformanceLog.objects.filter(id__in=ids_to_delete).delete()
                total_deleted += deleted_count
                logger.debug(f"  Deleted {deleted_count} rows (total={total_deleted})")

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'deleted': total_deleted,
            'days_to_keep': days_to_keep,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Cleaned up {total_deleted} TaskPerformanceLog records")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] cleanup_old_task_performance_logs failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# cleanup_old_queue_depth_snapshots
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.cleanup_tasks.cleanup_old_queue_depth_snapshots',
)
def cleanup_old_queue_depth_snapshots(self, days_to_keep: int = 7) -> dict:
    """
    Purge QueueDepth snapshot records older than `days_to_keep` days.
    High-frequency data — 7 days is usually sufficient for analysis.
    """
    try:
        from datetime import timedelta
        logger.info(f"🧹 Cleaning up old QueueDepth snapshots (keep={days_to_keep}d)...")

        cutoff  = timezone.now() - timedelta(days=days_to_keep)
        deleted = 0

        try:
            from api.tasks.models.monitoring import QueueDepth
            deleted, _ = QueueDepth.objects.filter(checked_at__lt=cutoff).delete()
        except ImportError as e:
            logger.warning(f"[WARN] QueueDepth model not available: {e}")

        result = {
            'status': 'success',
            'deleted': deleted,
            'days_to_keep': days_to_keep,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Cleaned up {deleted} QueueDepth snapshots")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] cleanup_old_queue_depth_snapshots failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# archive_old_completions
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    name='tasks.cleanup_tasks.archive_old_completions',
)
def archive_old_completions(self, days_to_keep: int = 90, batch_size: int = 500) -> dict:
    """
    Move UserTaskCompletion records older than `days_to_keep` days
    to an archive table (if it exists) or flag them as archived.
    Keeps the main table fast for live queries.
    """
    try:
        from datetime import timedelta
        from django.db import transaction

        logger.info(f"📦 Archiving old completions (keep={days_to_keep}d)...")

        cutoff   = timezone.now() - timedelta(days=days_to_keep)
        archived = 0
        errors   = 0

        try:
            from api.tasks.models import UserTaskCompletion

            old_qs = UserTaskCompletion.objects.filter(
                completed_at__lt=cutoff,
                status='completed',
                is_archived=False,
            )

            while True:
                batch_ids = list(old_qs.values_list('id', flat=True)[:batch_size])
                if not batch_ids:
                    break

                try:
                    with transaction.atomic():
                        UserTaskCompletion.objects.filter(
                            id__in=batch_ids
                        ).update(is_archived=True)
                        archived += len(batch_ids)
                except Exception as batch_err:
                    logger.error(f"[ERROR] Archive batch failed: {batch_err}")
                    errors += len(batch_ids)
                    break

        except ImportError as e:
            logger.warning(f"[WARN] UserTaskCompletion model not available: {e}")
        except Exception as attr_err:
            # is_archived field may not exist yet — silently skip
            logger.warning(f"[WARN] Completion archival skipped: {attr_err}")

        result = {
            'status': 'success',
            'archived': archived,
            'errors': errors,
            'days_to_keep': days_to_keep,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Archived {archived} old completions")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] archive_old_completions failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# cleanup_expired_sessions
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.cleanup_tasks.cleanup_expired_sessions',
)
def cleanup_expired_sessions(self) -> dict:
    """
    Purge expired Django session records from the database.
    Equivalent to running: python manage.py clearsessions
    """
    try:
        logger.info("🔑 Cleaning up expired sessions...")
        deleted = 0

        try:
            from django.contrib.sessions.backends.db import SessionStore
            from django.contrib.sessions.models import Session

            expired = Session.objects.filter(expire_date__lt=timezone.now())
            deleted, _ = expired.delete()

        except ImportError as e:
            logger.warning(f"[WARN] Session model not available: {e}")

        result = {
            'status': 'success',
            'deleted': deleted,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Cleaned up {deleted} expired sessions")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] cleanup_expired_sessions failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# cleanup_stale_worker_records
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name='tasks.cleanup_tasks.cleanup_stale_worker_records',
)
def cleanup_stale_worker_records(self, stale_minutes: int = 10) -> dict:
    """
    Mark WorkerHealth records as offline if their last heartbeat
    is older than `stale_minutes` minutes.
    Deletes records older than 24 hours entirely.
    """
    try:
        from datetime import timedelta
        logger.info(f"🔍 Cleaning up stale worker records (stale_minutes={stale_minutes})...")

        marked_offline = 0
        deleted        = 0

        try:
            from api.tasks.models.monitoring import WorkerHealth

            stale_cutoff  = timezone.now() - timedelta(minutes=stale_minutes)
            delete_cutoff = timezone.now() - timedelta(hours=24)

            # Mark stale workers as offline
            marked_offline = WorkerHealth.objects.filter(
                last_heartbeat__lt=stale_cutoff,
                status__in=[WorkerHealth.Status.ONLINE, WorkerHealth.Status.IDLE, WorkerHealth.Status.BUSY],
            ).update(status=WorkerHealth.Status.OFFLINE)

            # Delete very old offline records
            deleted, _ = WorkerHealth.objects.filter(
                last_heartbeat__lt=delete_cutoff,
                status=WorkerHealth.Status.OFFLINE,
            ).delete()

        except ImportError as e:
            logger.warning(f"[WARN] WorkerHealth model not available: {e}")

        result = {
            'status': 'success',
            'marked_offline': marked_offline,
            'deleted': deleted,
            'stale_minutes': stale_minutes,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Stale workers: {marked_offline} marked offline, {deleted} deleted")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] cleanup_stale_worker_records failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# cleanup_old_workflow_instances
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.cleanup_tasks.cleanup_old_workflow_instances',
)
def cleanup_old_workflow_instances(self, days_to_keep: int = 30) -> dict:
    """
    Delete completed/failed/cancelled WorkflowInstance records
    (and their logs) older than `days_to_keep` days.
    Retains 'running' instances regardless of age.
    """
    try:
        from datetime import timedelta
        logger.info(f"🧹 Cleaning up old workflow instances (keep={days_to_keep}d)...")

        cutoff  = timezone.now() - timedelta(days=days_to_keep)
        deleted = 0

        try:
            from api.tasks.models.workflow import WorkflowInstance

            deleted, _ = WorkflowInstance.objects.filter(
                status__in=['success', 'failed', 'cancelled'],
                completed_at__lt=cutoff,
            ).delete()

        except ImportError as e:
            logger.warning(f"[WARN] WorkflowInstance model not available: {e}")

        result = {
            'status': 'success',
            'deleted': deleted,
            'days_to_keep': days_to_keep,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Cleaned up {deleted} old workflow instances")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] cleanup_old_workflow_instances failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# vacuum_analytics_tables
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=1,
    default_retry_delay=120,
    name='tasks.cleanup_tasks.vacuum_analytics_tables',
)
def vacuum_analytics_tables(self) -> dict:
    """
    Run PostgreSQL VACUUM ANALYZE on high-churn analytics tables.
    Skipped silently on non-PostgreSQL backends.
    Should be scheduled weekly during off-peak hours.
    """
    try:
        from django.db import connection

        logger.info("🔧 Running VACUUM ANALYZE on analytics tables...")

        tables = [
            'tasks_taskperformancelog',
            'tasks_queuedepth',
            'tasks_taskthroughput',
            'tasks_taskinsight',
            'tasks_taskfailurerate',
        ]

        vacuumed = []
        skipped  = []

        if connection.vendor != 'postgresql':
            logger.info(f"[INFO] Database vendor is '{connection.vendor}'. VACUUM skipped.")
            return {
                'status': 'skipped',
                'reason': 'non_postgresql_backend',
                'vendor': connection.vendor,
                'timestamp': timezone.now().isoformat(),
            }

        with connection.cursor() as cursor:
            # Must be outside a transaction for VACUUM
            connection.set_autocommit(True)
            for table in tables:
                try:
                    cursor.execute(f"VACUUM ANALYZE {table}")
                    vacuumed.append(table)
                    logger.info(f"  VACUUM ANALYZE {table} done")
                except Exception as tbl_err:
                    skipped.append({'table': table, 'error': str(tbl_err)})
                    logger.warning(f"  [WARN] VACUUM ANALYZE {table}: {tbl_err}")

        result = {
            'status': 'success',
            'vacuumed': vacuumed,
            'skipped': skipped,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] VACUUM ANALYZE done: {len(vacuumed)} tables")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] vacuum_analytics_tables failed: {exc}")
        raise self.retry(exc=exc)
