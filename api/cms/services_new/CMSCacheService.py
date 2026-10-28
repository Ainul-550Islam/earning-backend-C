# api/cms/services/CMSCacheService.py
"""
CMSCacheService: Cache invalidation on content change, bulk clearing.
"""
import logging
from typing import List, Optional, Any

from django.core.cache import cache

logger = logging.getLogger(__name__)


class CMSCacheService:
    """Centralized cache management for CMS content."""

    # Cache key patterns by content type
    KEY_PATTERNS = {
        'blog_post': ['blog_post_{slug}', 'blog_post_{uuid}', 'blog_related_{id}_*'],
        'blog_category': ['blog_category_{slug}', 'blog_categories_tree', 'blog_categories_counts'],
        'media_file': ['media_file_{id}', 'media_folder_tree'],
        'popup': ['popup_{uuid}', 'active_popups'],
        'menu': ['menu_{slug}', 'menu_{id}', 'menu_location_{location}'],
        'seo_config': ['seo_config_active'],
        'sitemap': ['sitemap_xml'],
        'robots': ['robots_txt', 'robots_config_active'],
        'redirect': ['redirect_{from_url}', 'redirect_map'],
    }

    @classmethod
    def invalidate_blog_post(cls, post) -> None:
        """Invalidate all caches for a blog post."""
        try:
            keys = [
                f'blog_post_{post.slug}',
                f'blog_post_{post.uuid}',
                f'blog_related_{post.id}_5',
                f'blog_related_{post.id}_10',
                'blog_featured_posts',
                'blog_statistics_overall',
                'blog_categories_counts',
            ]
            if post.category:
                keys.append(f'blog_category_{post.category.slug}')
            cache.delete_many(keys)
            logger.debug(f"Invalidated cache for blog post {post.id}")
        except Exception as e:
            logger.warning(f"Cache invalidation error (blog post): {e}")

    @classmethod
    def invalidate_media_file(cls, file) -> None:
        """Invalidate caches for a media file."""
        try:
            cache.delete(f'media_file_{file.id}')
            cache.delete('media_folder_tree')
        except Exception as e:
            logger.warning(f"Cache invalidation error (media file): {e}")

    @classmethod
    def invalidate_popup(cls, popup) -> None:
        """Invalidate popup caches."""
        try:
            cache.delete(f'popup_{popup.uuid}')
            cache.delete('active_popups')
        except Exception as e:
            logger.warning(f"Cache invalidation error (popup): {e}")

    @classmethod
    def invalidate_menu(cls, menu) -> None:
        """Invalidate menu caches."""
        try:
            cache.delete(f'menu_{menu.slug}')
            cache.delete(f'menu_{menu.id}')
            cache.delete(f'menu_location_{menu.location}')
            for v in range(1, menu.cache_version + 1):
                cache.delete(f'menu_tree_{menu.id}_v{v}')
        except Exception as e:
            logger.warning(f"Cache invalidation error (menu): {e}")

    @classmethod
    def invalidate_seo(cls) -> None:
        """Invalidate SEO-related caches."""
        try:
            cache.delete('seo_config_active')
            cache.delete('sitemap_xml')
            cache.delete('robots_txt')
            cache.delete('robots_config_active')
        except Exception as e:
            logger.warning(f"Cache invalidation error (SEO): {e}")

    @classmethod
    def invalidate_content_page(cls, page) -> None:
        """Invalidate CMS content page caches."""
        try:
            keys = [
                f'content_url_{page.uuid}',
                f'content_{page.slug}',
                'featured_content_en_10',
                'popular_content_en_30_10',
                'content_statistics',
            ]
            cache.delete_many(keys)
        except Exception as e:
            logger.warning(f"Cache invalidation error (content page): {e}")

    @classmethod
    def clear_all_cms_caches(cls) -> None:
        """Clear ALL CMS-related caches. Use with caution."""
        try:
            # Clear known pattern keys
            generic_keys = [
                'blog_featured_posts', 'blog_statistics_overall',
                'blog_categories_counts', 'blog_categories_tree',
                'active_popups', 'media_folder_tree',
                'seo_config_active', 'sitemap_xml',
                'robots_txt', 'robots_config_active',
                'redirect_map', 'content_statistics',
                'faq_statistics', 'faq_categories_with_counts',
                'banner_statistics_overall',
            ]
            cache.delete_many(generic_keys)
            logger.info("Cleared all CMS caches")
        except Exception as e:
            logger.error(f"Error clearing CMS caches: {e}")

    @classmethod
    def warm_blog_cache(cls) -> None:
        """Pre-warm blog post caches for popular posts."""
        try:
            from api.cms.models_new.blog import BlogPost
            from api.cms.services_new.BlogService import BlogService
            posts = BlogPost.objects.filter(
                status='published', is_active=True
            ).order_by('-views_count')[:20]
            for post in posts:
                cache.set(f'blog_post_{post.slug}', post, 1800)
            logger.info(f"Warmed cache for {len(posts)} blog posts")
        except Exception as e:
            logger.warning(f"Cache warm-up error: {e}")
