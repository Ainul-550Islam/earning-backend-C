# publisher_tools/views_analytics.py
# ============================================================
# NEW FILE — AnalyticsViewSet
# Exposes performance_analytics subfolder via DRF.
#
# Register in urls.py:
#   router.register(r'analytics', AnalyticsViewSet, basename='analytics')
# ============================================================
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin

from core.views import BaseViewSet
from .permissions import IsPublisher, IsAdminOrPublisher
from .serializers import DateRangeSerializer, ReportFilterSerializer


class AnalyticsViewSet(BaseViewSet):
    """
    Performance Analytics।
    publisher_tools/performance_analytics/ subfolder-এর সব
    analytics functions এখানে API হিসেবে expose করা হয়েছে।

    Actions:
      dashboard      — full dashboard summary
      realtime       — live stats
      ecpm           — eCPM breakdown (by country / format / trend)
      ctr            — CTR analysis + anomaly detection
      rpm            — RPM by site + benchmarks
      fill_rate      — fill rate by unit + issues
      revenue        — revenue by dimension + top units
      forecast       — revenue forecast (linear regression)
      report/daily   — daily report
      report/weekly  — weekly report
      report/monthly — monthly report
      report/hourly  — hourly report
      report/custom  — custom date+dimension report
      alerts         — performance alerts
    """
    # No queryset — all actions are read-only analytics
    permission_classes = [IsAuthenticated, IsPublisher]
    http_method_names  = ['get', 'head', 'options']

    def _get_publisher(self):
        try:
            return self.request.user.publisher_profile
        except Exception:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No active publisher profile found.')

    # ── DASHBOARD ────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard(self, request):
        """
        Full publisher dashboard।
        GET /analytics/dashboard/?period=last_30_days
        """
        publisher = self._get_publisher()
        period    = request.query_params.get('period', 'last_30_days')

        try:
            from .performance_analytics import get_dashboard_summary, get_performance_alerts
            data   = get_dashboard_summary(publisher, period)
            alerts = get_performance_alerts(publisher)
        except (ImportError, Exception) as e:
            return self.error_response(f'Analytics service unavailable: {str(e)}', status_code=503)

        return self.success_response(data={**data, 'alerts': alerts})

    # ── REALTIME ──────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='realtime')
    def realtime(self, request):
        """
        Live stats।
        GET /analytics/realtime/
        """
        publisher = self._get_publisher()

        try:
            from .performance_analytics import get_realtime_stats, get_live_stats
            data = get_realtime_stats(publisher)
            data['live'] = get_live_stats(publisher)
        except (ImportError, Exception) as e:
            return self.error_response(f'Real-time analytics unavailable: {str(e)}', status_code=503)

        return self.success_response(data=data)

    # ── eCPM ─────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='ecpm')
    def ecpm(self, request):
        """
        eCPM analysis।
        GET /analytics/ecpm/?breakdown=country&start_date=2025-01-01&end_date=2025-01-31
        Breakdown options: country, format, trend
        """
        publisher = self._get_publisher()
        breakdown = request.query_params.get('breakdown', 'country')

        s = DateRangeSerializer(data=request.query_params)
        if not s.is_valid():
            return self.error_response(s.errors, status_code=400)

        start_date = s.validated_data['start_date']
        end_date   = s.validated_data['end_date']
        days       = (end_date - start_date).days or 30

        try:
            from .performance_analytics import get_ecpm_by_country, get_ecpm_by_format, get_ecpm_trend
            if breakdown == 'country':
                data = get_ecpm_by_country(publisher, start_date, end_date)
            elif breakdown == 'format':
                data = get_ecpm_by_format(publisher, start_date, end_date)
            elif breakdown == 'trend':
                data = get_ecpm_trend(publisher, days=days)
            else:
                return self.error_response(
                    f'Invalid breakdown {breakdown!r}. Options: country, format, trend',
                    status_code=400,
                )
        except (ImportError, Exception) as e:
            return self.error_response(f'eCPM analytics unavailable: {str(e)}', status_code=503)

        return self.success_response(data=data)

    # ── CTR ──────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='ctr')
    def ctr(self, request):
        """
        CTR analysis।
        GET /analytics/ctr/?breakdown=format&days=30
        """
        publisher = self._get_publisher()
        breakdown = request.query_params.get('breakdown', 'format')
        days      = int(request.query_params.get('days', 30))

        try:
            from .performance_analytics import get_ctr_by_format, get_ctr_trend, identify_ctr_anomalies
            if breakdown == 'format':
                data = get_ctr_by_format(publisher, days=days)
            elif breakdown == 'trend':
                data = get_ctr_trend(publisher, days=days)
            elif breakdown == 'anomalies':
                data = identify_ctr_anomalies(publisher, days=min(days, 7))
            else:
                return self.error_response(
                    f'Invalid breakdown {breakdown!r}. Options: format, trend, anomalies',
                    status_code=400,
                )
        except (ImportError, Exception) as e:
            return self.error_response(f'CTR analytics unavailable: {str(e)}', status_code=503)

        return self.success_response(data=data)

    # ── RPM ───────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='rpm')
    def rpm(self, request):
        """
        RPM analysis।
        GET /analytics/rpm/?days=30
        """
        publisher = self._get_publisher()
        days      = int(request.query_params.get('days', 30))

        try:
            from .performance_analytics import get_rpm_by_publisher, get_rpm_benchmarks
            publisher_rpm = get_rpm_by_publisher(publisher, days=days)
            benchmarks    = get_rpm_benchmarks()
        except (ImportError, Exception) as e:
            return self.error_response(f'RPM analytics unavailable: {str(e)}', status_code=503)

        return self.success_response(data={
            'publisher_rpm': publisher_rpm,
            'benchmarks':    benchmarks,
        })

    # ── FILL RATE ─────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='fill-rate')
    def fill_rate(self, request):
        """
        Fill rate analysis।
        GET /analytics/fill-rate/?breakdown=unit&days=30
        """
        publisher = self._get_publisher()
        breakdown = request.query_params.get('breakdown', 'unit')
        days      = int(request.query_params.get('days', 30))

        try:
            from .performance_analytics import (
                get_fill_rate_by_unit, get_fill_rate_by_country, identify_fill_rate_issues
            )
            if breakdown == 'unit':
                data = get_fill_rate_by_unit(publisher, days=days)
            elif breakdown == 'country':
                data = get_fill_rate_by_country(publisher, days=days)
            elif breakdown == 'issues':
                data = identify_fill_rate_issues(publisher, threshold=50.0)
            else:
                return self.error_response(
                    f'Invalid breakdown {breakdown!r}. Options: unit, country, issues',
                    status_code=400,
                )
        except (ImportError, Exception) as e:
            return self.error_response(f'Fill rate analytics unavailable: {str(e)}', status_code=503)

        return self.success_response(data=data)

    # ── REVENUE ───────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='revenue')
    def revenue(self, request):
        """
        Revenue analysis।
        GET /analytics/revenue/?breakdown=top_units&days=30
        """
        publisher  = self._get_publisher()
        breakdown  = request.query_params.get('breakdown', 'trend')
        days       = int(request.query_params.get('days', 30))
        limit      = int(request.query_params.get('limit', 10))
        start_date = request.query_params.get('start_date')
        end_date   = request.query_params.get('end_date')
        dimension  = request.query_params.get('dimension', 'date')

        try:
            from .performance_analytics import (
                get_revenue_by_dimension, get_top_performing_units, get_revenue_trend
            )
            if breakdown == 'top_units':
                data = get_top_performing_units(publisher, days=days, limit=limit)
            elif breakdown == 'trend':
                data = get_revenue_trend(publisher, days=days)
            elif breakdown == 'dimension':
                from datetime import date, timedelta
                sd = date.fromisoformat(start_date) if start_date else date.today() - timedelta(days=days)
                ed = date.fromisoformat(end_date)   if end_date   else date.today()
                data = get_revenue_by_dimension(publisher, sd, ed, dimension=dimension)
            else:
                return self.error_response(
                    f'Invalid breakdown {breakdown!r}. Options: top_units, trend, dimension',
                    status_code=400,
                )
        except (ImportError, Exception) as e:
            return self.error_response(f'Revenue analytics unavailable: {str(e)}', status_code=503)

        return self.success_response(data=data)

    # ── FORECAST ──────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='forecast')
    def forecast(self, request):
        """
        Revenue forecast (linear regression)।
        GET /analytics/forecast/?days_ahead=30
        """
        publisher  = self._get_publisher()
        days_ahead = int(request.query_params.get('days_ahead', 30))
        next_month = request.query_params.get('next_month', 'false').lower() == 'true'

        try:
            from .performance_analytics import forecast_publisher_revenue, forecast_next_month
            if next_month:
                data = forecast_next_month(publisher)
            else:
                data = forecast_publisher_revenue(publisher, days_ahead=days_ahead)
        except (ImportError, Exception) as e:
            return self.error_response(f'Forecast service unavailable: {str(e)}', status_code=503)

        return self.success_response(data=data)

    # ── REPORTS ───────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='report/daily')
    def report_daily(self, request):
        """
        Daily report।
        GET /analytics/report/daily/?date=2025-01-15
        """
        publisher   = self._get_publisher()
        from datetime import date as dt
        report_date_str = request.query_params.get('date')
        report_date     = dt.fromisoformat(report_date_str) if report_date_str else None

        try:
            from .performance_analytics import generate_daily_report, get_daily_comparison
            report     = generate_daily_report(publisher, report_date=report_date)
            comparison = get_daily_comparison(publisher, days=7)
            report['comparison'] = comparison
        except (ImportError, Exception) as e:
            return self.error_response(f'Report service unavailable: {str(e)}', status_code=503)

        return self.success_response(data=report)

    @action(detail=False, methods=['get'], url_path='report/weekly')
    def report_weekly(self, request):
        """
        Weekly report।
        GET /analytics/report/weekly/?week_start=2025-01-13
        """
        publisher       = self._get_publisher()
        from datetime import date as dt
        week_start_str  = request.query_params.get('week_start')
        week_start      = dt.fromisoformat(week_start_str) if week_start_str else None

        try:
            from .performance_analytics import generate_weekly_report
            data = generate_weekly_report(publisher, week_start=week_start)
        except (ImportError, Exception) as e:
            return self.error_response(f'Report service unavailable: {str(e)}', status_code=503)

        return self.success_response(data=data)

    @action(detail=False, methods=['get'], url_path='report/monthly')
    def report_monthly(self, request):
        """
        Monthly report।
        GET /analytics/report/monthly/?year=2025&month=1
        """
        publisher = self._get_publisher()
        year      = request.query_params.get('year')
        month     = request.query_params.get('month')

        try:
            from .performance_analytics import generate_monthly_report, get_monthly_growth_trend
            report  = generate_monthly_report(publisher,
                year=int(year) if year else None,
                month=int(month) if month else None,
            )
            growth  = get_monthly_growth_trend(publisher, months=6)
            report['growth_trend'] = growth
        except (ImportError, Exception) as e:
            return self.error_response(f'Report service unavailable: {str(e)}', status_code=503)

        return self.success_response(data=report)

    @action(detail=False, methods=['get'], url_path='report/hourly')
    def report_hourly(self, request):
        """
        Hourly report।
        GET /analytics/report/hourly/?date=2025-01-15
        """
        publisher = self._get_publisher()
        from datetime import date as dt
        date_str  = request.query_params.get('date')
        if not date_str:
            return self.error_response('date parameter is required (YYYY-MM-DD)', status_code=400)
        try:
            report_date = dt.fromisoformat(date_str)
        except ValueError:
            return self.error_response('Invalid date format. Use YYYY-MM-DD.', status_code=400)

        try:
            from .performance_analytics import generate_hourly_report, get_best_hours
            report     = generate_hourly_report(publisher, report_date=report_date)
            best_hours = get_best_hours(publisher, days=30)
            report['best_hours'] = best_hours
        except (ImportError, Exception) as e:
            return self.error_response(f'Hourly report unavailable: {str(e)}', status_code=503)

        return self.success_response(data=report)

    @action(detail=False, methods=['get'], url_path='report/custom')
    def report_custom(self, request):
        """
        Custom report।
        GET /analytics/report/custom/?start_date=...&end_date=...&dimensions=date,country&metrics=revenue,impressions
        """
        publisher  = self._get_publisher()
        dimensions = request.query_params.get('dimensions', 'date').split(',')
        metrics    = request.query_params.get('metrics', 'revenue,impressions,ecpm').split(',')
        group_by   = request.query_params.get('group_by', dimensions[0] if dimensions else 'date')

        s = DateRangeSerializer(data=request.query_params)
        if not s.is_valid():
            return self.error_response(s.errors, status_code=400)

        try:
            from .performance_analytics import build_custom_report
            data = build_custom_report(
                publisher,
                start_date=s.validated_data['start_date'],
                end_date=s.validated_data['end_date'],
                dimensions=dimensions,
                metrics=metrics,
                group_by=group_by,
            )
        except (ImportError, Exception) as e:
            return self.error_response(f'Custom report unavailable: {str(e)}', status_code=503)

        return self.success_response(data=data)

    # ── ALERTS ────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='alerts')
    def alerts(self, request):
        """
        Performance alerts।
        GET /analytics/alerts/
        """
        publisher = self._get_publisher()

        try:
            from .performance_analytics import get_performance_alerts, identify_ctr_anomalies, identify_fill_rate_issues
            perf_alerts  = get_performance_alerts(publisher)
            ctr_anomalies = identify_ctr_anomalies(publisher, days=7)
            fill_issues   = identify_fill_rate_issues(publisher, threshold=50.0)
        except (ImportError, Exception) as e:
            return self.error_response(f'Alerts service unavailable: {str(e)}', status_code=503)

        return self.success_response(data={
            'performance_alerts': perf_alerts,
            'ctr_anomalies':      ctr_anomalies,
            'fill_rate_issues':   fill_issues,
            'total_count':        len(perf_alerts) + len(ctr_anomalies) + len(fill_issues),
        })
