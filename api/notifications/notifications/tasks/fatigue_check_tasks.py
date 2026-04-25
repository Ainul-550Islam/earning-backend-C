# earning_backend/api/notifications/tasks/fatigue_check_tasks.py
"""
Fatigue check tasks — daily/weekly counter resets and fatigue flag recalculation.

Schedule via Celery Beat:
    reset_daily_fatigue_counters   — daily at 00:01 UTC
    reset_weekly_fatigue_counters  — every Monday at 00:05 UTC
    recalculate_fatigue_flags      — every 6 hours
"""
import logging
from datetime import timedelta

from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

logger = get_task_logger(__name__)


@shared_task(
    queue='notifications_maintenance',
    name='notifications.reset_daily_fatigue_counters',
)
def reset_daily_fatigue_counters():
    """
    Reset daily notification send counters for all users.
    Run every day at 00:01 UTC via Celery Beat.
    """
    from api.notifications.services.FatigueService import fatigue_service

    result = fatigue_service.reset_daily_counters()
    logger.info(
        f'reset_daily_fatigue_counters: reset={result["reset_count"]} '
        f'errors={result["errors"]}'
    )
    return result


@shared_task(
    queue='notifications_maintenance',
    name='notifications.reset_weekly_fatigue_counters',
)
def reset_weekly_fatigue_counters():
    """
    Reset weekly notification send counters for all users.
    Run every Monday at 00:05 UTC via Celery Beat.
    """
    from api.notifications.services.FatigueService import fatigue_service

    result = fatigue_service.reset_weekly_counters()
    logger.info(
        f'reset_weekly_fatigue_counters: reset={result["reset_count"]} '
        f'errors={result["errors"]}'
    )
    return result


@shared_task(
    queue='notifications_maintenance',
    name='notifications.recalculate_fatigue_flags',
)
def recalculate_fatigue_flags():
    """
    Re-evaluate the is_fatigued flag for all users based on current counters.
    Run every 6 hours via Celery Beat, and also after system-wide limit changes.
    """
    from api.notifications.services.FatigueService import fatigue_service

    result = fatigue_service.recalculate_all()
    logger.info(
        f'recalculate_fatigue_flags: evaluated={result["evaluated_count"]} '
        f'fatigued={result["fatigued_count"]} errors={result["errors"]}'
    )
    return result


@shared_task(
    queue='notifications_maintenance',
    name='notifications.reset_monthly_fatigue_counters',
)
def reset_monthly_fatigue_counters():
    """
    Reset monthly send counters for all users.
    Run on the 1st of each month at 00:10 UTC via Celery Beat.
    """
    from api.notifications.models.analytics import NotificationFatigue

    reset_count = 0
    errors = 0

    for record in NotificationFatigue.objects.all().iterator(chunk_size=500):
        try:
            record.reset_monthly(save=True)
            reset_count += 1
        except Exception as exc:
            logger.warning(f'reset_monthly_fatigue_counters user {record.user_id}: {exc}')
            errors += 1

    logger.info(f'reset_monthly_fatigue_counters: reset={reset_count} errors={errors}')
    return {'reset_count': reset_count, 'errors': errors}


@shared_task(
    bind=True,
    queue='notifications_maintenance',
    name='notifications.clear_user_fatigue',
)
def clear_user_fatigue_task(self, user_id: int):
    """
    Manually clear the fatigue flag for a specific user.
    Called by admin actions.
    """
    from django.contrib.auth import get_user_model
    from api.notifications.services.FatigueService import fatigue_service

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
        result = fatigue_service.clear_fatigue(user)
        logger.info(f'clear_user_fatigue_task: user #{user_id} fatigue cleared')
        return result
    except User.DoesNotExist:
        logger.warning(f'clear_user_fatigue_task: user #{user_id} not found')
        return {'success': False, 'error': 'User not found'}
    except Exception as exc:
        logger.error(f'clear_user_fatigue_task user #{user_id}: {exc}')
        return {'success': False, 'error': str(exc)}


@shared_task(
    queue='notifications_maintenance',
    name='notifications.create_missing_fatigue_records',
)
def create_missing_fatigue_records():
    """
    Ensure every active user has a NotificationFatigue record.
    Run once after deployment, then weekly as a safety net.
    """
    from django.contrib.auth import get_user_model
    from api.notifications.models.analytics import NotificationFatigue

    User = get_user_model()

    existing_user_ids = set(
        NotificationFatigue.objects.values_list('user_id', flat=True)
    )
    all_active_user_ids = set(
        User.objects.filter(is_active=True).values_list('pk', flat=True)
    )

    missing_ids = all_active_user_ids - existing_user_ids
    created = 0
    errors = 0

    for user_id in missing_ids:
        try:
            NotificationFatigue.objects.get_or_create(user_id=user_id)
            created += 1
        except Exception as exc:
            logger.warning(f'create_missing_fatigue_records user {user_id}: {exc}')
            errors += 1

    logger.info(f'create_missing_fatigue_records: created={created} errors={errors}')
    return {'created': created, 'errors': errors}
