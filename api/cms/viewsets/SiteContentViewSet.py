from typing import Dict, List, Any, Optional, Tuple, Union
from api.cms.permissions import IsOwnerOrAdmin, IsCMSAdmin
# api/cms/viewsets/SiteContentViewSet.py
"""
SiteContentViewSet: Global site settings, announcements, and site content management.
Covers SiteSettings, SiteAnalytics, and content configuration for earning/CPAlead sites.
"""
import logging
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class SiteContentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for site-wide content settings and configuration.

    Endpoints:
        GET    /api/cms/site-content/                    - List settings (admin)
        POST   /api/cms/site-content/                    - Create setting (admin)
        GET    /api/cms/site-content/{id}/               - Get setting (admin)
        PUT    /api/cms/site-content/{id}/               - Update setting (admin)
        DELETE /api/cms/site-content/{id}/               - Delete setting (admin)
        GET    /api/cms/site-content/public/             - Public settings (public)
        GET    /api/cms/site-content/by_category/        - Settings by category
        GET    /api/cms/site-content/app_config/         - Full app config (public)
        POST   /api/cms/site-content/bulk_update/        - Bulk update settings (admin)
        GET    /api/cms/site-content/earning_config/     - Earning/CPAlead config (auth)
        GET    /api/cms/site-content/feature_flags/      - Feature flags (auth)
        POST   /api/cms/site-content/{id}/toggle/        - Toggle boolean setting (admin)
    """
    authentication_classes = [JWTAuthentication]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['key', 'description', 'category']
    ordering_fields = ['category', 'key', 'created_at']
    ordering = ['category', 'key']

    def get_permissions(self):
        if self.action in ('public', 'app_config', 'feature_flags'):
            return [AllowAny()]
        if self.action in ('earning_config', 'by_category'):
            return [IsAuthenticated()]
        return [IsAdminUser()]

    def get_queryset(self):
        from api.cms.models import SiteSettings
        qs = SiteSettings.objects.all()
        user = self.request.user
        if not (user and user.is_authenticated and user.is_staff):
            qs = qs.filter(is_public=True)
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        return qs

    def get_serializer_class(self):
        from api.cms.serializers import SiteSettingsSerializer
        return SiteSettingsSerializer

    # ── Public Config Endpoints ───────────────────────────────────

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def public(self, request):
        """Get all public site settings."""
        from api.cms.models import SiteSettings
        from api.cms.serializers import SiteSettingsSerializer
        cache_key = 'site_settings_public'
        cached = cache.get(cache_key)
        if cached is None:
            settings_qs = SiteSettings.objects.filter(is_public=True)
            cached = {s.key: s.get_value() for s in settings_qs}
            cache.set(cache_key, cached, 3600)
        return Response(cached)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def app_config(self, request):
        """
        Get full app configuration for frontend.
        Used by earning site to configure UI, features, rewards.
        """
        from api.cms.models import SiteSettings
        cache_key = 'site_app_config'
        cached = cache.get(cache_key)
        if cached is None:
            try:
                # Build app config from public settings
                settings_dict = {
                    s.key: s.get_value()
                    for s in SiteSettings.objects.filter(is_public=True)
                }

                # SEO config
                seo_config = {}
                try:
                    from api.cms.services_new.SEOService import SEOService
                    seo = SEOService.get_seo_config()
                    if seo:
                        seo_config = {
                            'site_name': seo.site_name,
                            'default_title': seo.default_title,
                            'google_analytics_id': seo.google_analytics_id,
                            'google_tag_manager_id': seo.google_tag_manager_id,
                            'facebook_app_id': seo.facebook_app_id,
                        }
                except Exception:
                    pass

                cached = {
                    'settings': settings_dict,
                    'seo': seo_config,
                    'generated_at': timezone.now().isoformat(),
                }
            except Exception as e:
                logger.error(f"Error building app config: {e}")
                cached = {}
            cache.set(cache_key, cached, 1800)
        return Response(cached)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def earning_config(self, request):
        """
        Get earning/CPAlead-specific configuration.
        Returns reward rates, limits, CPAlead network config.
        """
        from api.cms.models import SiteSettings
        earning_keys = [
            'min_withdrawal', 'max_withdrawal', 'daily_earning_limit',
            'referral_bonus_rate', 'banner_click_reward', 'banner_view_reward',
            'content_read_reward', 'task_completion_bonus',
            'cpalead_api_key', 'cpalead_pub_id', 'cpalead_campaign_id',
            'reward_currency', 'withdrawal_methods', 'kyc_required',
            'min_balance_withdraw', 'earning_freeze_days',
        ]
        result = {}
        for key in earning_keys:
            try:
                setting = SiteSettings.objects.get(key=key, is_public=True)
                # Don't expose API keys to non-staff
                if 'api_key' in key and not request.user.is_staff:
                    continue
                result[key] = setting.get_value()
            except SiteSettings.DoesNotExist:
                pass
        return Response(result)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def feature_flags(self, request):
        """Get feature flags for UI feature toggling."""
        from api.cms.models import SiteSettings
        cache_key = 'feature_flags'
        cached = cache.get(cache_key)
        if cached is None:
            flags_qs = SiteSettings.objects.filter(
                category='feature_flag', is_public=True
            )
            cached = {s.key: s.get_value() for s in flags_qs}
            cache.set(cache_key, cached, 1800)
        return Response(cached)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def by_category(self, request):
        """Get settings grouped by category."""
        from api.cms.models import SiteSettings
        from api.cms.serializers import SiteSettingsSerializer
        qs = SiteSettings.objects.filter(is_public=True).order_by('category', 'key')
        grouped = {}
        for s in qs:
            cat = s.category or 'general'
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append({'key': s.key, 'value': s.get_value(), 'description': s.description})
        return Response(grouped)

    # ── Admin Management ──────────────────────────────────────────

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def bulk_update(self, request):
        """
        Bulk update multiple site settings.
        body: [{key, value, data_type?, category?}]
        """
        from api.cms.models import SiteSettings
        updates = request.data.get('settings', [])
        if not updates:
            return Response({'error': 'No settings provided'}, status=status.HTTP_400_BAD_REQUEST)
        updated = 0
        errors = []
        for item in updates:
            key = item.get('key')
            value = item.get('value')
            if not key:
                errors.append({'item': item, 'error': 'key required'})
                continue
            try:
                SiteSettings.set_setting(
                    key=key,
                    value=value,
                    data_type=item.get('data_type', 'string'),
                    category=item.get('category', 'general')
                )
                updated += 1
            except Exception as e:
                errors.append({'key': key, 'error': str(e)})

        # Invalidate relevant caches
        cache.delete('site_settings_public')
        cache.delete('site_app_config')
        cache.delete('feature_flags')

        return Response({'updated': updated, 'errors': errors})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def toggle(self, request, pk=None):
        """Toggle a boolean site setting."""
        from api.cms.models import SiteSettings
        setting = self.get_object()
        if setting.data_type != 'boolean':
            return Response({'error': 'Only boolean settings can be toggled'}, status=status.HTTP_400_BAD_REQUEST)
        current = setting.get_value()
        setting.value = not current
        setting.save(update_fields=['value'])
        cache.delete('site_settings_public')
        cache.delete('site_app_config')
        cache.delete('feature_flags')
        return Response({'key': setting.key, 'value': setting.get_value()})

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def invalidate_cache(self, request):
        """Invalidate all site content caches."""
        cache.delete('site_settings_public')
        cache.delete('site_app_config')
        cache.delete('feature_flags')
        cache.delete_many([f'site_setting_{k}' for k in range(100)])
        return Response({'invalidated': True})


class SiteAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for site analytics data — read-only.
    Covers: daily stats, earning metrics, content engagement.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date', 'page_views', 'total_earnings']
    ordering = ['-date']

    def get_queryset(self):
        from api.cms.models import SiteAnalytics
        qs = SiteAnalytics.objects.all()
        start = self.request.query_params.get('start_date')
        end = self.request.query_params.get('end_date')
        from django.utils.dateparse import parse_date
        if start:
            qs = qs.filter(date__gte=parse_date(start))
        if end:
            qs = qs.filter(date__lte=parse_date(end))
        return qs

    def get_serializer_class(self):
        from api.cms.serializers import SiteAnalyticsSerializer
        return SiteAnalyticsSerializer

    @action(detail=False, methods=['get'])
    def today(self, request):
        """Get today's analytics."""
        from api.cms.models import SiteAnalytics
        from api.cms.serializers import SiteAnalyticsSerializer
        today_stats = SiteAnalytics.get_daily_stats()
        return Response(SiteAnalyticsSerializer(today_stats).data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get analytics summary for a date range."""
        from api.cms.models import SiteAnalytics
        from django.utils.dateparse import parse_date
        start_str = request.query_params.get('start_date')
        end_str = request.query_params.get('end_date')
        if not start_str or not end_str:
            # Default: last 30 days
            end_date = timezone.now().date()
            start_date = end_date - timezone.timedelta(days=30)
        else:
            start_date = parse_date(start_str)
            end_date = parse_date(end_str)
        stats = SiteAnalytics.get_date_range_stats(start_date, end_date)
        return Response({
            'start_date': start_date,
            'end_date': end_date,
            'stats': stats
        })

    @action(detail=False, methods=['get'])
    def earning_summary(self, request):
        """
        Get earning-specific analytics for CPAlead site.
        Returns daily earnings, withdrawals, offer/task completions.
        """
        from api.cms.models import SiteAnalytics
        from django.db.models import Sum, Avg
        days = int(request.query_params.get('days', 30))
        cutoff = timezone.now().date() - timezone.timedelta(days=days)
        agg = SiteAnalytics.objects.filter(date__gte=cutoff).aggregate(
            total_earnings=Sum('total_earnings'),
            total_withdrawals=Sum('total_withdrawals'),
            total_offer_completions=Sum('offer_completions'),
            total_task_completions=Sum('task_completions'),
            total_banner_impressions=Sum('banner_impressions'),
            total_banner_clicks=Sum('banner_clicks'),
            total_banner_conversions=Sum('banner_conversions'),
        )
        return Response({
            'period_days': days,
            'start_date': cutoff,
            'end_date': timezone.now().date(),
            **{k: float(v or 0) if v is not None else 0 for k, v in agg.items()}
        })

    @action(detail=False, methods=['get'])
    def cms_analytics(self, request):
        """Get CMS-specific analytics dashboard."""
        from api.cms.services_new.CMSAnalyticsService import CMSAnalyticsService
        days = int(request.query_params.get('days', 30))
        return Response(CMSAnalyticsService.get_dashboard_summary(days=days))
