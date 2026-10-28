# api/cms/services/SEOService.py
"""
SEOService: Sitemap generation, robots.txt management, SEO audit.
"""
import logging
from typing import Dict, List, Optional, Any

from django.db import transaction
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class SEOService:
    """Service for SEO management."""

    # ────────────────────────────────────────────────────
    # SITEMAP
    # ────────────────────────────────────────────────────

    @staticmethod
    def regenerate_sitemap() -> int:
        """
        Regenerate sitemap entries for all published content.
        Returns number of entries created/updated.
        """
        from api.cms.models_new.seo import Sitemap
        count = 0
        try:
            # Add blog posts
            count += SEOService._add_blog_posts_to_sitemap()
            # Add CMS content pages
            count += SEOService._add_content_pages_to_sitemap()
            logger.info(f"Regenerated sitemap with {count} entries")
            cache.delete('sitemap_xml')
        except Exception as e:
            logger.error(f"Error regenerating sitemap: {e}", exc_info=True)
        return count

    @staticmethod
    def _add_blog_posts_to_sitemap() -> int:
        """Add all published blog posts to sitemap."""
        from api.cms.models_new.blog import BlogPost
        from api.cms.models_new.seo import Sitemap
        count = 0
        try:
            posts = BlogPost.objects.filter(status='published', is_active=True)
            for post in posts:
                url = f"{SEOService._get_base_url()}{post.get_absolute_url()}"
                Sitemap.upsert_for_object(
                    url=url,
                    source_type='BlogPost',
                    source_id=post.id,
                    priority=0.7,
                    changefreq='weekly'
                )
                count += 1
        except Exception as e:
            logger.warning(f"Error adding blog posts to sitemap: {e}")
        return count

    @staticmethod
    def _add_content_pages_to_sitemap() -> int:
        """Add all published CMS pages to sitemap."""
        count = 0
        try:
            from api.cms.models import ContentPage
            pages = ContentPage.objects.filter(status='published', is_active=True)
            from api.cms.models_new.seo import Sitemap
            for page in pages:
                url = f"{SEOService._get_base_url()}{page.get_absolute_url()}"
                Sitemap.upsert_for_object(
                    url=url,
                    source_type='ContentPage',
                    source_id=page.id,
                    priority=0.8,
                    changefreq='weekly'
                )
                count += 1
        except Exception as e:
            logger.warning(f"Error adding content pages to sitemap: {e}")
        return count

    @staticmethod
    def _get_base_url() -> str:
        from django.conf import settings
        return getattr(settings, 'SITE_BASE_URL', '').rstrip('/')

    @staticmethod
    def get_sitemap_xml() -> str:
        """Get sitemap XML content (cached)."""
        from api.cms.models_new.seo import Sitemap
        xml = cache.get('sitemap_xml')
        if xml is None:
            xml = Sitemap.generate_xml()
            cache.set('sitemap_xml', xml, 3600)
        return xml

    @staticmethod
    def add_url_to_sitemap(url: str, changefreq: str = 'weekly', priority: float = 0.5) -> Any:
        """Manually add a URL to the sitemap."""
        from api.cms.models_new.seo import Sitemap
        try:
            obj, _ = Sitemap.objects.update_or_create(
                url=url,
                defaults={
                    'changefreq': changefreq,
                    'priority': priority,
                    'last_modified': timezone.now(),
                    'is_active': True,
                }
            )
            cache.delete('sitemap_xml')
            return obj
        except Exception as e:
            logger.error(f"Error adding URL to sitemap: {e}", exc_info=True)
            return None

    @staticmethod
    def remove_url_from_sitemap(url: str) -> bool:
        """Remove a URL from the sitemap."""
        from api.cms.models_new.seo import Sitemap
        try:
            Sitemap.objects.filter(url=url).update(is_active=False)
            cache.delete('sitemap_xml')
            return True
        except Exception as e:
            logger.error(f"Error removing URL from sitemap: {e}", exc_info=True)
            return False

    # ────────────────────────────────────────────────────
    # ROBOTS.TXT
    # ────────────────────────────────────────────────────

    @staticmethod
    def get_robots_txt() -> str:
        """Get robots.txt content."""
        from api.cms.models_new.seo import RobotsConfig
        config = RobotsConfig.get_active()
        if config:
            return config.generate_robots_txt()
        return "User-agent: *\nAllow: /"

    @staticmethod
    def update_robots_config(data: Dict[str, Any]) -> bool:
        """Update the active robots config."""
        from api.cms.models_new.seo import RobotsConfig
        try:
            config = RobotsConfig.get_active()
            if not config:
                config = RobotsConfig.objects.create(**data)
            else:
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
                config.save()
            return True
        except Exception as e:
            logger.error(f"Error updating robots config: {e}", exc_info=True)
            return False

    # ────────────────────────────────────────────────────
    # SEO CONFIG
    # ────────────────────────────────────────────────────

    @staticmethod
    def get_seo_config() -> Optional[Any]:
        """Get active SEO config."""
        from api.cms.models_new.seo import SEOConfig
        return SEOConfig.get_active()

    @staticmethod
    def update_seo_config(data: Dict[str, Any]) -> bool:
        """Update SEO config."""
        from api.cms.models_new.seo import SEOConfig
        try:
            config = SEOConfig.get_active()
            if not config:
                config = SEOConfig.objects.create(**data)
            else:
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
                config.save()
            return True
        except Exception as e:
            logger.error(f"Error updating SEO config: {e}", exc_info=True)
            return False

    # ────────────────────────────────────────────────────
    # SEO AUDIT
    # ────────────────────────────────────────────────────

    @staticmethod
    def audit_blog_seo() -> List[Dict[str, Any]]:
        """Audit SEO health of blog posts."""
        from api.cms.models_new.blog import BlogPost, BlogSEO
        issues = []
        try:
            posts = BlogPost.objects.filter(status='published', is_active=True).select_related('seo')
            for post in posts:
                post_issues = []
                # Check if SEO exists
                try:
                    seo = post.seo
                except Exception:
                    seo = None

                if not seo:
                    post_issues.append({'type': 'missing_seo', 'severity': 'high', 'message': 'No SEO metadata'})
                else:
                    if not seo.meta_title:
                        post_issues.append({'type': 'missing_meta_title', 'severity': 'high', 'message': 'No meta title'})
                    elif len(seo.meta_title) > 60:
                        post_issues.append({'type': 'long_meta_title', 'severity': 'medium', 'message': f'Meta title too long ({len(seo.meta_title)} chars)'})
                    if not seo.meta_description:
                        post_issues.append({'type': 'missing_meta_description', 'severity': 'medium', 'message': 'No meta description'})
                    elif len(seo.meta_description) > 160:
                        post_issues.append({'type': 'long_meta_description', 'severity': 'low', 'message': f'Meta description too long ({len(seo.meta_description)} chars)'})

                if not post.excerpt:
                    post_issues.append({'type': 'missing_excerpt', 'severity': 'medium', 'message': 'No excerpt'})
                if not post.featured_image:
                    post_issues.append({'type': 'missing_featured_image', 'severity': 'medium', 'message': 'No featured image'})

                if post_issues:
                    issues.append({
                        'post_id': post.id,
                        'post_title': post.title,
                        'post_slug': post.slug,
                        'issues': post_issues,
                        'issue_count': len(post_issues),
                    })
        except Exception as e:
            logger.error(f"Error auditing blog SEO: {e}", exc_info=True)
        return issues

    @staticmethod
    def get_seo_statistics() -> Dict[str, Any]:
        """Get overall SEO statistics."""
        from api.cms.models_new.seo import Sitemap, Redirect301
        from api.cms.models_new.blog import BlogPost, BlogSEO
        try:
            total_sitemap = Sitemap.objects.filter(is_active=True).count()
            total_redirects = Redirect301.objects.filter(is_active=True).count()
            total_posts = BlogPost.objects.filter(status='published', is_active=True).count()
            posts_with_seo = BlogSEO.objects.count()
            return {
                'sitemap_entries': total_sitemap,
                'active_redirects': total_redirects,
                'published_posts': total_posts,
                'posts_with_seo': posts_with_seo,
                'seo_coverage_pct': round((posts_with_seo / total_posts * 100) if total_posts else 0, 1),
            }
        except Exception as e:
            logger.error(f"Error getting SEO statistics: {e}", exc_info=True)
            return {}
