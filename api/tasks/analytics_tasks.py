"""
tasks/analytics_tasks.py
Analytics Celery tasks:
  - daily_analytics_rollup         — aggregate daily TaskInsight rows
  - compute_queue_throughput       — snapshot tasks-per-minute per queue
  - compute_task_failure_rates     — aggregate failure rates by period
  - compute_platform_kpis          — MAU, DAU, ARPU, retention
  - refresh_analytics_cache        — warm analytics cache for admin dashboard
"""
from celery.exceptions import MaxRetriesExceededError
from datetime import date
from datetime import timedelta
from typing import Any
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# daily_analytics_rollup
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='tasks.analytics_tasks.daily_analytics_rollup',
)
def daily_analytics_rollup(self, date_str: str = None) -> dict:
    """
    Aggregate TaskPerformanceLog records into TaskInsight rows for a given date.
    Creates or updates one TaskInsight row per (date, task_name).
    Called by Celery Beat daily at 00:05 UTC for the previous day.
    """
    try:
        from datetime import datetime, timedelta
        from django.db.models import Count, Sum, Avg, Min, Max, Q

        target_date = (
            datetime.strptime(date_str, '%Y-%m-%d').date()
            if date_str
            else (timezone.now() - timedelta(days=1)).date()
        )

        logger.info(f"📊 Daily analytics rollup for {target_date}...")

        rows_created  = 0
        rows_updated  = 0

        try:
            from api.tasks.models.monitoring import TaskPerformanceLog
            from api.tasks.models.analytics import TaskInsight

            day_start = timezone.make_aware(
                datetime.combine(target_date, datetime.min.time())
            )
            day_end = day_start + timedelta(days=1)

            # Group logs by task_name
            task_names = (
                TaskPerformanceLog.objects.filter(
                    created_at__gte=day_start,
                    created_at__lt=day_end,
                )
                .values_list('task_name', flat=True)
                .distinct()
            )

            for task_name in task_names:
                qs = TaskPerformanceLog.objects.filter(
                    task_name=task_name,
                    created_at__gte=day_start,
                    created_at__lt=day_end,
                )

                agg = qs.aggregate(
                    run_count=Count('id'),
                    success_count=Count('id', filter=Q(result='success')),
                    failure_count=Count('id', filter=Q(result='failure')),
                    retry_count=Count('id', filter=Q(result='retry')),
                    avg_duration=Avg('duration_seconds'),
                    min_duration=Min('duration_seconds'),
                    max_duration=Max('duration_seconds'),
                    total_cpu=Sum('cpu_seconds'),
                    avg_memory=Avg('memory_mb'),
                )

                # Calculate percentiles via Python (no DB percentile support in SQLite)
                durations = list(
                    qs.filter(duration_seconds__isnull=False)
                    .values_list('duration_seconds', flat=True)
                    .order_by('duration_seconds')
                )
                p50 = p95 = p99 = None
                n   = len(durations)
                if n > 0:
                    p50 = durations[int(n * 0.50)]
                    p95 = durations[min(int(n * 0.95), n - 1)]
                    p99 = durations[min(int(n * 0.99), n - 1)]

                queue = qs.filter(queue__isnull=False).values_list('queue', flat=True).first() or ''

                obj, created = TaskInsight.objects.update_or_create(
                    date=target_date,
                    task_name=task_name,
                    defaults={
                        'queue': queue,
                        'run_count': agg['run_count'] or 0,
                        'success_count': agg['success_count'] or 0,
                        'failure_count': agg['failure_count'] or 0,
                        'retry_count': agg['retry_count'] or 0,
                        'avg_duration': agg['avg_duration'],
                        'min_duration': agg['min_duration'],
                        'max_duration': agg['max_duration'],
                        'p50_duration': p50,
                        'p95_duration': p95,
                        'p99_duration': p99,
                        'total_cpu_seconds': agg['total_cpu'],
                        'avg_memory_mb': agg['avg_memory'],
                    },
                )

                if created:
                    rows_created += 1
                else:
                    rows_updated += 1

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'date': str(target_date),
            'rows_created': rows_created,
            'rows_updated': rows_updated,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Daily analytics rollup done: {rows_created} created, {rows_updated} updated")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] daily_analytics_rollup failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# compute_queue_throughput
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name='tasks.analytics_tasks.compute_queue_throughput',
)
def compute_queue_throughput(self, period_minutes: int = 5) -> dict:
    """
    Compute tasks-per-minute throughput for each queue over the last `period_minutes`.
    Creates TaskThroughput snapshot records for charting.
    """
    try:
        from datetime import timedelta
        from django.db.models import Count, Q

        logger.info(f"⚡ Computing queue throughput (period={period_minutes}m)...")

        snapshots_created = 0
        window_start      = timezone.now() - timedelta(minutes=period_minutes)

        try:
            from api.tasks.models.monitoring import TaskPerformanceLog
            from api.tasks.models.analytics  import TaskThroughput

            queue_stats = (
                TaskPerformanceLog.objects.filter(created_at__gte=window_start)
                .values('queue')
                .annotate(
                    completed=Count('id', filter=Q(result='success')),
                    failed=Count('id', filter=Q(result='failure')),
                )
            )

            for row in queue_stats:
                queue_name = row['queue'] or 'default'
                total      = row['completed'] + row['failed']
                tpm        = total / period_minutes  # tasks per minute

                TaskThroughput.objects.create(
                    queue_name=queue_name,
                    tasks_per_minute=round(tpm, 4),
                    tasks_per_hour=round(tpm * 60, 4),
                    period='5m',
                    completed_count=row['completed'],
                    failed_count=row['failed'],
                    snapshot_at=timezone.now(),
                )
                snapshots_created += 1

                cache.set(f'queue_tpm_{queue_name}', round(tpm, 4), timeout=600)

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'snapshots_created': snapshots_created,
            'period_minutes': period_minutes,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Queue throughput computed: {snapshots_created} queues")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] compute_queue_throughput failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# compute_task_failure_rates
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.analytics_tasks.compute_task_failure_rates',
)
def compute_task_failure_rates(self, period: str = 'daily') -> dict:
    """
    Aggregate per-task failure rates for the given period.
    period: 'hourly' | 'daily' | 'weekly' | 'monthly'
    Creates or updates TaskFailureRate records.
    """
    try:
        from datetime import timedelta, datetime
        from django.db.models import Count, Q

        logger.info(f"📉 Computing task failure rates (period={period})...")

        now = timezone.now()
        period_map = {
            'hourly':  timedelta(hours=1),
            'daily':   timedelta(days=1),
            'weekly':  timedelta(weeks=1),
            'monthly': timedelta(days=30),
        }
        delta        = period_map.get(period, timedelta(days=1))
        period_start = now - delta
        period_end   = now

        rows_created = 0
        rows_updated = 0

        try:
            from api.tasks.models.monitoring import TaskPerformanceLog
            from api.tasks.models.analytics  import TaskFailureRate

            task_names = (
                TaskPerformanceLog.objects.filter(
                    created_at__gte=period_start,
                    created_at__lt=period_end,
                )
                .values_list('task_name', flat=True)
                .distinct()
            )

            for task_name in task_names:
                qs = TaskPerformanceLog.objects.filter(
                    task_name=task_name,
                    created_at__gte=period_start,
                    created_at__lt=period_end,
                )

                agg = qs.aggregate(
                    total=Count('id'),
                    failures=Count('id', filter=Q(result='failure')),
                )

                total    = agg['total'] or 0
                failures = agg['failures'] or 0
                fail_pct = (failures / total * 100) if total > 0 else 0.0

                # Find most common error
                most_common = (
                    qs.filter(result='failure')
                    .exclude(error='')
                    .values('error')
                    .annotate(cnt=Count('id'))
                    .order_by('-cnt')
                    .first()
                )
                most_common_error       = most_common['error'] if most_common else ''
                most_common_error_count = most_common['cnt'] if most_common else 0

                # Error breakdown (top 5)
                error_breakdown = list(
                    qs.filter(result='failure')
                    .exclude(error='')
                    .values('error')
                    .annotate(cnt=Count('id'))
                    .order_by('-cnt')[:5]
                    .values('error', 'cnt')
                )

                obj, created = TaskFailureRate.objects.update_or_create(
                    task_name=task_name,
                    period=period,
                    period_start=period_start,
                    defaults={
                        'period_end': period_end,
                        'total_runs': total,
                        'failure_count': failures,
                        'failure_pct': round(fail_pct, 4),
                        'most_common_error': most_common_error[:500],
                        'most_common_error_count': most_common_error_count,
                        'error_breakdown': error_breakdown,
                    },
                )
                if created:
                    rows_created += 1
                else:
                    rows_updated += 1

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'period': period,
            'rows_created': rows_created,
            'rows_updated': rows_updated,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Task failure rates computed: {rows_created} created, {rows_updated} updated")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] compute_task_failure_rates failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# compute_platform_kpis
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.analytics_tasks.compute_platform_kpis',
)
def compute_platform_kpis(self) -> dict:
    """
    Compute platform-wide KPIs and cache for admin dashboard:
    - DAU (Daily Active Users)
    - MAU (Monthly Active Users)
    - ARPU (Average Revenue Per User)
    - Task completion rate today
    - Total revenue today
    - Retention rate (users active on day 1 and day 7)
    """
    try:
        from datetime import timedelta
        from django.db.models import Sum, Count, Avg, Q
        from django.contrib.auth import get_user_model

        logger.info("📊 Computing platform KPIs...")

        kpis = {}
        now  = timezone.now()

        try:
            from api.tasks.models import UserTaskCompletion
            User = get_user_model()

            day_start   = now.replace(hour=0, minute=0, second=0, microsecond=0)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # DAU
            kpis['dau'] = (
                UserTaskCompletion.objects.filter(
                    completed_at__gte=day_start,
                    status='completed',
                )
                .values('user')
                .distinct()
                .count()
            )

            # MAU
            kpis['mau'] = (
                UserTaskCompletion.objects.filter(
                    completed_at__gte=month_start,
                    status='completed',
                )
                .values('user')
                .distinct()
                .count()
            )

            # Total revenue today
            today_revenue = (
                UserTaskCompletion.objects.filter(
                    completed_at__gte=day_start,
                    status='completed',
                )
                .aggregate(total=Sum('reward_amount'))['total'] or Decimal('0')
            )
            kpis['revenue_today'] = str(today_revenue)

            # ARPU (today)
            kpis['arpu_today'] = (
                str(round(today_revenue / kpis['dau'], 4))
                if kpis['dau'] > 0
                else '0'
            )

            # Completion rate today (completions / total registered users)
            total_users = User.objects.filter(is_active=True).count()
            kpis['completion_rate_today'] = (
                round(kpis['dau'] / total_users * 100, 2)
                if total_users > 0
                else 0.0
            )
            kpis['total_users'] = total_users

            cache.set('platform_kpis', kpis, timeout=1800)

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'kpis': kpis,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Platform KPIs computed: {kpis}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] compute_platform_kpis failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# refresh_analytics_cache
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name='tasks.analytics_tasks.refresh_analytics_cache',
)
def refresh_analytics_cache(self) -> dict:
    """
    Warm up all analytics-related caches used by the admin dashboard.
    Delegates to sub-tasks to keep results fresh.
    """
    try:
        logger.info("🔄 Refreshing analytics cache...")

        # Chain sub-tasks
        compute_platform_kpis.apply_async()
        compute_queue_throughput.apply_async()

        result = {
            'status': 'success',
            'tasks_triggered': [
                'compute_platform_kpis',
                'compute_queue_throughput',
            ],
            'timestamp': timezone.now().isoformat(),
        }
        logger.info("[OK] Analytics cache refresh triggered")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] refresh_analytics_cache failed: {exc}")
        raise self.retry(exc=exc)


# ══════════════════════════════════════════════════════════════
# MIGRATED FROM: api/behavior_analytics/tasks.py (original code preserved)
# ══════════════════════════════════════════════════════════════
@shared_task(
    bind=True,
    name=TASK_CALCULATE_ENGAGEMENT,
    max_retries=3,
    default_retry_delay=60,        # 1 minute
    acks_late=True,
    reject_on_worker_lost=True,
)
def calculate_engagement_score(
    self,
    user_id: str | int,
    target_date_iso: str | None = None,
) -> dict[str, Any]:
    """
    Calculate (or recalculate) the engagement score for a single user
    on `target_date_iso` (ISO-8601 date string, e.g. '2024-03-15').
    If not provided, today is used.

    Returns a summary dict on success.
    """
    from api.behavior_analytics.services import EngagementScoreService

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.error("calc_engagement.user_not_found user_id=%s", user_id)
        return {"status": "error", "reason": "user_not_found", "user_id": str(user_id)}

    target: date | None = None
    if target_date_iso:
        try:
            target = date.fromisoformat(target_date_iso)
        except ValueError:
            logger.error(
                "calc_engagement.invalid_date user_id=%s date=%s",
                user_id, target_date_iso,
            )
            return {"status": "error", "reason": "invalid_date"}

    try:
        score_obj = EngagementScoreService.calculate_for_user(
            user=user, target_date=target
        )
        logger.info(
            "calc_engagement.done user_id=%s date=%s score=%s",
            user_id, score_obj.date, score_obj.score,
        )
        return {
            "status":  "ok",
            "user_id": str(user_id),
            "date":    str(score_obj.date),
            "score":   float(score_obj.score),
            "tier":    score_obj.tier,
        }

    except Exception as exc:
        logger.exception(
            "calc_engagement.error user_id=%s attempt=%d",
            user_id, self.request.retries,
        )
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "calc_engagement.max_retries_exceeded user_id=%s",
                user_id,
            )
            return {"status": "error", "reason": "max_retries_exceeded"}


# =============================================================================
# Batch engagement recalculation (e.g. daily Celery beat job)
# =============================================================================

@shared_task(
    bind=True,
    name="behavior_analytics.tasks.recalculate_all_engagement",
    max_retries=1,
    default_retry_delay=300,
    acks_late=True,
)
def recalculate_all_engagement(self, target_date_iso: str | None = None) -> dict:
    """
    Enqueue individual engagement-score tasks for *all active users*.
    This task fans out work; it does not perform calculations itself.

    Typically scheduled via Celery beat once per day (e.g. 01:00 UTC).
    """
    target_iso = target_date_iso or timezone.localdate().isoformat()

    users = User.objects.filter(is_active=True).values_list("pk", flat=True)
    count = 0
    for uid in users:
        calculate_engagement_score.delay(str(uid), target_iso)
        count += 1

    logger.info("recalculate_all_engagement.dispatched count=%d date=%s", count, target_iso)
    return {"status": "ok", "dispatched": count, "date": target_iso}


# =============================================================================
# Click batch processing
# =============================================================================

@shared_task(
    bind=True,
    name=TASK_PROCESS_CLICK_BATCH,
    max_retries=5,
    default_retry_delay=30,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_click_batch(
    self,
    path_id: str,
    events: list[dict],
) -> dict[str, Any]:
    """
    Bulk-persist a list of click events for the given path_id.

    This task is typically enqueued by the tracking middleware when it
    accumulates a batch of events without wanting to block the HTTP response.
    """
    from .models import UserPath
    from api.behavior_analytics.services import ClickMetricService

    try:
        path = UserPath.objects.get(pk=path_id)
    except UserPath.DoesNotExist:
        logger.error("process_click_batch.path_not_found path_id=%s", path_id)
        return {"status": "error", "reason": "path_not_found"}

    try:
        created = ClickMetricService.bulk_record(path=path, events=events)
        logger.info(
            "process_click_batch.done path_id=%s count=%d",
            path_id, len(created),
        )
        return {"status": "ok", "created": len(created)}
    except Exception as exc:
        logger.exception(
            "process_click_batch.error path_id=%s attempt=%d",
            path_id, self.request.retries,
        )
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"status": "error", "reason": "max_retries_exceeded"}


# =============================================================================
# Report generation
# =============================================================================

@shared_task(
    bind=True,
    name=TASK_GENERATE_DAILY_REPORT,
    max_retries=2,
    default_retry_delay=120,
    acks_late=True,
)
def generate_daily_report(self, report_date_iso: str | None = None) -> dict:
    """
    Generate (or regenerate) the daily analytics report for `report_date_iso`.
    Defaults to yesterday so the full day's data is available.
    """
    from .reports.daily_report import DailyReportGenerator

    try:
        target = (
            date.fromisoformat(report_date_iso)
            if report_date_iso
            else timezone.localdate() - timedelta(days=1)
        )
        result = DailyReportGenerator().generate(target_date=target)
        logger.info(
            "daily_report.generated date=%s rows=%s",
            target, result.get("row_count", "?"),
        )
        return {"status": "ok", "date": str(target), **result}
    except Exception as exc:
        logger.exception(
            "daily_report.error date=%s attempt=%d",
            report_date_iso, self.request.retries,
        )
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"status": "error", "reason": "max_retries_exceeded"}


@shared_task(
    bind=True,
    name=TASK_GENERATE_WEEKLY_REPORT,
    max_retries=2,
    default_retry_delay=300,
    acks_late=True,
)
def generate_weekly_report(self, week_start_iso: str | None = None) -> dict:
    """
    Generate the weekly analytics report.
    week_start_iso should be a Monday date (ISO-8601).
    Defaults to the previous ISO week.
    """
    from .reports.weekly_analytics import WeeklyReportGenerator

    try:
        if week_start_iso:
            week_start = date.fromisoformat(week_start_iso)
        else:
            today      = timezone.localdate()
            week_start = today - timedelta(days=today.weekday() + 7)

        result = WeeklyReportGenerator().generate(week_start=week_start)
        logger.info("weekly_report.generated week_start=%s", week_start)
        return {"status": "ok", "week_start": str(week_start), **result}
    except Exception as exc:
        logger.exception(
            "weekly_report.error week_start=%s attempt=%d",
            week_start_iso, self.request.retries,
        )
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"status": "error", "reason": "max_retries_exceeded"}


# =============================================================================
# Cleanup
# =============================================================================

@shared_task(
    bind=True,
    name=TASK_CLEANUP_OLD_PATHS,
    max_retries=1,
    acks_late=True,
)
def cleanup_old_paths(self) -> dict:
    """
    Delete UserPath records (and cascade: ClickMetric, StayTime) older than
    REPORT_DAILY_RETENTION_DAYS.  Runs in chunks to avoid lock contention.
    """
    from .models import UserPath

    CHUNK = 1_000
    cutoff = timezone.now() - timedelta(days=REPORT_DAILY_RETENTION_DAYS)

    total_deleted = 0
    while True:
        ids = list(
            UserPath.objects.filter(created_at__lt=cutoff)
            .values_list("pk", flat=True)[:CHUNK]
        )
        if not ids:
            break
        deleted, _ = UserPath.objects.filter(pk__in=ids).delete()
        total_deleted += deleted
        logger.info("cleanup_old_paths.chunk_deleted count=%d", deleted)

    logger.info(
        "cleanup_old_paths.done total_deleted=%d cutoff=%s",
        total_deleted, cutoff.date(),
    )
    return {"status": "ok", "total_deleted": total_deleted}

