# api/support/signals_kb.py
"""Knowledge base specific signals."""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='support.KBArticle')
def on_kb_article_saved(sender, instance, created, **kwargs):
    """When KB article published — invalidate caches and suggest to open tickets."""
    try:
        from api.support.cache import invalidate_kb_article
        invalidate_kb_article(instance.slug)
    except Exception as e:
        logger.debug(f'on_kb_article_saved cache: {e}')
    if created and instance.status == 'published':
        try:
            from api.support.notifications import notification_service
            notification_service.notify_new_kb_article(instance)
        except Exception as e:
            logger.debug(f'on_kb_article_saved notify: {e}')


@receiver(post_delete, sender='support.KBArticle')
def on_kb_article_deleted(sender, instance, **kwargs):
    """When KB article deleted — clear its cache."""
    try:
        from api.support.cache import invalidate_kb_article
        invalidate_kb_article(instance.slug)
    except Exception:
        pass


@receiver(post_save, sender='support.KBCategory')
def on_kb_category_saved(sender, instance, created, **kwargs):
    """When KB category saved — clear categories cache."""
    try:
        from django.core.cache import cache
        cache.delete('support:kb:categories:global')
    except Exception:
        pass