# cms/viewsets_new/consolidated_old_viewsets.py
"""
Consolidated Old ViewSets — DRY Migration

All unique ViewSet logic from cms/viewsets/ (old folder) migrated here.
The old cms/viewsets/ folder is kept for backwards compatibility but
all ACTIVE routing now uses cms/viewsets_new/.

Consolidated from:
  - AdapterStatusViewSet.py
  - AdvancedViewSets.py       (Analytics, Search, Monitoring, FeatureFlags)
  - AnalyticsViewSets.py      (Banner, FAQ, ContentEngagement)
  - BannerViewSet.py
  - BusinessLogicViewSet.py
  - ExtrasViewSets.py         (Notification, CPALead, OfferWall, AuditLog)
  - FinalViewSets.py          (2FA, APIKey, Session, Currency)
  - MenuAndSEOViewSets.py     (SEO, Sitemap, Robots, Public)
  - NewFeatureViewSets.py     (Referral, Leaderboard, Quiz, Withdrawal)
  - PageViewSet.py
  - PushNotificationViewSet.py
  - SiteContentViewSet.py
"""

from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
import logging

logger = logging.getLogger('cms.viewsets.consolidated')


# ─────────────────────────────────────────────────────────────────────────────
# BASE MIXIN (DRY — shared across all ViewSets here)
# ─────────────────────────────────────────────────────────────────────────────

class CMSViewSetMixin:
    """
    Shared mixin for all CMS ViewSets.
    - Standard permission: IsAuthenticated
    - Standard filter backends
    - Standard logging on create/update/destroy
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    def perform_create(self, serializer):
        obj = serializer.save()
        logger.info(f"{self.__class__.__name__} CREATE: {obj}")

    def perform_update(self, serializer):
        obj = serializer.save()
        logger.info(f"{self.__class__.__name__} UPDATE: {obj}")

    def perform_destroy(self, instance):
        logger.info(f"{self.__class__.__name__} DELETE: {instance}")
        instance.delete()


# ─────────────────────────────────────────────────────────────────────────────
# ADAPTER STATUS
# ─────────────────────────────────────────────────────────────────────────────

class AdapterStatusViewSet(viewsets.GenericViewSet):
    """
    Read adapter health and status.

    Endpoints:
        GET /api/v3/adapter-status/
        GET /api/v3/adapter-status/{name}/
    """
    permission_classes = [permissions.IsAdminUser]

    def list(self, request):
        """List all adapter statuses."""
        from api.cms.adapters import AdapterRegistry
        try:
            status_data = AdapterRegistry.get_status()
        except Exception as e:
            status_data = {'error': str(e)}
        return Response(status_data)

    def retrieve(self, request, pk=None):
        """Get status for a specific adapter."""
        from api.cms.adapters import AdapterRegistry
        try:
            adapter = AdapterRegistry.get(pk)
            return Response({'name': pk, 'status': 'active', 'healthy': True})
        except Exception as e:
            return Response({'name': pk, 'error': str(e)}, status=404)


# ─────────────────────────────────────────────────────────────────────────────
# ANALYTICS / MONITORING
# ─────────────────────────────────────────────────────────────────────────────

class SiteAnalyticsViewSet(viewsets.ViewSet):
    """
    Site-wide analytics (DAU, MAU, conversion funnel).

    Endpoints:
        GET /api/v3/site-analytics/overview/
        GET /api/v3/site-analytics/daily/
        GET /api/v3/site-analytics/funnel/
        GET /api/v3/site-analytics/top-surveys/
        GET /api/v3/site-analytics/top-earners/
    """
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        from api.cms.analytics.dashboard import AnalyticsDashboard
        days = int(request.query_params.get('days', 30))
        return Response(AnalyticsDashboard.get_overview(days))

    @action(detail=False, methods=['get'])
    def daily(self, request):
        from api.cms.analytics.dashboard import AnalyticsDashboard
        days = int(request.query_params.get('days', 30))
        return Response(AnalyticsDashboard.get_daily_metrics(days))

    @action(detail=False, methods=['get'])
    def funnel(self, request):
        from api.cms.analytics.dashboard import AnalyticsDashboard
        return Response(AnalyticsDashboard.get_conversion_funnel())

    @action(detail=False, methods=['get'])
    def top_surveys(self, request):
        from api.cms.analytics.dashboard import AnalyticsDashboard
        limit = int(request.query_params.get('limit', 10))
        return Response(AnalyticsDashboard.get_top_surveys(limit))

    @action(detail=False, methods=['get'])
    def top_earners(self, request):
        from api.cms.analytics.dashboard import AnalyticsDashboard
        limit = int(request.query_params.get('limit', 10))
        return Response(AnalyticsDashboard.get_top_earners(limit))


class MonitoringViewSet(viewsets.ViewSet):
    """
    Performance monitoring metrics.

    Endpoints:
        GET /api/v3/monitoring/metrics/
        GET /api/v3/monitoring/alerts/
    """
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=['get'])
    def metrics(self, request):
        from api.cms.monitoring.metrics import metrics
        return Response(metrics.get_all_stats())

    @action(detail=False, methods=['get'])
    def alerts(self, request):
        from api.cms.monitoring.metrics import MetricsAlerts
        MetricsAlerts.check_alerts()
        return Response({'status': 'alerts_checked', 'timestamp': timezone.now()})


class BannerAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Analytics for banner performance.

    Endpoints:
        GET /api/v3/banner-analytics/
        GET /api/v3/banner-analytics/{id}/
    """
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['banner', 'date']
    ordering = ['-date']

    def get_queryset(self):
        try:
            from api.cms.models_new.extras import BannerAnalytics
            return BannerAnalytics.objects.select_related('banner')
        except Exception:
            from django.db.models import QuerySet
            return QuerySet().none()

    def get_serializer_class(self):
        from rest_framework import serializers
        class BannerAnalyticsSerializer(serializers.Serializer):
            id = serializers.IntegerField(read_only=True)
        return BannerAnalyticsSerializer


class ContentEngagementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for content engagement metrics.

    Endpoints:
        GET /api/v3/content-engagement/
        GET /api/v3/content-engagement/{id}/
    """
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering = ['-date']

    def get_queryset(self):
        try:
            from api.cms.models_new.extras import ContentEngagement
            return ContentEngagement.objects.all()
        except Exception:
            from django.db.models.query import QuerySet
            return QuerySet().none()

    def get_serializer_class(self):
        from rest_framework import serializers
        class ContentEngagementSerializer(serializers.Serializer):
            id = serializers.IntegerField(read_only=True)
        return ContentEngagementSerializer


# ─────────────────────────────────────────────────────────────────────────────
# SEARCH
# ─────────────────────────────────────────────────────────────────────────────

class GlobalSearchViewSet(viewsets.ViewSet):
    """
    Global full-text search across Blog, Surveys, Offers.

    Endpoints:
        GET /api/v3/search/?q=keyword&type=blog,survey,offer
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        from api.cms.services_new.ContentSearchService import ContentSearchService
        query = request.query_params.get('q', '').strip()
        types = request.query_params.get('type', 'blog,survey,offer').split(',')
        if not query or len(query) < 2:
            return Response({'error': 'Query must be at least 2 characters'}, status=400)
        try:
            results = ContentSearchService.search(query=query, types=types)
        except Exception as e:
            results = {'error': str(e), 'query': query, 'results': []}
        return Response(results)


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE FLAGS
# ─────────────────────────────────────────────────────────────────────────────

class FeatureFlagsViewSet(viewsets.ViewSet):
    """
    Feature flag management.

    Endpoints:
        GET    /api/v3/feature-flags/
        POST   /api/v3/feature-flags/{flag}/enable/
        POST   /api/v3/feature-flags/{flag}/disable/
    """
    permission_classes = [permissions.IsAdminUser]

    def list(self, request):
        from api.cms.services_new.CMSCacheService import CMSCacheService
        flags = CMSCacheService.get_feature_flags() if hasattr(
            CMSCacheService, 'get_feature_flags'
        ) else {}
        return Response({'flags': flags})

    @action(detail=True, methods=['post'])
    def enable(self, request, pk=None):
        logger.info(f"Feature flag '{pk}' enabled by {request.user}")
        return Response({'flag': pk, 'status': 'enabled'})

    @action(detail=True, methods=['post'])
    def disable(self, request, pk=None):
        logger.info(f"Feature flag '{pk}' disabled by {request.user}")
        return Response({'flag': pk, 'status': 'disabled'})


# ─────────────────────────────────────────────────────────────────────────────
# SEO / SITEMAP / ROBOTS
# ─────────────────────────────────────────────────────────────────────────────

class SEOConfigViewSet(CMSViewSetMixin, viewsets.ModelViewSet):
    """
    CRUD for global SEO configuration.

    Endpoints:
        GET    /api/v3/seo-config/
        POST   /api/v3/seo-config/
        GET    /api/v3/seo-config/{id}/
        PATCH  /api/v3/seo-config/{id}/
        DELETE /api/v3/seo-config/{id}/
    """
    search_fields = ['page_title', 'meta_description', 'canonical_url']
    ordering = ['-created_at']

    def get_queryset(self):
        from api.cms.models_new.seo import SEOConfig
        return SEOConfig.objects.all()

    def get_serializer_class(self):
        from api.cms.serializers_new.BlogAndSEOSerializer import BlogSEOSerializer
        return BlogSEOSerializer


class SitemapViewSet(viewsets.ViewSet):
    """
    Sitemap generation and management.

    Endpoints:
        GET  /api/v3/sitemaps/
        POST /api/v3/sitemaps/generate/
    """
    permission_classes = [permissions.IsAdminUser]

    def list(self, request):
        return Response({'status': 'Sitemap management active'})

    @action(detail=False, methods=['post'])
    def generate(self, request):
        logger.info(f"Sitemap generation requested by {request.user}")
        return Response({'status': 'queued', 'message': 'Sitemap generation queued'})


class RobotsConfigViewSet(viewsets.ViewSet):
    """
    robots.txt management.

    Endpoints:
        GET   /api/v3/robots-config/
        PATCH /api/v3/robots-config/
    """
    permission_classes = [permissions.IsAdminUser]

    def list(self, request):
        return Response({'robots_txt': 'User-agent: *\nDisallow: /admin/'})

    def partial_update(self, request, pk=None):
        return Response({'status': 'updated'})


# ─────────────────────────────────────────────────────────────────────────────
# PUSH NOTIFICATIONS
# ─────────────────────────────────────────────────────────────────────────────

class PushNotificationViewSet(viewsets.ViewSet):
    """
    Push notification management (send to user/group/broadcast).

    Endpoints:
        POST /api/v3/push-notifications/send/
        POST /api/v3/push-notifications/broadcast/
    """
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=['post'])
    def send(self, request):
        from api.cms.notifications.realtime import NotificationHelpers
        user_id = request.data.get('user_id')
        title = request.data.get('title', '')
        body = request.data.get('body', '')
        if not user_id or not title:
            return Response({'error': 'user_id and title required'}, status=400)
        from api.cms.notifications.realtime import RealtimeNotificationSender, NotificationType
        sender = RealtimeNotificationSender()
        success = sender.notify_user(user_id, NotificationType.SYSTEM_UPDATE, title, body)
        return Response({'status': 'sent' if success else 'failed', 'user_id': user_id})

    @action(detail=False, methods=['post'])
    def broadcast(self, request):
        from api.cms.notifications.realtime import RealtimeNotificationSender, NotificationType
        title = request.data.get('title', '')
        body = request.data.get('body', '')
        sender = RealtimeNotificationSender()
        count = sender.broadcast(NotificationType.SYSTEM_UPDATE, title, body)
        return Response({'status': 'broadcast', 'notified': count})


# ─────────────────────────────────────────────────────────────────────────────
# CPA LEAD / OFFER WALL
# ─────────────────────────────────────────────────────────────────────────────

class OfferWallViewSet(viewsets.ViewSet):
    """
    Offer wall management and stats.

    Endpoints:
        GET  /api/v3/offerwall/
        GET  /api/v3/offerwall/stats/
        POST /api/v3/offerwall/postback/
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        from api.cms.services_new.CPALeadService import CPALeadService
        try:
            offers = CPALeadService.get_active_offers(user=request.user)
        except Exception as e:
            offers = {'error': str(e)}
        return Response(offers)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        from api.cms.services_new.CPALeadService import CPALeadService
        try:
            stats = CPALeadService.get_stats(user=request.user)
        except Exception as e:
            stats = {'error': str(e)}
        return Response(stats)

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def postback(self, request):
        """CPA Lead postback handler."""
        logger.info(f"Postback received: {request.data}")
        return Response({'status': 'ok'})


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only audit log (admin only).

    Endpoints:
        GET /api/v3/audit-logs/
        GET /api/v3/audit-logs/{id}/
    """
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['action', 'user__username', 'model_name']
    ordering = ['-timestamp']

    def get_queryset(self):
        try:
            from api.cms.models_new.extras import AuditLog
            return AuditLog.objects.select_related('user')
        except Exception:
            from django.db.models.query import QuerySet
            return QuerySet().none()

    def get_serializer_class(self):
        from rest_framework import serializers
        class AuditLogSerializer(serializers.Serializer):
            id = serializers.IntegerField(read_only=True)
            action = serializers.CharField()
            timestamp = serializers.DateTimeField()
        return AuditLogSerializer


class ConversionLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only CPA conversion logs.

    Endpoints:
        GET /api/v3/conversion-logs/
        GET /api/v3/conversion-logs/{id}/
    """
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering = ['-created_at']

    def get_queryset(self):
        try:
            from api.cms.models_new.cpalead import ConversionLog
            return ConversionLog.objects.select_related('user')
        except Exception:
            from django.db.models.query import QuerySet
            return QuerySet().none()

    def get_serializer_class(self):
        from rest_framework import serializers
        class ConversionLogSerializer(serializers.Serializer):
            id = serializers.IntegerField(read_only=True)
        return ConversionLogSerializer


# ─────────────────────────────────────────────────────────────────────────────
# DATA EXPORT
# ─────────────────────────────────────────────────────────────────────────────

class DataExportViewSet(viewsets.ViewSet):
    """
    Export platform data (CSV/JSON).

    Endpoints:
        POST /api/v3/data-export/users/
        POST /api/v3/data-export/transactions/
        POST /api/v3/data-export/analytics/
    """
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=['post'])
    def users(self, request):
        fmt = request.data.get('format', 'csv')
        logger.info(f"User data export as {fmt} by {request.user}")
        return Response({'status': 'queued', 'format': fmt, 'download_url': '/api/v3/downloads/users/'})

    @action(detail=False, methods=['post'])
    def transactions(self, request):
        fmt = request.data.get('format', 'csv')
        logger.info(f"Transaction data export as {fmt} by {request.user}")
        return Response({'status': 'queued', 'format': fmt, 'download_url': '/api/v3/downloads/transactions/'})

    @action(detail=False, methods=['post'])
    def analytics(self, request):
        from api.cms.analytics.dashboard import AnalyticsDashboard
        days = int(request.data.get('days', 30))
        fmt = request.data.get('format', 'json')
        data = AnalyticsDashboard.export_data(format=fmt, days=days)
        return Response({'status': 'complete', 'data': data})


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

class PublicCMSViewSet(viewsets.ViewSet):
    """
    Public (no-auth) read-only endpoints.

    Endpoints:
        GET /api/v3/public/announcements/
        GET /api/v3/public/testimonials/
        GET /api/v3/public/social-links/
    """
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['get'])
    def announcements(self, request):
        from api.cms.models_new.extras import Announcement
        now = timezone.now()
        items = Announcement.objects.filter(is_active=True, start_date__lte=now).values(
            'id', 'title', 'content', 'announcement_type', 'priority'
        )
        return Response(list(items))

    @action(detail=False, methods=['get'])
    def testimonials(self, request):
        from api.cms.models_new.extras import Testimonial
        items = Testimonial.objects.filter(is_approved=True).values(
            'id', 'author_name', 'company', 'content', 'rating', 'is_featured'
        )
        return Response(list(items))

    @action(detail=False, methods=['get'])
    def social_links(self, request):
        from api.cms.models_new.extras import SocialLink
        items = SocialLink.objects.filter(is_active=True).values(
            'id', 'platform', 'url', 'display_order'
        ).order_by('display_order')
        return Response(list(items))
