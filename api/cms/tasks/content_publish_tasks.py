# api/cms/tasks/content_publish_tasks.py
"""Scheduled content publishing task."""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='cms.tasks.publish_scheduled_content', bind=True)
def publish_scheduled_content(self):
    """Publish all scheduled blog posts and CMS pages whose time has come."""
    try:
        from api.cms.services_new.CMSPublishService import CMSPublishService
        results = CMSPublishService.publish_scheduled_all()
        logger.info(f"[Task] Scheduled publish run: {results}")
        return {'status': 'success', **results}
    except Exception as exc:
        logger.error(f"[Task] Scheduled content publish failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)


@shared_task(name='cms.tasks.expire_old_content', bind=True)
def expire_old_content(self):
    """Mark content as expired if expiry_date has passed."""
    try:
        from api.cms.models import ContentPage
        from django.utils import timezone
        from django.db.models import Q
        expired = ContentPage.objects.filter(
            expiry_date__lt=timezone.now(),
            is_active=True,
        ).exclude(status='expired')
        count = expired.update(status='expired')
        logger.info(f"[Task] Marked {count} content pages as expired")
        return {'status': 'success', 'expired': count}
    except Exception as exc:
        logger.error(f"[Task] Content expire task failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=120)


@shared_task(name='cms.tasks.deactivate_expired_banners', bind=True)
def deactivate_expired_banners(self):
    """Deactivate banners that have passed their end date."""
    try:
        from api.cms.models import Banner
        from django.utils import timezone
        count = Banner.objects.filter(
            end_date__lt=timezone.now(), is_active=True
        ).update(is_active=False)
        logger.info(f"[Task] Deactivated {count} expired banners")
        return {'status': 'success', 'deactivated': count}
    except Exception as exc:
        logger.error(f"[Task] Banner deactivation task failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=120)
