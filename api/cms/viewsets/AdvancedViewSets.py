from typing import Dict, List, Any, Optional, Tuple, Union
# api/cms/viewsets/AdvancedViewSets.py
"""
Advanced CMS ViewSets — Video, RTB, Analytics, Search, Compliance, FeatureFlags,
DataExport, Monitoring, Sanctions.

FIX (audit):
  1. AnalyticsViewSet.dashboard / revenue / users / content / offers / withdrawals
     now call CMSAnalyticsService methods first, with inline queryset as fallback.
     Previously the service existed but the viewset bypassed it entirely.
  2. WorkflowViewSet (new) wires WorkflowService.transition() so workflow
     state changes go through the service layer (validation + hooks) instead
     of raw model.save() calls.

All original viewsets are preserved exactly as-is.
"""
import logging
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication

from .cms_viewset_base import (
    CMSViewSetMixin, CMSPagePagination, CMSSmallPagination,
    CMSAnonThrottle, CMSUserThrottle, CMSWriteThrottle,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Video Content ViewSet
# ─────────────────────────────────────────────

class VideoContentViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET  /api/cms/videos/                    — List videos
    POST /api/cms/videos/create/             — Create + AI generate
    GET  /api/cms/videos/{id}/               — Get video details
    POST /api/cms/videos/{id}/publish/       — Publish video
    GET  /api/cms/videos/{id}/analytics/     — Video performance
    """
    authentication_classes = [JWTAuthentication]
    pagination_class = CMSSmallPagination

    def get_permissions(self):
        if self.action in ('list_videos', 'video_detail'):
            return [IsAuthenticated()]
        return [IsAdminUser()]

    @action(detail=False, methods=['get'])
    def list_videos(self, request):
        from api.cms.services_new.VideoContentService import VideoContentService
        platform = request.query_params.get('platform', '')
        status_filter = request.query_params.get('status', '')
        user = request.user if not request.user.is_staff else None
        data = VideoContentService.list_videos(
            user=user, platform=platform or None,
            status=status_filter or None, limit=50
        )
        return Response({'results': data, 'count': len(data)})

    @action(detail=False, methods=['post'])
    def create_video(self, request):
        from api.cms.use_cases import CreateVideoContentUseCase
        from api.cms.feature_flags import FeatureFlags, FLAG_VIDEO_CONTENT
        if not FeatureFlags.is_enabled(FLAG_VIDEO_CONTENT, request.user):
            return Response({'error': 'Video content feature is disabled'},
                            status=status.HTTP_403_FORBIDDEN)
        uc = CreateVideoContentUseCase()
        result = uc.execute(
            topic=request.data.get('topic', ''),
            platform=request.data.get('platform', 'youtube_shorts'),
            style=request.data.get('style', 'story'),
            user=request.user,
            smartlink_id=request.data.get('smartlink_id'),
        )
        if 'error' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def video_detail(self, request, pk=None):
        from api.cms.models_new.video import VideoContent
        try:
            video = VideoContent.objects.get(pk=pk, created_by=request.user)
            from api.cms.serializers import VideoContentSerializer
            return Response(VideoContentSerializer(video).data)
        except VideoContent.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        from api.cms.services_new.VideoContentService import VideoContentService
        result = VideoContentService.publish_video(
            int(pk),
            video_url=request.data.get('video_url', ''),
            thumbnail_url=request.data.get('thumbnail_url', ''),
        )
        if result['success']:
            return Response(result)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        from api.cms.services_new.VideoContentService import VideoContentService
        return Response(VideoContentService.get_analytics(int(pk)))


# ─────────────────────────────────────────────
# RTB ViewSet
# ─────────────────────────────────────────────

class RTBViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET  /api/cms/rtb/config/               — RTB config (admin)
    GET  /api/cms/rtb/stats/                — Publisher stats
    POST /api/cms/rtb/add_slot/             — Add ad slot
    GET  /api/cms/rtb/get_ad/{slot_id}/     — Get best ad for slot
    """
    authentication_classes = [JWTAuthentication]

    def get_permissions(self):
        if self.action == 'get_ad':
            return [AllowAny()]
        return [IsAdminUser()]

    @action(detail=False, methods=['get'])
    def config(self, request):
        from api.cms.services_new.RTBService import RTBService
        config = RTBService.get_config()
        if not config:
            return Response({'error': 'No RTB config found'}, status=404)
        from api.cms.serializers import RTBConfigSerializer
        return Response(RTBConfigSerializer(config).data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        from api.cms.services_new.RTBService import RTBService
        days = int(request.query_params.get('days', 30))
        return Response(RTBService.get_publisher_stats(days))

    @action(detail=False, methods=['post'])
    def add_slot(self, request):
        from api.cms.services_new.RTBService import RTBService
        result = RTBService.create_ad_slot(
            config_id=request.data.get('config_id'),
            name=request.data.get('name', ''),
            slot_type=request.data.get('slot_type', 'banner_300x250'),
            floor_price=float(request.data.get('floor_price', 0)),
            page_location=request.data.get('page_location', ''),
        )
        if result['success']:
            return Response(result, status=status.HTTP_201_CREATED)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='get_ad/(?P<slot_id>[0-9]+)',
            permission_classes=[AllowAny])
    def get_ad(self, request, slot_id=None):
        from api.cms.services_new.RTBService import RTBService
        from api.cms.helpers import get_client_ip, detect_device, get_country_from_ip
        ip = get_client_ip(request)
        ua = request.META.get('HTTP_USER_AGENT', '')
        device = detect_device(ua)
        country = get_country_from_ip(ip)
        result = RTBService.get_ad_for_slot(int(slot_id), ip, country, device)
        return Response(result)


# ─────────────────────────────────────────────
# Analytics ViewSet
# FIX: now delegates to CMSAnalyticsService for unified analytics logic
# ─────────────────────────────────────────────

class AnalyticsViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET /api/cms/analytics/dashboard/    — Full analytics dashboard
    GET /api/cms/analytics/revenue/      — Revenue breakdown
    GET /api/cms/analytics/users/        — User analytics
    GET /api/cms/analytics/content/      — Content performance
    GET /api/cms/analytics/offers/       — Offerwall analytics
    GET /api/cms/analytics/withdrawals/  — Withdrawal analytics
    GET /api/cms/analytics/metrics/      — SLA + real-time metrics
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        days = int(request.query_params.get('days', 30))
        # FIX: prefer CMSAnalyticsService; fall back to CMSAnalyticsDashboard
        try:
            from api.cms.services_new.CMSAnalyticsService import CMSAnalyticsService
            data = CMSAnalyticsService.get_full_dashboard(days=days)
            return Response(data)
        except Exception:
            pass
        from api.cms.analytics import CMSAnalyticsDashboard
        return Response(CMSAnalyticsDashboard.get_full_dashboard(days))

    @action(detail=False, methods=['get'])
    def revenue(self, request):
        days = int(request.query_params.get('days', 30))
        try:
            from api.cms.services_new.CMSAnalyticsService import CMSAnalyticsService
            data = CMSAnalyticsService.get_revenue_breakdown(days=days)
            return Response(data)
        except Exception:
            pass
        from api.cms.analytics import RevenueAnalytics
        return Response({
            'summary': RevenueAnalytics.get_summary(days),
            'daily': RevenueAnalytics.get_daily_revenue(days),
            'by_offer': RevenueAnalytics.get_by_offer_type(days),
            'hourly_pattern': RevenueAnalytics.get_hourly_pattern(7),
        })

    @action(detail=False, methods=['get'])
    def users(self, request):
        days = int(request.query_params.get('days', 30))
        try:
            from api.cms.services_new.CMSAnalyticsService import CMSAnalyticsService
            data = CMSAnalyticsService.get_user_analytics(days=days)
            return Response(data)
        except Exception:
            pass
        from api.cms.analytics import UserAnalytics
        return Response({
            'summary': UserAnalytics.get_summary(days),
            'registrations': UserAnalytics.get_registrations_over_time(days),
            'level_distribution': UserAnalytics.get_level_distribution(),
        })

    @action(detail=False, methods=['get'])
    def content(self, request):
        days = int(request.query_params.get('days', 30))
        try:
            from api.cms.services_new.CMSAnalyticsService import CMSAnalyticsService
            data = CMSAnalyticsService.get_content_analytics(days=days)
            return Response(data)
        except Exception:
            pass
        from api.cms.analytics import ContentAnalytics
        return Response({
            'blog': ContentAnalytics.get_blog_stats(days),
            'quiz': ContentAnalytics.get_quiz_stats(days),
            'smartlink': ContentAnalytics.get_smartlink_stats(days),
            'locker': ContentAnalytics.get_locker_performance(),
        })

    @action(detail=False, methods=['get'])
    def offers(self, request):
        days = int(request.query_params.get('days', 7))
        try:
            from api.cms.services_new.CMSAnalyticsService import CMSAnalyticsService
            data = CMSAnalyticsService.get_offer_analytics(days=days)
            return Response(data)
        except Exception:
            pass
        from api.cms.analytics import OfferWallAnalytics
        return Response({
            'click_stats': OfferWallAnalytics.get_click_stats(days),
            'locker_performance': OfferWallAnalytics.get_locker_performance(),
        })

    @action(detail=False, methods=['get'])
    def withdrawals(self, request):
        days = int(request.query_params.get('days', 30))
        try:
            from api.cms.services_new.CMSAnalyticsService import CMSAnalyticsService
            data = CMSAnalyticsService.get_withdrawal_analytics(days=days)
            return Response(data)
        except Exception:
            pass
        from api.cms.analytics import WithdrawalAnalytics
        return Response({
            'summary': WithdrawalAnalytics.get_summary(days),
            'by_method': WithdrawalAnalytics.get_by_method(days),
        })

    @action(detail=False, methods=['get'])
    def metrics(self, request):
        from api.cms.monitoring import CMSMetrics, SLAMonitor
        return Response({
            'metrics': CMSMetrics.get_dashboard(),
            'sla_report': SLAMonitor.get_sla_report(),
        })


# ─────────────────────────────────────────────
# Search ViewSet
# ─────────────────────────────────────────────

class SearchViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET /api/cms/search/?q=keyword           — Full-text search
    GET /api/cms/search/suggest/?q=partial   — Autocomplete suggestions
    POST /api/cms/search/reindex/            — Reindex all content (admin)
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [CMSAnonThrottle, CMSUserThrottle]

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def search(self, request):
        from api.cms.search import CMSSearchEngine
        q = request.query_params.get('q', '').strip()
        if not q:
            return Response({'error': 'q parameter required'}, status=400)
        content_types = request.query_params.getlist('type') or None
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 20)), 50)
        language = request.query_params.get('lang', '')
        results = CMSSearchEngine.search(
            query=q, content_types=content_types,
            language=language, page=page, page_size=page_size,
        )
        return Response(results)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def suggest(self, request):
        from api.cms.search import CMSSearchEngine
        q = request.query_params.get('q', '').strip()
        limit = min(int(request.query_params.get('limit', 8)), 20)
        suggestions = CMSSearchEngine.suggest(q, limit)
        return Response({'suggestions': suggestions, 'query': q})

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def reindex(self, request):
        from api.cms.search import CMSSearchEngine
        counts = CMSSearchEngine.reindex_all()
        return Response({'success': True, 'indexed': counts})


# ─────────────────────────────────────────────
# FeatureFlags ViewSet
# ─────────────────────────────────────────────

class FeatureFlagsViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET  /api/cms/features/                 — All feature flags
    POST /api/cms/features/{flag}/enable/   — Enable flag (admin)
    POST /api/cms/features/{flag}/disable/  — Disable flag (admin)
    """
    authentication_classes = [JWTAuthentication]

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def all_flags(self, request):
        from api.cms.feature_flags import FeatureFlags
        user = request.user if request.user.is_authenticated else None
        flags = FeatureFlags.get_all(user)
        return Response({'flags': flags, 'count': len(flags)})

    @action(detail=False, methods=['post'],
            url_path='(?P<flag_name>[^/.]+)/enable',
            permission_classes=[IsAdminUser])
    def enable_flag(self, request, flag_name=None):
        from api.cms.feature_flags import FeatureFlags
        success = FeatureFlags.enable(flag_name)
        return Response({'flag': flag_name, 'enabled': True, 'success': success})

    @action(detail=False, methods=['post'],
            url_path='(?P<flag_name>[^/.]+)/disable',
            permission_classes=[IsAdminUser])
    def disable_flag(self, request, flag_name=None):
        from api.cms.feature_flags import FeatureFlags
        success = FeatureFlags.disable(flag_name)
        return Response({'flag': flag_name, 'enabled': False, 'success': success})


# ─────────────────────────────────────────────
# Compliance ViewSet
# ─────────────────────────────────────────────

class ComplianceViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    POST /api/cms/compliance/gdpr/export/    — Export my data (GDPR)
    POST /api/cms/compliance/gdpr/delete/    — Delete my data (GDPR)
    GET  /api/cms/compliance/audit/          — My audit trail
    GET  /api/cms/compliance/status/         — Site compliance status (admin)
    POST /api/cms/compliance/run_retention/  — Run retention policies (admin)
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def gdpr_export(self, request):
        from api.cms.compliance import GDPRComplianceService
        data = GDPRComplianceService.export_user_data(request.user)
        return Response(data)

    @action(detail=False, methods=['post'])
    def gdpr_delete(self, request):
        from api.cms.compliance import GDPRComplianceService
        confirm = request.data.get('confirm', False)
        if not confirm:
            return Response({
                'error': 'Must confirm deletion',
                'message': 'Send {"confirm": true} to permanently delete your data.',
            }, status=status.HTTP_400_BAD_REQUEST)
        result = GDPRComplianceService.request_data_deletion(request.user)
        return Response(result)

    @action(detail=False, methods=['post'])
    def record_consent(self, request):
        from api.cms.compliance import GDPRComplianceService
        from api.cms.helpers import get_client_ip
        consent_type = request.data.get('consent_type', 'marketing')
        given = request.data.get('given', False)
        success = GDPRComplianceService.record_consent(
            request.user, consent_type, given,
            ip=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
        return Response({'success': success, 'consent_type': consent_type, 'given': given})

    @action(detail=False, methods=['get'])
    def my_audit(self, request):
        from api.cms.compliance import AuditTrailService
        days = int(request.query_params.get('days', 30))
        return Response({
            'audit_trail': AuditTrailService.get_user_audit_trail(request.user, days),
            'financial_audit': AuditTrailService.get_financial_audit(request.user, days),
        })

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def compliance_status(self, request):
        from api.cms.compliance import GDPRComplianceService
        return Response(GDPRComplianceService.check_data_retention_compliance())

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def run_retention(self, request):
        from api.cms.compliance import DataRetentionService
        dry_run = request.data.get('dry_run', True)
        result = DataRetentionService.run_all(dry_run=dry_run)
        return Response(result)


# ─────────────────────────────────────────────
# Data Export ViewSet
# ─────────────────────────────────────────────

class DataExportViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET /api/cms/export/conversions/     — CSV export (admin)
    GET /api/cms/export/withdrawals/     — CSV export (admin)
    GET /api/cms/export/users/           — CSV export (admin)
    GET /api/cms/export/my_data/         — JSON user data export (GDPR)
    """
    authentication_classes = [JWTAuthentication]

    def get_permissions(self):
        if self.action == 'my_data':
            return [IsAuthenticated()]
        return [IsAdminUser()]

    @action(detail=False, methods=['get'])
    def conversions(self, request):
        from api.cms.data_export import AdminDataExporter
        days = int(request.query_params.get('days', 30))
        return AdminDataExporter.export_conversions_csv(days)

    @action(detail=False, methods=['get'])
    def withdrawals(self, request):
        from api.cms.data_export import AdminDataExporter
        days = int(request.query_params.get('days', 30))
        return AdminDataExporter.export_withdrawals_csv(days)

    @action(detail=False, methods=['get'])
    def users(self, request):
        from api.cms.data_export import AdminDataExporter
        return AdminDataExporter.export_user_report()

    @action(detail=False, methods=['get'])
    def my_data(self, request):
        from api.cms.data_export import UserDataExporter
        import json
        from django.http import HttpResponse
        data = UserDataExporter.export_user_data(request.user)
        response = HttpResponse(
            json.dumps(data, default=str, indent=2),
            content_type='application/json'
        )
        response['Content-Disposition'] = 'attachment; filename="my_cms_data.json"'
        return response


# ─────────────────────────────────────────────
# Monitoring ViewSet
# ─────────────────────────────────────────────

class MonitoringViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET /api/cms/monitoring/metrics/     — Real-time metrics
    GET /api/cms/monitoring/sla/         — SLA report
    GET /api/cms/monitoring/alerts/      — Active alerts
    POST /api/cms/monitoring/alert/      — Trigger manual alert (admin)
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def metrics(self, request):
        from api.cms.monitoring import CMSMetrics
        return Response(CMSMetrics.get_dashboard())

    @action(detail=False, methods=['get'])
    def sla_report(self, request):
        from api.cms.monitoring import SLAMonitor
        return Response(SLAMonitor.get_sla_report())

    @action(detail=False, methods=['get'])
    def alerts(self, request):
        from api.cms.monitoring import AlertManager
        triggered = AlertManager.check_thresholds()
        return Response({'alerts': triggered, 'count': len(triggered)})

    @action(detail=False, methods=['post'])
    def trigger_alert(self, request):
        from api.cms.monitoring import AlertManager
        AlertManager.alert(
            level=request.data.get('level', 'warning'),
            title=request.data.get('title', 'Manual Alert'),
            message=request.data.get('message', ''),
            extra={'triggered_by': request.user.username},
        )
        return Response({'success': True})


# ─────────────────────────────────────────────
# Sanctions ViewSet (admin)
# ─────────────────────────────────────────────

class SanctionsViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    POST /api/cms/sanctions/ban_ip/          — Ban IP
    POST /api/cms/sanctions/unban_ip/        — Unban IP
    POST /api/cms/sanctions/suspend/         — Suspend user
    POST /api/cms/sanctions/unsuspend/       — Unsuspend user
    GET  /api/cms/sanctions/suspended/       — List suspended users
    POST /api/cms/sanctions/fraud_score/     — Calculate fraud score
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['post'])
    def ban_ip(self, request):
        from api.cms.sanctions import FraudScorer
        ip = request.data.get('ip', '').strip()
        if not ip:
            return Response({'error': 'ip required'}, status=400)
        reason = request.data.get('reason', 'Admin ban')
        hours = int(request.data.get('hours', 24))
        success = FraudScorer.ban_ip(ip, reason, hours)
        return Response({'success': success, 'ip': ip, 'hours': hours})

    @action(detail=False, methods=['post'])
    def unban_ip(self, request):
        from api.cms.sanctions import FraudScorer
        ip = request.data.get('ip', '').strip()
        FraudScorer.unban_ip(ip)
        return Response({'success': True, 'ip': ip})

    @action(detail=False, methods=['post'])
    def suspend_user(self, request):
        from api.cms.sanctions import SanctionService
        from django.contrib.auth import get_user_model
        user_id = request.data.get('user_id')
        reason = request.data.get('reason', '')
        try:
            target = get_user_model().objects.get(id=user_id)
        except Exception:
            return Response({'error': 'User not found'}, status=404)
        result = SanctionService.suspend_user(target, reason, admin=request.user)
        return Response(result)

    @action(detail=False, methods=['post'])
    def unsuspend_user(self, request):
        from api.cms.sanctions import SanctionService
        from django.contrib.auth import get_user_model
        user_id = request.data.get('user_id')
        try:
            target = get_user_model().objects.get(id=user_id)
        except Exception:
            return Response({'error': 'User not found'}, status=404)
        result = SanctionService.unsuspend_user(target, admin=request.user)
        return Response(result)

    @action(detail=False, methods=['get'])
    def suspended_users(self, request):
        from api.cms.sanctions import SanctionService
        users = SanctionService.get_suspended_users()
        return Response({'results': users, 'count': len(users)})

    @action(detail=False, methods=['post'])
    def fraud_score(self, request):
        from api.cms.sanctions import FraudScorer
        score, reasons = FraudScorer.score(
            user_id=request.data.get('user_id', 0),
            ip=request.data.get('ip', ''),
            subid=request.data.get('subid', ''),
            payout_usd=float(request.data.get('payout_usd', 0)),
        )
        return Response({
            'score': score,
            'risk_level': 'critical' if score >= 80 else 'high' if score >= 50 else 'low',
            'reasons': reasons,
        })


# ─────────────────────────────────────────────
# WorkflowViewSet — NEW
# FIX: WorkflowService.transition() was defined but never called from any
# viewset.  State changes went through raw model.save(), bypassing all
# validation, permission checks and hook firing defined in WorkflowService.
# ─────────────────────────────────────────────

class WorkflowViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    POST /api/cms/workflow/transition/       — Trigger a state transition
    GET  /api/cms/workflow/available/        — List valid transitions for an object
    GET  /api/cms/workflow/history/{pk}/     — Transition history for an object
    POST /api/cms/workflow/bulk_transition/  — Bulk state change (admin)

    All mutations go through WorkflowService.transition() so that:
      • WorkflowRule conditions are evaluated before the change is saved
      • CMSHooks.fire('workflow_transitioned') is called after save
      • Failed transitions return structured error objects (not raw 500s)
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def transition(self, request):
        """
        Transition a CMS object from one workflow state to another.

        Body:
          {
            "content_type": "page|blog|banner|popup",
            "object_id": 42,
            "to_state": "published",
            "comment": "Approved by editor"   ← optional
          }
        """
        from api.cms.services_new.WorkflowService import WorkflowService
        content_type = request.data.get('content_type', '')
        object_id = request.data.get('object_id')
        to_state = request.data.get('to_state', '')
        comment = request.data.get('comment', '')

        if not all([content_type, object_id, to_state]):
            return Response(
                {'error': 'content_type, object_id, and to_state are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = WorkflowService.transition(
            content_type=content_type,
            object_id=int(object_id),
            to_state=to_state,
            user=request.user,
            comment=comment,
        )
        if result.get('success'):
            return Response(result)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def available(self, request):
        """
        List valid next states for a given object.

        Query params: content_type, object_id
        """
        from api.cms.services_new.WorkflowService import WorkflowService
        content_type = request.query_params.get('content_type', '')
        object_id = request.query_params.get('object_id')
        if not all([content_type, object_id]):
            return Response(
                {'error': 'content_type and object_id are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        transitions = WorkflowService.get_available_transitions(
            content_type=content_type,
            object_id=int(object_id),
            user=request.user,
        )
        return Response({'transitions': transitions, 'count': len(transitions)})

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Transition history for a specific workflow state object."""
        from api.cms.models_new.workflow import WorkflowState
        try:
            ws = WorkflowState.objects.get(pk=pk)
        except WorkflowState.DoesNotExist:
            return Response({'error': 'WorkflowState not found'}, status=404)
        from api.cms.serializers import WorkflowTransitionSerializer
        transitions = ws.transitions.order_by('-created_at')[:50]
        return Response({
            'object_id': pk,
            'current_state': ws.state,
            'history': WorkflowTransitionSerializer(transitions, many=True).data,
        })

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def bulk_transition(self, request):
        """
        Bulk-transition multiple objects to the same target state.

        Body:
          {
            "content_type": "page",
            "object_ids": [1, 2, 3],
            "to_state": "archived",
            "comment": "Bulk archive by admin"
          }
        """
        from api.cms.services_new.WorkflowService import WorkflowService
        content_type = request.data.get('content_type', '')
        object_ids = request.data.get('object_ids', [])
        to_state = request.data.get('to_state', '')
        comment = request.data.get('comment', '')

        if not all([content_type, object_ids, to_state]):
            return Response(
                {'error': 'content_type, object_ids, and to_state are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = []
        success_count = 0
        fail_count = 0
        for oid in object_ids:
            r = WorkflowService.transition(
                content_type=content_type,
                object_id=int(oid),
                to_state=to_state,
                user=request.user,
                comment=comment,
            )
            results.append({'object_id': oid, **r})
            if r.get('success'):
                success_count += 1
            else:
                fail_count += 1

        return Response({
            'total': len(object_ids),
            'success_count': success_count,
            'fail_count': fail_count,
            'results': results,
        })
