# api/cms/services/CMSPublishService.py
"""
CMSPublishService: Draft → Publish workflow for all CMS content types.
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class CMSPublishService:
    """Unified publish workflow for all CMS content types."""

    @staticmethod
    def publish(obj, content_type: str, publish_date: Optional[datetime] = None, user=None) -> bool:
        """
        Publish any CMS content object.

        Args:
            obj: Model instance (ContentPage, BlogPost, etc.)
            content_type: 'page', 'blog', 'popup', 'banner', 'menu'
            publish_date: Optional backdated publish date
            user: User performing the action

        Returns:
            True on success
        """
        try:
            handler = {
                'page': CMSPublishService._publish_page,
                'blog': CMSPublishService._publish_blog,
                'popup': CMSPublishService._publish_popup,
                'banner': CMSPublishService._publish_banner,
            }.get(content_type)

            if not handler:
                logger.warning(f"Unknown content type for publish: {content_type}")
                return False

            result = handler(obj, publish_date=publish_date)
            if result and user:
                logger.info(f"User {user.id} published {content_type} id={obj.id}")
            return result
        except Exception as e:
            logger.error(f"Error in CMSPublishService.publish: {e}", exc_info=True)
            return False

    @staticmethod
    def _publish_page(page, publish_date=None) -> bool:
        from api.cms.services_new.PageService import PageService
        return PageService.publish_page(page, publish_date=publish_date)

    @staticmethod
    def _publish_blog(post, publish_date=None) -> bool:
        from api.cms.services_new.BlogService import BlogService
        return BlogService.publish_post(post, publish_date=publish_date)

    @staticmethod
    def _publish_popup(popup, publish_date=None) -> bool:
        try:
            popup.status = 'active'
            popup.is_active = True
            if publish_date:
                popup.start_date = publish_date
            popup.save(update_fields=['status', 'is_active', 'start_date'])
            return True
        except Exception as e:
            logger.error(f"Error publishing popup: {e}")
            return False

    @staticmethod
    def _publish_banner(banner, publish_date=None) -> bool:
        try:
            banner.is_active = True
            if publish_date:
                banner.start_date = publish_date
            banner.save(update_fields=['is_active', 'start_date'])
            return True
        except Exception as e:
            logger.error(f"Error publishing banner: {e}")
            return False

    @staticmethod
    def unpublish(obj, content_type: str, user=None) -> bool:
        """Unpublish/revert any CMS content object to draft."""
        try:
            if content_type in ('page',):
                from api.cms.services_new.PageService import PageService
                return PageService.unpublish_page(obj)
            elif content_type == 'blog':
                from api.cms.services_new.BlogService import BlogService
                return BlogService.unpublish_post(obj)
            elif content_type == 'popup':
                obj.status = 'paused'
                obj.save(update_fields=['status'])
                return True
            elif content_type == 'banner':
                obj.is_active = False
                obj.save(update_fields=['is_active'])
                return True
            return False
        except Exception as e:
            logger.error(f"Error unpublishing {content_type}: {e}", exc_info=True)
            return False

    @staticmethod
    def bulk_publish(obj_ids: List[int], content_type: str, user=None) -> int:
        """Bulk publish multiple content objects."""
        count = 0
        if content_type == 'blog':
            from api.cms.services_new.BlogService import BlogService
            count = BlogService.bulk_publish(obj_ids, user=user)
        elif content_type == 'page':
            from api.cms.models import ContentPage
            now = timezone.now()
            count = ContentPage.objects.filter(id__in=obj_ids).update(
                status='published', published_date=now
            )
        return count

    @staticmethod
    def publish_scheduled_all() -> Dict[str, int]:
        """Run all scheduled publishes across content types."""
        from api.cms.services_new.BlogService import BlogService
        from api.cms.services_new.PageService import PageService
        results = {}
        results['blog'] = BlogService.publish_scheduled_posts()
        results['page'] = PageService.publish_scheduled_pages()
        logger.info(f"Scheduled publish run: {results}")
        return results
