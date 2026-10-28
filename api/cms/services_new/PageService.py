# api/cms/services/PageService.py
"""
PageService: CMS page CRUD, slug generation, publishing, preview, versioning.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any

from django.db import transaction
from django.db.models import Q, F, Count, Sum, Avg
from django.utils import timezone
from django.utils.text import slugify
from django.core.cache import cache

logger = logging.getLogger(__name__)


class PageService:
    """Service for CMS content page management."""

    # ────────────────────────────────────────────────────
    # CRUD
    # ────────────────────────────────────────────────────

    @staticmethod
    def create_page(
        title: str,
        content: str,
        author=None,
        category=None,
        page_type: str = 'static',
        status: str = 'draft',
        **kwargs
    ) -> Optional[Any]:
        """Create a new content page."""
        from api.cms.models import ContentPage
        try:
            with transaction.atomic():
                slug = PageService._generate_unique_slug(title)
                page = ContentPage.objects.create(
                    title=title,
                    slug=slug,
                    content=content,
                    author=author,
                    category=category,
                    page_type=page_type,
                    status=status,
                    **kwargs
                )
                logger.info(f"Created page '{page.title}' (id={page.id})")
                return page
        except Exception as e:
            logger.error(f"Error creating page: {e}", exc_info=True)
            return None

    @staticmethod
    def update_page(page, data: Dict[str, Any]) -> bool:
        """Update an existing content page."""
        try:
            with transaction.atomic():
                if 'title' in data and data['title'] != page.title:
                    data['slug'] = PageService._generate_unique_slug(data['title'], exclude_id=page.id)
                for field, value in data.items():
                    if hasattr(page, field):
                        setattr(page, field, value)
                page.save()
                cache.delete(f'content_{page.slug}')
                cache.delete(f'content_url_{page.uuid}')
                logger.info(f"Updated page '{page.title}' (id={page.id})")
                return True
        except Exception as e:
            logger.error(f"Error updating page {page.id}: {e}", exc_info=True)
            return False

    @staticmethod
    def delete_page(page, soft: bool = True) -> bool:
        """Soft or hard delete a content page."""
        try:
            with transaction.atomic():
                if soft:
                    page.status = 'archived'
                    page.is_active = False
                    page.save(update_fields=['status', 'is_active'])
                else:
                    page.delete()
                cache.delete(f'content_{page.slug}')
                return True
        except Exception as e:
            logger.error(f"Error deleting page {page.id}: {e}", exc_info=True)
            return False

    @staticmethod
    def get_page(slug: str, user=None, preview: bool = False) -> Optional[Any]:
        """Get a content page by slug with optional preview mode."""
        from api.cms.models import ContentPage
        try:
            page = ContentPage.objects.select_related(
                'category', 'author', 'related_offer', 'related_task'
            ).get(slug=slug)
            if not preview and not PageService._can_view(page, user):
                return None
            page.increment_view_count()
            return page
        except ContentPage.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting page by slug '{slug}': {e}")
            return None

    @staticmethod
    def _can_view(page, user) -> bool:
        if not page.is_active:
            return False
        if page.status == 'published':
            if page.visibility == 'public':
                return True
            if page.visibility == 'authenticated':
                return user and user.is_authenticated
            if page.visibility in ('vip', 'admin'):
                return user and user.is_staff
        if user and user.is_staff:
            return True
        return False

    # ────────────────────────────────────────────────────
    # LISTING
    # ────────────────────────────────────────────────────

    @staticmethod
    def list_pages(
        category_id: Optional[int] = None,
        page_type: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        language: str = 'en',
        limit: int = 20,
        offset: int = 0,
        order_by: str = '-published_date',
        user=None
    ) -> Tuple[List, int]:
        """List pages with filtering and pagination."""
        from api.cms.models import ContentPage
        try:
            q = Q(is_active=True)
            if status:
                q &= Q(status=status)
            else:
                q &= Q(status='published')
            if language:
                q &= Q(language=language)
            if category_id:
                q &= Q(category_id=category_id)
            if page_type:
                q &= Q(page_type=page_type)
            if search:
                q &= Q(title__icontains=search) | Q(excerpt__icontains=search)
            # Visibility
            if not (user and user.is_staff):
                if user and user.is_authenticated:
                    q &= Q(visibility__in=['public', 'authenticated'])
                else:
                    q &= Q(visibility='public')

            total = ContentPage.objects.filter(q).count()
            pages = (
                ContentPage.objects.filter(q)
                .select_related('category', 'author')
                .order_by(order_by)[offset:offset + limit]
            )
            return list(pages), total
        except Exception as e:
            logger.error(f"Error listing pages: {e}", exc_info=True)
            return [], 0

    # ────────────────────────────────────────────────────
    # PUBLISHING
    # ────────────────────────────────────────────────────

    @staticmethod
    def publish_page(page, publish_date: Optional[datetime] = None) -> bool:
        """Publish a content page."""
        try:
            page.status = 'published'
            page.published_date = publish_date or timezone.now()
            page.save(update_fields=['status', 'published_date'])
            cache.delete(f'content_{page.slug}')
            logger.info(f"Published page '{page.title}' (id={page.id})")
            return True
        except Exception as e:
            logger.error(f"Error publishing page {page.id}: {e}", exc_info=True)
            return False

    @staticmethod
    def schedule_page(page, scheduled_date: datetime) -> bool:
        """Schedule a page for future publishing."""
        try:
            if scheduled_date <= timezone.now():
                raise ValueError("Scheduled date must be in the future.")
            page.status = 'scheduled'
            page.scheduled_date = scheduled_date
            page.save(update_fields=['status', 'scheduled_date'])
            return True
        except Exception as e:
            logger.error(f"Error scheduling page {page.id}: {e}", exc_info=True)
            return False

    @staticmethod
    def unpublish_page(page) -> bool:
        """Revert page to draft."""
        try:
            page.status = 'draft'
            page.save(update_fields=['status'])
            cache.delete(f'content_{page.slug}')
            return True
        except Exception as e:
            logger.error(f"Error unpublishing page {page.id}: {e}", exc_info=True)
            return False

    @staticmethod
    def publish_scheduled_pages() -> int:
        """Publish all scheduled pages whose time has come."""
        from api.cms.models import ContentPage
        now = timezone.now()
        pages = ContentPage.objects.filter(
            status='scheduled', scheduled_date__lte=now, is_active=True
        )
        count = 0
        for page in pages:
            if PageService.publish_page(page, publish_date=page.scheduled_date):
                count += 1
        logger.info(f"Published {count} scheduled pages")
        return count

    # ────────────────────────────────────────────────────
    # VERSIONING
    # ────────────────────────────────────────────────────

    @staticmethod
    def create_version(page) -> Optional[Any]:
        """Create a new version of a content page."""
        try:
            new_version = page.create_new_version()
            return new_version
        except Exception as e:
            logger.error(f"Error creating version for page {page.id}: {e}", exc_info=True)
            return None

    @staticmethod
    def get_version_history(page) -> List:
        """Get complete version history of a page."""
        return page.get_version_history()

    # ────────────────────────────────────────────────────
    # SLUG
    # ────────────────────────────────────────────────────

    @staticmethod
    def _generate_unique_slug(title: str, exclude_id: Optional[int] = None) -> str:
        from api.cms.models import ContentPage
        base_slug = slugify(title)[:200] or 'page'
        slug = base_slug
        counter = 1
        while True:
            qs = ContentPage.objects.filter(slug=slug)
            if exclude_id:
                qs = qs.exclude(id=exclude_id)
            if not qs.exists():
                break
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    # ────────────────────────────────────────────────────
    # STATISTICS
    # ────────────────────────────────────────────────────

    @staticmethod
    def get_page_statistics() -> Dict[str, Any]:
        """Get overall page statistics."""
        from api.cms.models import ContentPage
        cache_key = 'page_statistics'
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            total = ContentPage.objects.count()
            published = ContentPage.objects.filter(status='published', is_active=True).count()
            drafts = ContentPage.objects.filter(status='draft').count()
            total_views = ContentPage.objects.aggregate(t=Sum('view_count'))['t'] or 0
            top_pages = list(
                ContentPage.objects.filter(status='published', is_active=True)
                .order_by('-view_count')[:5]
                .values('id', 'title', 'slug', 'view_count', 'published_date')
            )
            stats = {
                'total': total, 'published': published, 'drafts': drafts,
                'total_views': total_views, 'top_pages': top_pages,
            }
            cache.set(cache_key, stats, 300)
            return stats
        except Exception as e:
            logger.error(f"Error getting page statistics: {e}", exc_info=True)
            return {}
