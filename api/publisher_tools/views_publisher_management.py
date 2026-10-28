# publisher_tools/views_publisher_management.py
# Exposes publisher_management/ subfolder logic via DRF.
# Register: router.register(r'publisher-tools', PublisherManagementViewSet, basename='publisher-tool')

from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher


class PublisherManagementViewSet(BaseViewSet):
    """
    Publisher Management Tools API.
    publisher_management/ subfolder expose করা হয়েছে।

    Publisher endpoints:
      GET /publisher-tools/overview/         — full revenue + performance overview
      GET /publisher-tools/revenue-breakdown/— revenue by dimension
      GET /publisher-tools/metrics/          — KPI metrics
      GET /publisher-tools/forecast/         — revenue forecast
      GET /publisher-tools/top-content/      — top earning content
      GET /publisher-tools/profile/          — profile completion + level
      GET /publisher-tools/health-score/     — publisher health score
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def _get_publisher(self):
        try:
            return self.request.user.publisher_profile
        except Exception:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No active publisher profile.')

    # ── Overview ──────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='overview')
    def overview(self, request):
        """
        Full publisher overview with revenue + metrics.
        GET /publisher-tools/overview/?period=last_30_days
        """
        publisher = self._get_publisher()
        period    = request.query_params.get('period', 'last_30_days')

        try:
            from .publisher_management import get_publisher_overview, get_revenue_breakdown
            from .utils import get_date_range
            start_date, end_date = get_date_range(period)
            overview  = get_publisher_overview(publisher, period=period)
            breakdown = get_revenue_breakdown(publisher, start_date, end_date)
            overview['revenue_breakdown'] = breakdown
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=overview)

    # ── Revenue Breakdown ─────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='revenue-breakdown')
    def revenue_breakdown(self, request):
        """
        Revenue breakdown by format, country, site, ad unit.
        GET /publisher-tools/revenue-breakdown/?start_date=2025-01-01&end_date=2025-01-31
        """
        publisher = self._get_publisher()
        from .serializers import DateRangeSerializer
        s = DateRangeSerializer(data=request.query_params)
        if not s.is_valid():
            return self.error_response(s.errors, status_code=400)

        try:
            from .publisher_management import get_revenue_breakdown
            data = get_revenue_breakdown(
                publisher,
                s.validated_data['start_date'],
                s.validated_data['end_date'],
            )
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=data)

    # ── KPI Metrics ───────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='metrics')
    def metrics(self, request):
        """
        KPI metrics (eCPM, fill rate, CTR, RPM).
        GET /publisher-tools/metrics/?days=30
        """
        publisher = self._get_publisher()
        days      = int(request.query_params.get('days', 30))

        try:
            from .publisher_management import get_performance_metrics
            data = get_performance_metrics(publisher, days=days)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=data)

    # ── Revenue Forecast ──────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='forecast')
    def forecast(self, request):
        """
        Revenue forecast (30-day linear regression).
        GET /publisher-tools/forecast/?days_ahead=30
        """
        publisher  = self._get_publisher()
        days_ahead = int(request.query_params.get('days_ahead', 30))

        try:
            from .publisher_management import get_revenue_forecast
            data = get_revenue_forecast(publisher, days_ahead=days_ahead)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=data)

    # ── Top Content ───────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='top-content')
    def top_content(self, request):
        """
        Top earning content / pages.
        GET /publisher-tools/top-content/?days=30&limit=10
        """
        publisher = self._get_publisher()
        days      = int(request.query_params.get('days', 30))
        limit     = int(request.query_params.get('limit', 10))

        try:
            from .publisher_management import get_top_earning_content
            data = get_top_earning_content(publisher, days=days, limit=limit)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=data)

    # ── Profile Completion ────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='profile')
    def profile(self, request):
        """
        Profile completion % + publisher level.
        GET /publisher-tools/profile/
        """
        publisher = self._get_publisher()

        try:
            from .publisher_management import (
                get_publisher_profile_completion,
                get_publisher_level,
            )
            completion = get_publisher_profile_completion(publisher)
            level      = get_publisher_level(publisher)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'profile_completion': completion,
            'publisher_level':    level,
        })

    # ── Health Score ──────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='health-score')
    def health_score(self, request):
        """
        Publisher health score (0-100).
        GET /publisher-tools/health-score/
        """
        publisher = self._get_publisher()

        try:
            from .publisher_management import calculate_publisher_health_score
            score = calculate_publisher_health_score(publisher)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        grade = 'A' if score >= 90 else 'B' if score >= 75 else 'C' if score >= 60 else 'D' if score >= 40 else 'F'
        return self.success_response(data={
            'health_score': score,
            'grade':        grade,
            'publisher_id': publisher.publisher_id,
        })
