import logging
from celery import shared_task

logger = logging.getLogger('smartlink.tasks.cap')


@shared_task(name='smartlink.reset_daily_caps', queue='default')
def reset_daily_caps():
    """
    Midnight UTC: Reset all daily offer caps.
    Clears Redis counters and marks DB OfferCapTracker as reset.
    """
    try:
        from ..services.rotation.CapTrackerService import CapTrackerService
        svc = CapTrackerService()
        count = svc.reset_daily_caps()
        logger.info(f"Daily caps reset: {count} entries")
        return {'reset': count}
    except Exception as e:
        logger.error(f"reset_daily_caps failed: {e}")
        return {'error': str(e)}


@shared_task(name='smartlink.reset_monthly_caps', queue='default')
def reset_monthly_caps():
    """
    First day of each month: Reset monthly caps.
    """
    from django.utils import timezone
    from django.core.cache import cache
    from ..models import OfferPoolEntry

    entries = OfferPoolEntry.objects.filter(
        is_active=True, cap_per_month__isnull=False
    )
    now = timezone.now()
    prev_month = now.month - 1 if now.month > 1 else 12
    prev_year = now.year if now.month > 1 else now.year - 1
    month_key_part = f"{prev_year}-{prev_month:02d}"

    count = 0
    for entry in entries:
        cache.delete(f"cap:monthly:{entry.pk}:{month_key_part}")
        count += 1

    logger.info(f"Monthly caps reset: {count} entries for {month_key_part}")
    return {'reset': count}
