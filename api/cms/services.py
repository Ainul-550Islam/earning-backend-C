# api/cms/services.py
"""
CMSService: Expanded with full business logic for CMS operations.
Covers: content, notices, banners, FAQs, analytics, cache, search.
"""
import logging
from typing import Optional, Dict, Any, List
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Q, F, Count, Sum

logger = logging.getLogger(__name__)


class CMSService:
    """
    Central CMS service — aggregates all CMS operations.
    Delegates to specialised services for complex logic.
    """

    # ── Survey Management Services ─────────────────────────────────────

    @staticmethod
    def get_available_surveys(user, limit=20):
        """Get surveys available for a specific user."""
        try:
            from .services_new.ProfileSurveyService import ProfileSurveyManager
            manager = ProfileSurveyManager()
            return manager.get_available_surveys(user)[:limit]
        except Exception as e:
            logger.error(f"Error getting available surveys: {e}")
            return []

    @staticmethod
    def get_survey_recommendations(user, limit=10):
        """Get personalized survey recommendations for user."""
        try:
            from .services_new.ProfileSurveyService import ProfileSurveyManager
            manager = ProfileSurveyManager()
            return manager.get_survey_recommendations(user)[:limit]
        except Exception as e:
            logger.error(f"Error getting survey recommendations: {e}")
            return []

    @staticmethod
    def start_survey(user, survey_uuid):
        """Start a survey for a user."""
        try:
            from .services_new.ProfileSurveyService import ProfileSurveyManager
            manager = ProfileSurveyManager()
            return manager.start_survey(user, survey_uuid)
        except Exception as e:
            logger.error(f"Error starting survey: {e}")
            return None

    @staticmethod
    def submit_survey(user, survey_uuid, responses):
        """Submit survey responses."""
        try:
            from .services_new.ProfileSurveyService import ProfileSurveyManager
            manager = ProfileSurveyManager()
            return manager.submit_survey(user, survey_uuid, responses)
        except Exception as e:
            logger.error(f"Error submitting survey: {e}")
            return None

    @staticmethod
    def get_survey_analytics(survey_uuid=None, days=30):
        """Get survey analytics data."""
        try:
            from .services_new.SurveyAnalyticsService import SurveyAnalyticsService
            service = SurveyAnalyticsService()
            return service.get_survey_analytics(survey_uuid=survey_uuid, days=days)
        except Exception as e:
            logger.error(f"Error getting survey analytics: {e}")
            return {}

    # ── User Profile & Segmentation Services ─────────────────────────────

    @staticmethod
    def get_user_profile(user):
        """Get or create user profile."""
        try:
            from .services_new.UserProfileService import UserProfileService
            service = UserProfileService()
            return service.get_or_create_profile(user)
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return None

    @staticmethod
    def update_user_profile(user, profile_data):
        """Update user profile."""
        try:
            from .services_new.UserProfileService import UserProfileService
            service = UserProfileService()
            return service.update_profile(user, profile_data)
        except Exception as e:
            logger.error(f"Error updating user profile: {e}")
            return None

    @staticmethod
    def get_user_segments(user=None, is_active=True):
        """Get user segments."""
        try:
            from .services_new.UserSegmentService import UserSegmentService
            service = UserSegmentService()
            return service.get_segments(user=user, is_active=is_active)
        except Exception as e:
            logger.error(f"Error getting user segments: {e}")
            return []

    @staticmethod
    def create_user_segment(creator, segment_data):
        """Create a new user segment."""
        try:
            from .services_new.UserSegmentService import UserSegmentService
            service = UserSegmentService()
            return service.create_segment(creator, segment_data)
        except Exception as e:
            logger.error(f"Error creating user segment: {e}")
            return None

    # ── Reward Management Services ─────────────────────────────────────

    @staticmethod
    def calculate_survey_reward(user, survey_uuid, quality_score=1.0):
        """Calculate reward for survey completion."""
        try:
            from .services_new.SurveyRewardService import SurveyRewardService
            service = SurveyRewardService()
            return service.calculate_reward(user, survey_uuid, quality_score)
        except Exception as e:
            logger.error(f"Error calculating survey reward: {e}")
            return None

    @staticmethod
    def process_reward_transaction(user, amount, transaction_type, description):
        """Process a reward transaction."""
        try:
            from .services_new.SurveyRewardService import SurveyRewardService
            service = SurveyRewardService()
            return service.create_transaction(user, amount, transaction_type, description)
        except Exception as e:
            logger.error(f"Error processing reward transaction: {e}")
            return None

    @staticmethod
    def get_user_reward_summary(user, days=30):
        """Get user's reward summary."""
        try:
            from .services_new.SurveyRewardService import SurveyRewardService
            service = SurveyRewardService()
            return service.get_user_reward_summary(user.id, days)
        except Exception as e:
            logger.error(f"Error getting reward summary: {e}")
            return {}

    @staticmethod
    def get_reward_pool_status():
        """Get status of all reward pools."""
        try:
            from .services_new.SurveyRewardService import SurveyRewardService
            service = SurveyRewardService()
            return service.get_pool_status()
        except Exception as e:
            logger.error(f"Error getting reward pool status: {e}")
            return []

    # ── Task Management Services ─────────────────────────────────────

    @staticmethod
    def get_ready_tasks():
        """Get tasks ready to run."""
        try:
            from .services_new.TaskManagementService import TaskManagementService
            service = TaskManagementService()
            return service.get_ready_tasks()
        except Exception as e:
            logger.error(f"Error getting ready tasks: {e}")
            return []

    @staticmethod
    def execute_task(task_uuid):
        """Execute a specific task."""
        try:
            from .services_new.TaskManagementService import TaskManagementService
            service = TaskManagementService()
            return service.execute_task(task_uuid)
        except Exception as e:
            logger.error(f"Error executing task: {e}")
            return None

    @staticmethod
    def get_task_statistics():
        """Get task execution statistics."""
        try:
            from .services_new.TaskManagementService import TaskManagementService
            service = TaskManagementService()
            return service.get_task_statistics()
        except Exception as e:
            logger.error(f"Error getting task statistics: {e}")
            return {}

    @staticmethod
    def schedule_task(creator, task_data):
        """Schedule a new task."""
        try:
            from .services_new.TaskManagementService import TaskManagementService
            service = TaskManagementService()
            return service.schedule_task(creator, task_data)
        except Exception as e:
            logger.error(f"Error scheduling task: {e}")
            return None

    # ── Notification Services ───────────────────────────────────────

    @staticmethod
    def send_notification(user, notification_data):
        """Send notification to user."""
        try:
            from .services_new.NotificationService import NotificationService
            service = NotificationService()
            return service.send_notification(user, notification_data)
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return None

    @staticmethod
    def send_bulk_notifications(users, notification_data):
        """Send notification to multiple users."""
        try:
            from .services_new.NotificationService import NotificationService
            service = NotificationService()
            return service.send_bulk_notifications(users, notification_data)
        except Exception as e:
            logger.error(f"Error sending bulk notifications: {e}")
            return None

    # ── Analytics & Reporting Services ─────────────────────────────────

    @staticmethod
    def get_dashboard_analytics(days=30):
        """Get comprehensive dashboard analytics."""
        try:
            analytics = {}
            
            # Survey analytics
            survey_analytics = CMSService.get_survey_analytics(days=days)
            analytics['surveys'] = survey_analytics
            
            # Task analytics
            task_analytics = CMSService.get_task_statistics()
            analytics['tasks'] = task_analytics
            
            # Reward analytics
            reward_analytics = CMSService.get_reward_pool_status()
            analytics['rewards'] = reward_analytics
            
            return analytics
        except Exception as e:
            logger.error(f"Error getting dashboard analytics: {e}")
            return {}

    @staticmethod
    def generate_report(report_type, filters=None, format='csv'):
        """Generate various types of reports."""
        try:
            if report_type == 'survey_completion':
                return CMSService._generate_survey_report(filters, format)
            elif report_type == 'reward_transactions':
                return CMSService._generate_reward_report(filters, format)
            elif report_type == 'task_execution':
                return CMSService._generate_task_report(filters, format)
            else:
                return None
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return None

    @staticmethod
    def _generate_survey_report(filters, format):
        """Generate survey completion report."""
        try:
            from .models_new.profile_surveys import SurveyCompletion
            queryset = SurveyCompletion.objects.all()
            
            if filters:
                if filters.get('date_from'):
                    queryset = queryset.filter(started_at__date__gte=filters['date_from'])
                if filters.get('date_to'):
                    queryset = queryset.filter(started_at__date__lte=filters['date_to'])
                if filters.get('status'):
                    queryset = queryset.filter(status=filters['status'])
            
            data = list(queryset.values(
                'user__username', 'survey__title', 'status',
                'quality_score', 'total_reward_earned', 'started_at', 'completed_at'
            ))
            
            return {'data': data, 'format': format}
        except Exception as e:
            logger.error(f"Error generating survey report: {e}")
            return None

    @staticmethod
    def _generate_reward_report(filters, format):
        """Generate reward transaction report."""
        try:
            from .models_new.survey_rewards import RewardTransaction
            queryset = RewardTransaction.objects.all()
            
            if filters:
                if filters.get('date_from'):
                    queryset = queryset.filter(created_at__date__gte=filters['date_from'])
                if filters.get('date_to'):
                    queryset = queryset.filter(created_at__date__lte=filters['date_to'])
                if filters.get('status'):
                    queryset = queryset.filter(status=filters['status'])
            
            data = list(queryset.values(
                'user__username', 'amount', 'transaction_type', 'status',
                'description', 'created_at'
            ))
            
            return {'data': data, 'format': format}
        except Exception as e:
            logger.error(f"Error generating reward report: {e}")
            return None

    @staticmethod
    def _generate_task_report(filters, format):
        """Generate task execution report."""
        try:
            from .models_new.task_management import TaskExecution
            queryset = TaskExecution.objects.all()
            
            if filters:
                if filters.get('date_from'):
                    queryset = queryset.filter(started_at__date__gte=filters['date_from'])
                if filters.get('date_to'):
                    queryset = queryset.filter(started_at__date__lte=filters['date_to'])
                if filters.get('status'):
                    queryset = queryset.filter(status=filters['status'])
            
            data = list(queryset.values(
                'schedule__task_name', 'status', 'worker_id',
                'runtime_seconds', 'started_at', 'completed_at', 'error_message'
            ))
            
            return {'data': data, 'format': format}
        except Exception as e:
            logger.error(f"Error generating task report: {e}")
            return None
    """
    Central CMS service — aggregates all CMS operations.
    Delegates to specialised services for complex logic.
    """

    # ── Notices / Announcements ───────────────────────────────────

    @staticmethod
    def get_active_notices(limit: int = 10) -> list:
        """Return active announcement/notice pages."""
        try:
            from .models import ContentPage
            return list(
                ContentPage.objects.filter(
                    status='published', is_active=True,
                    page_type='announcement',
                    published_date__lte=timezone.now()
                ).order_by('-is_pinned', '-published_date')[:limit]
            )
        except Exception as e:
            logger.error(f"Error getting active notices: {e}")
            return []

    @staticmethod
    def get_active_banners(position: str = None, device: str = 'all', limit: int = 10, user=None) -> list:
        """Get active banners for display position."""
        try:
            from .services.BannerService import BannerService
            return BannerService.get_active_banners(user=user, device=device, position=position, limit=limit)
        except Exception as e:
            logger.error(f"Error getting active banners: {e}")
            return []

    @staticmethod
    def get_featured_content(limit: int = 10, language: str = 'en', page_type: str = None) -> list:
        """Get featured published content."""
        try:
            from .models import ContentPage
            q = Q(is_featured=True, status='published', is_active=True,
                  published_date__lte=timezone.now(), language=language)
            if page_type:
                q &= Q(page_type=page_type)
            cache_key = f'cms_featured_{language}_{page_type}_{limit}'
            result = cache.get(cache_key)
            if result is None:
                result = list(
                    ContentPage.objects.filter(q)
                    .select_related('category', 'author')
                    .order_by('-published_date')[:limit]
                )
                cache.set(cache_key, result, 1800)
            return result
        except Exception as e:
            logger.error(f"Error getting featured content: {e}")
            return []

    @staticmethod
    def get_popular_content(days: int = 30, limit: int = 10) -> list:
        """Get popular content by view count."""
        try:
            from .models import ContentPage
            from datetime import timedelta
            cutoff = timezone.now() - timedelta(days=days)
            return list(
                ContentPage.objects.filter(
                    status='published', is_active=True,
                    published_date__gte=cutoff
                ).order_by('-view_count')
                .select_related('category')[:limit]
            )
        except Exception as e:
            logger.error(f"Error getting popular content: {e}")
            return []

    # ── FAQs ──────────────────────────────────────────────────────

    @staticmethod
    def get_faqs(category_slug: str = None, limit: int = 20) -> list:
        """Get active FAQs optionally filtered by category."""
        try:
            from .models import FAQ
            q = Q(is_active=True)
            if category_slug:
                q &= Q(category__slug=category_slug)
            return list(
                FAQ.objects.filter(q)
                .select_related('category')
                .order_by('-priority', '-is_featured')[:limit]
            )
        except Exception as e:
            logger.error(f"Error getting FAQs: {e}")
            return []

    @staticmethod
    def get_faq_categories() -> list:
        """Get all active FAQ categories."""
        try:
            from .models import FAQCategory
            cache_key = 'cms_faq_categories'
            result = cache.get(cache_key)
            if result is None:
                result = list(FAQCategory.objects.filter(is_active=True).order_by('order'))
                cache.set(cache_key, result, 3600)
            return result
        except Exception as e:
            logger.error(f"Error getting FAQ categories: {e}")
            return []

    # ── Site Settings ─────────────────────────────────────────────

    @staticmethod
    def get_setting(key: str, default=None):
        """Get a public site setting by key."""
        try:
            from .models import SiteSettings
            return SiteSettings.get_setting(key, default=default)
        except Exception:
            return default

    @staticmethod
    def set_setting(key: str, value: Any, data_type: str = 'string', category: str = 'general'):
        """Set a site setting."""
        try:
            from .models import SiteSettings
            return SiteSettings.set_setting(key, value, data_type=data_type, category=category)
        except Exception as e:
            logger.error(f"Error setting {key}: {e}")
            return None

    @staticmethod
    def get_public_settings() -> Dict[str, Any]:
        """Get all public settings as a dict."""
        try:
            from .models import SiteSettings
            cache_key = 'cms_public_settings'
            result = cache.get(cache_key)
            if result is None:
                result = {
                    s.key: s.get_value()
                    for s in SiteSettings.objects.filter(is_public=True)
                }
                cache.set(cache_key, result, 3600)
            return result
        except Exception as e:
            logger.error(f"Error getting public settings: {e}")
            return {}

    # ── Analytics ─────────────────────────────────────────────────

    @staticmethod
    def get_daily_analytics(date=None) -> Optional[Any]:
        """Get analytics for a specific date."""
        try:
            from .models import SiteAnalytics
            return SiteAnalytics.get_daily_stats(date=date)
        except Exception as e:
            logger.error(f"Error getting daily analytics: {e}")
            return None

    @staticmethod
    def get_analytics_range(start_date, end_date) -> Dict[str, Any]:
        """Get aggregated analytics for date range."""
        try:
            from .models import SiteAnalytics
            return SiteAnalytics.get_date_range_stats(start_date, end_date)
        except Exception as e:
            logger.error(f"Error getting analytics range: {e}")
            return {}

    @staticmethod
    def record_page_view(page, user=None, ip=None, user_agent='', referrer='') -> None:
        """Record a content page view."""
        try:
            from .models import ContentViewLog, ContentPage
            ContentViewLog.objects.create(
                content=page,
                user=user,
                ip_address=ip,
                user_agent=user_agent,
                referrer=referrer,
            )
            ContentPage.objects.filter(id=page.id).update(view_count=F('view_count') + 1)
        except Exception as e:
            logger.warning(f"Error recording page view: {e}")

    # ── Search ────────────────────────────────────────────────────

    @staticmethod
    def search(query: str, content_types: list = None, limit: int = 20, user=None) -> Dict[str, Any]:
        """Full-text search across CMS content."""
        try:
            from .services_new.ContentSearchService import ContentSearchService
            return ContentSearchService.search(
                query=query,
                content_types=content_types,
                limit=limit,
                user=user
            )
        except Exception as e:
            logger.error(f"Error in CMS search: {e}")
            return {'results': [], 'total': 0, 'query': query}

    # ── Cache Management ──────────────────────────────────────────

    @staticmethod
    def invalidate_content_cache(page=None) -> None:
        """Invalidate content-related caches."""
        try:
            from .services_new.CMSCacheService import CMSCacheService
            if page:
                CMSCacheService.invalidate_content_page(page)
            else:
                CMSCacheService.clear_all_cms_caches()
        except Exception as e:
            logger.warning(f"Cache invalidation error: {e}")

    @staticmethod
    def invalidate_settings_cache() -> None:
        """Invalidate settings caches."""
        cache.delete('cms_public_settings')
        cache.delete('cms_faq_categories')
        cache.delete('site_settings_public')
        cache.delete('site_app_config')

    # ── Content Statistics ────────────────────────────────────────

    @staticmethod
    def get_content_stats() -> Dict[str, Any]:
        """Get overall CMS content statistics."""
        try:
            from .models import ContentPage, Banner, FAQ
            cache_key = 'cms_content_stats'
            result = cache.get(cache_key)
            if result is None:
                result = {
                    'total_pages': ContentPage.objects.count(),
                    'published_pages': ContentPage.objects.filter(status='published', is_active=True).count(),
                    'draft_pages': ContentPage.objects.filter(status='draft').count(),
                    'total_views': ContentPage.objects.aggregate(t=Sum('view_count'))['t'] or 0,
                    'total_banners': Banner.objects.filter(is_active=True).count(),
                    'total_faqs': FAQ.objects.filter(is_active=True).count(),
                    'generated_at': timezone.now().isoformat(),
                }
                cache.set(cache_key, result, 300)
            return result
        except Exception as e:
            logger.error(f"Error getting content stats: {e}")
            return {}

    # ── Blog ──────────────────────────────────────────────────────

    @staticmethod
    def get_latest_blog_posts(limit: int = 10, language: str = 'en') -> list:
        """Get latest published blog posts."""
        try:
            from .services_new.BlogService import BlogService
            posts, _ = BlogService.get_published_posts(language=language, limit=limit)
            return posts
        except Exception as e:
            logger.error(f"Error getting latest blog posts: {e}")
            return []

    @staticmethod
    def get_featured_blog_posts(limit: int = 6, language: str = 'en') -> list:
        """Get featured blog posts."""
        try:
            from .services_new.BlogService import BlogService
            return BlogService.get_featured_posts(limit=limit, language=language)
        except Exception as e:
            logger.error(f"Error getting featured blog posts: {e}")
            return []

    # ── Menus ─────────────────────────────────────────────────────

    @staticmethod
    def get_menu_tree(location: str, user=None) -> list:
        """Get full navigation menu tree for a location."""
        try:
            from .services_new.MenuService import MenuService
            menu = MenuService.get_menu(location=location)
            if menu:
                return MenuService.build_menu_tree(menu, user=user)
            return []
        except Exception as e:
            logger.error(f"Error getting menu tree for {location}: {e}")
            return []

    # ── Popups ────────────────────────────────────────────────────

    @staticmethod
    def get_active_popups(user=None, page_url: str = '') -> list:
        """Get active popups for display."""
        try:
            from .services_new.PopupService import PopupService
            return PopupService.get_active_popups(user=user, page_url=page_url)
        except Exception as e:
            logger.error(f"Error getting active popups: {e}")
            return []

    # ── SEO ───────────────────────────────────────────────────────

    @staticmethod
    def get_seo_config() -> Optional[Any]:
        """Get active SEO configuration."""
        try:
            from .services_new.SEOService import SEOService
            return SEOService.get_seo_config()
        except Exception as e:
            logger.error(f"Error getting SEO config: {e}")
            return None

    @staticmethod
    def get_sitemap_xml() -> str:
        """Get sitemap.xml content."""
        try:
            from .services_new.SEOService import SEOService
            return SEOService.get_sitemap_xml()
        except Exception as e:
            logger.error(f"Error getting sitemap: {e}")
            return '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'

    @staticmethod
    def get_robots_txt() -> str:
        """Get robots.txt content."""
        try:
            from .services_new.SEOService import SEOService
            return SEOService.get_robots_txt()
        except Exception as e:
            logger.error(f"Error getting robots.txt: {e}")
            return "User-agent: *\nAllow: /"

    @staticmethod
    def find_redirect(from_url: str) -> Optional[Any]:
        """Find 301 redirect for a URL."""
        try:
            from .services_new.RedirectService import RedirectService
            return RedirectService.find(from_url)
        except Exception as e:
            logger.error(f"Error finding redirect: {e}")
            return None

    # ── App Home Data ─────────────────────────────────────────────

    @staticmethod
    def get_home_data(user=None, language: str = 'en') -> Dict[str, Any]:
        """
        Get all home page data in a single call.
        Used by PublicCMSViewSet home endpoint.
        CPAlead pattern: includes earning-related content.
        """
        try:
            data = {
                'settings': CMSService.get_public_settings(),
                'featured_content': [],
                'featured_posts': [],
                'active_popups': [],
                'header_menu': [],
                'footer_menu': [],
                'active_banners': [],
            }

            # Featured CMS pages
            try:
                pages = CMSService.get_featured_content(limit=6, language=language)
                data['featured_content'] = [
                    {'id': p.id, 'title': p.title, 'slug': p.slug,
                     'excerpt': p.excerpt, 'page_type': p.page_type}
                    for p in pages
                ]
            except Exception:
                pass

            # Featured blog posts
            try:
                data['featured_posts'] = [
                    {'id': p.id, 'title': p.title, 'slug': p.slug, 'excerpt': p.excerpt}
                    for p in CMSService.get_featured_blog_posts(limit=4, language=language)
                ]
            except Exception:
                pass

            # Menus
            try:
                data['header_menu'] = CMSService.get_menu_tree('header', user=user)
            except Exception:
                pass
            try:
                data['footer_menu'] = CMSService.get_menu_tree('footer', user=user)
            except Exception:
                pass

            # Active popups
            try:
                popups = CMSService.get_active_popups(user=user)
                data['active_popups'] = [
                    {'id': p.id, 'name': p.name, 'popup_type': p.popup_type,
                     'title': p.title, 'cta_url': p.cta_url}
                    for p in popups
                ]
            except Exception:
                pass

            return data
        except Exception as e:
            logger.error(f"Error getting home data: {e}")
            return {}
