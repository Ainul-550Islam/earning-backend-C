# api/cms/viewsets_new/SurveyAnalyticsViewSet.py
"""
Survey Analytics API — exposes SurveyAnalyticsService logic that was entirely
internal (no routes existed).

Endpoints:
  GET  /v3/survey-analytics/overview/               — platform-wide dashboard
  GET  /v3/survey-analytics/realtime/               — live metrics
  GET  /v3/survey-analytics/survey/<uuid>/report/   — per-survey performance
  GET  /v3/survey-analytics/user/<user_id>/         — per-user analytics (admin)
  GET  /v3/survey-analytics/me/                     — own analytics
"""
import logging
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

logger = logging.getLogger('api.cms.viewsets')


class SurveyAnalyticsViewSet(viewsets.ViewSet):
    """
    Read-only analytics surface for the survey system.
    All heavy lifting is delegated to SurveyAnalyticsService.
    """
    permission_classes = [permissions.IsAuthenticated]

    def _service(self):
        from ..services_new.SurveyAnalyticsService import SurveyAnalyticsService
        return SurveyAnalyticsService()

    # ── Platform-wide ──────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAdminUser])
    def overview(self, request):
        """
        GET /v3/survey-analytics/overview/?days=30
        Platform-wide completion counts, reward totals, drop-off rates.
        """
        days = int(request.query_params.get('days', 30))
        try:
            data = self._service().get_dashboard_overview(days=days)
            return Response(data)
        except Exception as exc:
            logger.error(f"SurveyAnalytics.overview failed: {exc}")
            return Response({'detail': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAdminUser])
    def realtime(self, request):
        """
        GET /v3/survey-analytics/realtime/
        Live metrics: active users, submissions in last 5 min, live revenue.
        """
        try:
            data = self._service().get_real_time_metrics()
            return Response(data)
        except Exception as exc:
            logger.error(f"SurveyAnalytics.realtime failed: {exc}")
            return Response({'detail': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ── Per-survey ─────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='survey/(?P<survey_uuid>[^/.]+)/report',
            permission_classes=[permissions.IsAdminUser])
    def survey_report(self, request, survey_uuid=None):
        """
        GET /v3/survey-analytics/survey/<uuid>/report/?days=30
        Completion funnel, demographic breakdown, financial summary for one survey.
        """
        days = int(request.query_params.get('days', 30))
        try:
            data = self._service().get_survey_performance_report(survey_uuid, days=days)
            return Response(data)
        except Exception as exc:
            logger.error(f"SurveyAnalytics.survey_report failed: {exc}")
            return Response({'detail': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ── Per-user (admin) ───────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='user/(?P<user_id>[0-9]+)',
            permission_classes=[permissions.IsAdminUser])
    def user_analytics(self, request, user_id=None):
        """
        GET /v3/survey-analytics/user/<user_id>/?days=30
        Individual user completion history, quality score trend, earnings.
        """
        days = int(request.query_params.get('days', 30))
        try:
            data = self._service().get_user_analytics(int(user_id), days=days)
            return Response(data)
        except Exception as exc:
            logger.error(f"SurveyAnalytics.user_analytics failed: {exc}")
            return Response({'detail': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ── Self-service ───────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def me(self, request):
        """
        GET /v3/survey-analytics/me/?days=30
        The authenticated user's own analytics (no admin needed).
        """
        days = int(request.query_params.get('days', 30))
        try:
            data = self._service().get_user_analytics(request.user.id, days=days)
            return Response(data)
        except Exception as exc:
            logger.error(f"SurveyAnalytics.me failed: {exc}")
            return Response({'detail': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
