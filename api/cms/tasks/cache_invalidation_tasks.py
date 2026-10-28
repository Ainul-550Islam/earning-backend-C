# api/cms/tasks/cache_invalidation_tasks.py
"""Cache invalidation on content change."""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='cms.tasks.invalidate_blog_post_cache', bind=True)
def invalidate_blog_post_cache(self, post_id: int):
    """Invalidate all caches for a specific blog post."""
    try:
        from api.cms.models_new.blog import BlogPost
        from api.cms.services_new.CMSCacheService import CMSCacheService
        post = BlogPost.objects.get(id=post_id)
        CMSCacheService.invalidate_blog_post(post)
        logger.info(f"[Task] Cache invalidated for blog post {post_id}")
        return {'status': 'success', 'post_id': post_id}
    except Exception as exc:
        logger.error(f"[Task] Cache invalidation failed for post {post_id}: {exc}")
        raise self.retry(exc=exc, countdown=30)


@shared_task(name='cms.tasks.invalidate_all_cms_caches', bind=True)
def invalidate_all_cms_caches(self):
    """Invalidate ALL CMS caches. Use after major content updates."""
    try:
        from api.cms.services_new.CMSCacheService import CMSCacheService
        CMSCacheService.clear_all_cms_caches()
        logger.info("[Task] All CMS caches invalidated")
        return {'status': 'success'}
    except Exception as exc:
        logger.error(f"[Task] All CMS cache invalidation failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(name='cms.tasks.warm_blog_cache', bind=True)
def warm_blog_cache(self):
    """Pre-warm blog cache for popular posts."""
    try:
        from api.cms.services_new.CMSCacheService import CMSCacheService
        CMSCacheService.warm_blog_cache()
        logger.info("[Task] Blog cache warmed")
        return {'status': 'success'}
    except Exception as exc:
        logger.error(f"[Task] Blog cache warm failed: {exc}")
        raise
