# api/cms/tasks/sitemap_tasks.py
"""Weekly sitemap regeneration task."""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='cms.tasks.regenerate_sitemap', bind=True, max_retries=3)
def regenerate_sitemap(self):
    """Regenerate sitemap weekly from all published content."""
    try:
        from api.cms.services_new.SEOService import SEOService
        count = SEOService.regenerate_sitemap()
        logger.info(f"[Task] Sitemap regenerated: {count} entries")
        return {'status': 'success', 'entries': count}
    except Exception as exc:
        logger.error(f"[Task] Sitemap regeneration failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=300)
