"""
NEW FILE — Celery tasks for Feature Flags & A/B Testing.

These move work that was previously either (a) done synchronously inside
the broken `FlagAnalyticsMiddleware` (100+ queries per request) or (b)
not implemented at all (scheduled changes, cache warmup, analytics
cleanup) off the request/response cycle and into background workers.
"""
import logging
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger('feature_flags')


@shared_task(bind=True, max_retries=3, queue='analytics')
def track_request_analytics(self, context: dict):
    """
    Asynchronously record flag-evaluation analytics for a single request.

    FIX: this is the async replacement for what the old synchronous
    `FlagAnalyticsMiddleware` did inline (fetch every active flag,
    re-evaluate each one, write analytics rows) — now it happens in a
    worker, off the request path, and only does work for flags that are
    actually active.
    """
    from .flag_engine import FlagEngine
    from .utils import update_flag_analytics
    from .models.flag_analytics import FlagAnalytics  # noqa: F401 (imported for clarity)

    try:
        engine = FlagEngine()
        environment = settings.FEATURE_FLAGS['DEFAULT_ENVIRONMENT']
        active_flags = engine.get_active_flags(environment)

        for flag in active_flags:
            is_enabled = engine.is_enabled(flag.name, context, environment)
            if is_enabled:
                update_flag_analytics(flag, None, context.get('user_id', ''))
    except Exception as exc:
        logger.exception('track_request_analytics failed')
        raise self.retry(exc=exc, countdown=10)


@shared_task
def track_flag_evaluation_async(flag_name: str, user_id: str, enabled: bool):
    """Lightweight single-flag analytics write, used by decorators/services
    that evaluate one specific flag rather than the whole portfolio."""
    from .models.feature_flag import FeatureFlag
    from .utils import update_flag_analytics

    try:
        flag = FeatureFlag.objects.get(name=flag_name)
    except FeatureFlag.DoesNotExist:
        return
    update_flag_analytics(flag, None, user_id)


@shared_task
def cleanup_old_analytics():
    """Delete FlagAnalytics rows older than FEATURE_FLAGS['ANALYTICS_RETENTION_DAYS']."""
    from .models.flag_analytics import FlagAnalytics

    retention_days = settings.FEATURE_FLAGS.get('ANALYTICS_RETENTION_DAYS', 30)
    cutoff = timezone.now().date() - timedelta(days=retention_days)
    deleted, _ = FlagAnalytics.objects.filter(date__lt=cutoff).delete()
    logger.info('cleanup_old_analytics removed %s rows older than %s', deleted, cutoff)
    return deleted


@shared_task
def warmup_flag_cache():
    """Pre-populate the flag cache for every active flag in every environment
    so the first real request after a deploy/cache-flush isn't a cache miss."""
    from .flag_engine import FlagEngine
    from .utils import FlagCacheManager

    engine = FlagEngine()
    warmed = 0
    for environment in settings.FEATURE_FLAGS.get('ENVIRONMENTS', ['production']):
        for flag in engine.get_active_flags(environment):
            FlagCacheManager.set_enabled(flag.name, flag.rollout_percentage == 100, environment)
            warmed += 1
    logger.info('warmup_flag_cache warmed %s flag cache entries', warmed)
    return warmed


@shared_task
def execute_scheduled_changes():
    """
    Apply due scheduled flag changes. NEW — implements Missing Component
    #9 (Scheduling): previously there was no way to schedule a future
    activation/pause without a human doing it at the exact time.
    """
    from .models.scheduling import ScheduledChange

    now = timezone.now()
    due = ScheduledChange.objects.filter(scheduled_for__lte=now, executed=False)

    applied = 0
    for change in due:
        flag = change.flag
        if change.change_type == ScheduledChange.ChangeType.ACTIVATE:
            flag.status = flag.Status.ACTIVE
        elif change.change_type == ScheduledChange.ChangeType.PAUSE:
            flag.status = flag.Status.PAUSED
        elif change.change_type == ScheduledChange.ChangeType.ARCHIVE:
            flag.status = flag.Status.ARCHIVED

        if change.target_rollout_percentage is not None:
            flag.rollout_percentage = change.target_rollout_percentage

        flag.save()

        change.executed = True
        change.executed_at = now
        change.save(update_fields=['executed', 'executed_at'])
        applied += 1

    if applied:
        logger.info('execute_scheduled_changes applied %s scheduled changes', applied)
    return applied
