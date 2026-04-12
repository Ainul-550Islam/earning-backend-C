import logging
import datetime
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('smartlink.tasks.cleanup')


@shared_task(name='smartlink.archive_old_clicks', queue='maintenance')
def archive_old_clicks(days: int = 90):
    """
    Weekly: Move clicks older than N days to archive table / cold storage.
    Keeps hot click table fast for recent analytics queries.
    """
    from ..models import Click
    cutoff = timezone.now() - datetime.timedelta(days=days)
    old_qs = Click.objects.filter(created_at__lt=cutoff)
    count = old_qs.count()

    # In production: move to ClickArchive table or export to S3/BigQuery
    # For now: soft delete (mark archived)
    old_qs.delete()
    logger.info(f"Archived {count} clicks older than {days} days")
    return {'archived': count, 'cutoff': str(cutoff.date())}


@shared_task(name='smartlink.cleanup_old_redirect_logs', queue='maintenance')
def cleanup_old_redirect_logs(days: int = 30):
    """Monthly: Remove redirect logs older than N days."""
    from ..models import RedirectLog
    cutoff = timezone.now() - datetime.timedelta(days=days)
    count, _ = RedirectLog.objects.filter(created_at__lt=cutoff).delete()
    logger.info(f"Deleted {count} redirect logs older than {days} days")
    return {'deleted': count}


@shared_task(name='smartlink.cleanup_old_rotation_logs', queue='maintenance')
def cleanup_old_rotation_logs(days: int = 14):
    """Weekly: Remove offer rotation logs older than N days."""
    from ..models import OfferRotationLog
    cutoff = timezone.now() - datetime.timedelta(days=days)
    count, _ = OfferRotationLog.objects.filter(created_at__lt=cutoff).delete()
    logger.info(f"Deleted {count} rotation logs older than {days} days")
    return {'deleted': count}


@shared_task(name='smartlink.cleanup_bot_clicks', queue='maintenance')
def cleanup_bot_clicks(days: int = 30):
    """Monthly: Remove bot click records older than N days."""
    from ..models import BotClick
    cutoff = timezone.now() - datetime.timedelta(days=days)
    count, _ = BotClick.objects.filter(created_at__lt=cutoff).delete()
    logger.info(f"Deleted {count} bot clicks older than {days} days")
    return {'deleted': count}


@shared_task(name='smartlink.cleanup_expired_unique_clicks', queue='maintenance')
def cleanup_expired_unique_clicks(days: int = 7):
    """Weekly: Remove UniqueClick dedup records older than N days."""
    from ..models import UniqueClick
    cutoff = timezone.now().date() - datetime.timedelta(days=days)
    count, _ = UniqueClick.objects.filter(date__lt=cutoff).delete()
    logger.info(f"Deleted {count} expired unique click records")
    return {'deleted': count}
