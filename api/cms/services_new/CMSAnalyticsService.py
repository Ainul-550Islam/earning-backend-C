# api/cms/services/CMSAnalyticsService.py
"""
CMSAnalyticsService: Page views, blog reads, popup CTR, banner analytics.
"""
import logging
from datetime import timedelta
from typing import Dict, List, Optional, Any

from django.db.models import Q, F, Sum, Count, Avg
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class CMSAnalyticsService:
    """Analytics service for all CMS content types."""

    # ────────────────────────────────────────────────────
    # PAGE ANALYTICS
    # ────────────────────────────────────────────────────

    @staticmethod
    def get_page_views(days: int = 30) -> Dict[str, Any]:
        """Get page view analytics for last N days."""
        from api.cms.models import ContentPage, ContentViewLog
        try:
            cutoff = timezone.now() - timedelta(days=days)
            views = ContentViewLog.objects.filter(created_at__gte=cutoff)
            total_views = views.count()
            unique_views = views.values('ip_address').distinct().count()
            avg_duration = views.aggregate(avg=Avg('view_duration'))['avg'] or 0
            completion_rate = views.filter(is_completed=True).count() / total_views if total_views else 0

            # Top pages
            top_pages = list(
                views.values('content__title', 'content__slug')
                .annotate(view_count=Count('id'))
                .order_by('-view_count')[:10]
            )

            # Daily breakdown
            from django.db.models.functions import TruncDate
            daily = list(
                views.annotate(date=TruncDate('created_at'))
                .values('date')
                .annotate(views=Count('id'), unique=Count('ip_address', distinct=True))
                .order_by('date')
            )

            return {
                'period_days': days,
                'total_views': total_views,
                'unique_views': unique_views,
                'avg_duration_seconds': round(avg_duration, 1),
                'completion_rate_pct': round(completion_rate * 100, 2),
                'top_pages': top_pages,
                'daily': daily,
            }
        except Exception as e:
            logger.error(f"Error getting page view analytics: {e}", exc_info=True)
            return {}

    # ────────────────────────────────────────────────────
    # BLOG ANALYTICS
    # ────────────────────────────────────────────────────

    @staticmethod
    def get_blog_reads(days: int = 30) -> Dict[str, Any]:
        """Get blog read analytics."""
        from api.cms.models_new.blog import BlogPost
        cache_key = f'blog_analytics_{days}'
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            cutoff = timezone.now() - timedelta(days=days)
            posts = BlogPost.objects.filter(
                status='published', is_active=True,
                published_at__gte=cutoff
            )
            total_posts = posts.count()
            total_reads = posts.aggregate(t=Sum('views_count'))['t'] or 0
            total_likes = posts.aggregate(t=Sum('like_count'))['t'] or 0
            total_comments = posts.aggregate(t=Sum('comment_count'))['t'] or 0
            avg_reads = total_reads / total_posts if total_posts else 0

            top_posts = list(
                posts.order_by('-views_count')
                .values('id', 'title', 'slug', 'views_count', 'like_count', 'comment_count', 'published_at')[:10]
            )

            # By category
            from api.cms.models_new.blog import BlogCategory
            by_category = list(
                BlogPost.objects.filter(status='published', is_active=True)
                .values('category__name', 'category__slug')
                .annotate(
                    post_count=Count('id'),
                    total_views=Sum('views_count')
                )
                .order_by('-total_views')[:10]
            )

            result = {
                'period_days': days,
                'total_posts_in_period': total_posts,
                'total_reads': total_reads,
                'total_likes': total_likes,
                'total_comments': total_comments,
                'avg_reads_per_post': round(avg_reads, 1),
                'top_posts': top_posts,
                'by_category': by_category,
                'generated_at': timezone.now().isoformat(),
            }
            cache.set(cache_key, result, 300)
            return result
        except Exception as e:
            logger.error(f"Error getting blog read analytics: {e}", exc_info=True)
            return {}

    # ────────────────────────────────────────────────────
    # POPUP CTR
    # ────────────────────────────────────────────────────

    @staticmethod
    def get_popup_ctr(days: int = 30) -> List[Dict[str, Any]]:
        """Get popup click-through rates."""
        from api.cms.models_new.popup import Popup, PopupStat
        cache_key = f'popup_ctr_{days}'
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            from datetime import timedelta as td
            cutoff = timezone.now().date() - td(days=days)
            stats = (
                PopupStat.objects.filter(date__gte=cutoff)
                .values('popup__id', 'popup__name', 'popup__popup_type')
                .annotate(
                    total_views=Sum('views'),
                    total_clicks=Sum('clicks'),
                    total_dismissals=Sum('dismissals'),
                    total_conversions=Sum('conversions'),
                )
                .order_by('-total_views')
            )
            result = []
            for stat in stats:
                views = stat['total_views'] or 0
                clicks = stat['total_clicks'] or 0
                ctr = round((clicks / views * 100) if views else 0, 2)
                result.append({
                    'popup_id': stat['popup__id'],
                    'popup_name': stat['popup__name'],
                    'popup_type': stat['popup__popup_type'],
                    'total_views': views,
                    'total_clicks': clicks,
                    'total_dismissals': stat['total_dismissals'] or 0,
                    'total_conversions': stat['total_conversions'] or 0,
                    'ctr': ctr,
                })
            cache.set(cache_key, result, 300)
            return result
        except Exception as e:
            logger.error(f"Error getting popup CTR: {e}", exc_info=True)
            return []

    # ────────────────────────────────────────────────────
    # BANNER ANALYTICS
    # ────────────────────────────────────────────────────

    @staticmethod
    def get_banner_analytics(days: int = 30) -> Dict[str, Any]:
        """Get banner performance analytics."""
        from api.cms.models import Banner, BannerImpression, BannerClick
        cache_key = f'banner_analytics_{days}'
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            cutoff = timezone.now() - timedelta(days=days)
            impressions = BannerImpression.objects.filter(created_at__gte=cutoff).count()
            clicks = BannerClick.objects.filter(created_at__gte=cutoff).count()
            overall_ctr = round((clicks / impressions * 100) if impressions else 0, 2)

            # Top banners
            top_banners = list(
                Banner.objects.filter(is_active=True)
                .order_by('-impression_count')[:10]
                .values(
                    'id', 'name', 'banner_type', 'position',
                    'impression_count', 'click_count', 'conversion_count',
                    'click_through_rate', 'conversion_rate'
                )
            )

            # By type
            by_type = list(
                Banner.objects.values('banner_type')
                .annotate(
                    count=Count('id'),
                    total_impressions=Sum('impression_count'),
                    total_clicks=Sum('click_count'),
                )
                .order_by('-total_impressions')
            )

            result = {
                'period_days': days,
                'period_impressions': impressions,
                'period_clicks': clicks,
                'overall_ctr': overall_ctr,
                'top_banners': top_banners,
                'by_type': by_type,
                'generated_at': timezone.now().isoformat(),
            }
            cache.set(cache_key, result, 300)
            return result
        except Exception as e:
            logger.error(f"Error getting banner analytics: {e}", exc_info=True)
            return {}

    # ────────────────────────────────────────────────────
    # COMBINED DASHBOARD
    # ────────────────────────────────────────────────────

    @staticmethod
    def get_dashboard_summary(days: int = 30) -> Dict[str, Any]:
        """Get combined analytics dashboard summary."""
        cache_key = f'cms_dashboard_summary_{days}'
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            result = {
                'period_days': days,
                'page_views': CMSAnalyticsService.get_page_views(days=days),
                'blog_reads': CMSAnalyticsService.get_blog_reads(days=days),
                'popup_ctr': CMSAnalyticsService.get_popup_ctr(days=days)[:5],
                'banner': CMSAnalyticsService.get_banner_analytics(days=days),
                'generated_at': timezone.now().isoformat(),
            }
            cache.set(cache_key, result, 600)
            return result
        except Exception as e:
            logger.error(f"Error getting dashboard summary: {e}", exc_info=True)
            return {}

    # ────────────────────────────────────────────────────
    # RECORD EVENTS
    # ────────────────────────────────────────────────────

    @staticmethod
    def record_page_view(page, user=None, ip='', user_agent='', referrer='', duration=0) -> None:
        """Record a page view."""
        from api.cms.models import ContentViewLog
        try:
            ContentViewLog.objects.create(
                content=page,
                user=user,
                view_duration=duration,
                is_completed=duration >= 30,
                ip_address=ip or None,
                user_agent=user_agent,
                referrer=referrer,
            )
            from api.cms.models import ContentPage
            ContentPage.objects.filter(id=page.id).update(view_count=F('view_count') + 1)
        except Exception as e:
            logger.warning(f"Error recording page view: {e}")

    @staticmethod
    def record_blog_read(post, user=None) -> None:
        """Record a blog post read."""
        try:
            post.increment_views()
        except Exception as e:
            logger.warning(f"Error recording blog read: {e}")
