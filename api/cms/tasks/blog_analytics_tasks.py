# api/cms/tasks/blog_analytics_tasks.py
"""Daily blog view stats collection."""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='cms.tasks.collect_blog_analytics', bind=True)
def collect_blog_analytics(self):
    """Collect and cache daily blog analytics."""
    try:
        from api.cms.services_new.CMSAnalyticsService import CMSAnalyticsService
        result = CMSAnalyticsService.get_blog_reads(days=1)
        logger.info(f"[Task] Blog analytics collected: {result.get('total_reads', 0)} reads today")
        return {'status': 'success', 'data': result}
    except Exception as exc:
        logger.error(f"[Task] Blog analytics collection failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='cms.tasks.update_blog_view_counts', bind=True)
def update_blog_view_counts(self):
    """Update blog post view count caches."""
    try:
        from api.cms.models_new.blog import BlogPost
        from django.db.models import F
        # Refresh view counts from DB
        posts = BlogPost.objects.filter(status='published', is_active=True).order_by('-views_count')[:100]
        from django.core.cache import cache
        for post in posts:
            cache.set(f'blog_views_{post.id}', post.views_count, 3600)
        logger.info(f"[Task] Updated view counts for {posts.count()} blog posts")
        return {'status': 'success', 'updated': posts.count()}
    except Exception as exc:
        logger.error(f"[Task] Blog view count update failed: {exc}", exc_info=True)
        raise
