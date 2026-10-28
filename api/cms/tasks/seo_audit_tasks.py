# api/cms/tasks/seo_audit_tasks.py
"""Weekly SEO health check task."""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='cms.tasks.run_seo_audit', bind=True)
def run_seo_audit(self):
    """Run weekly SEO audit across all published content."""
    try:
        from api.cms.services_new.SEOService import SEOService
        issues = SEOService.audit_blog_seo()
        stats = SEOService.get_seo_statistics()
        logger.info(f"[Task] SEO audit complete: {len(issues)} issues found")
        return {
            'status': 'success',
            'issues_count': len(issues),
            'statistics': stats,
        }
    except Exception as exc:
        logger.error(f"[Task] SEO audit failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=600)


@shared_task(name='cms.tasks.auto_fill_missing_seo', bind=True)
def auto_fill_missing_seo(self):
    """Auto-fill SEO metadata for blog posts missing it."""
    try:
        from api.cms.models_new.blog import BlogPost, BlogSEO
        from api.cms.services_new.BlogService import BlogService
        posts_without_seo = BlogPost.objects.filter(
            status='published', is_active=True
        ).exclude(seo__isnull=False)
        count = 0
        for post in posts_without_seo:
            BlogService._auto_fill_seo(post)
            count += 1
        logger.info(f"[Task] Auto-filled SEO for {count} blog posts")
        return {'status': 'success', 'filled': count}
    except Exception as exc:
        logger.error(f"[Task] SEO auto-fill failed: {exc}", exc_info=True)
        raise
