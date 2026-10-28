# publisher_tools/views_reporting.py
"""
ReportingViewSet — performance_analytics/ subfolder-এর সব floating
functions এখানে API-তে wire করা হয়েছে।

Previously floating (এখন wired):
  performance_analytics/monthly_report.py   → generate_monthly_report, get_monthly_growth_trend
  performance_analytics/revenue_forecast.py → forecast_publisher_revenue, forecast_next_month
  performance_analytics/ecpm_analyzer.py    → get_ecpm_by_country, get_ecpm_by_format,
                                               get_ecpm_trend, get_ecpm_optimization_suggestions
  performance_analytics/fill_rate_analyzer.py → calculate_revenue_impact_of_low_fill,
                                                  identify_fill_rate_issues
  performance_analytics/publisher_dashboard.py → get_dashboard_summary, get_performance_alerts,
                                                   get_earnings_chart_data
  performance_analytics/revenue_tracker.py  → get_revenue_by_dimension, get_top_performing_units,
                                               get_revenue_trend
  performance_analytics/custom_report.py    → build_custom_report, export_report_to_csv

Register in urls.py:
  router.register(r'reports', ReportingViewSet, basename='reports')

Endpoints:
  GET  /api/publisher-tools/reports/monthly/
  GET  /api/publisher-tools/reports/monthly-trend/
  GET  /api/publisher-tools/reports/revenue-forecast/
  GET  /api/publisher-tools/reports/ecpm-breakdown/
  GET  /api/publisher-tools/reports/ecpm-suggestions/
  GET  /api/publisher-tools/reports/chart-data/
  GET  /api/publisher-tools/reports/top-units/
  GET  /api/publisher-tools/reports/revenue-trend/
  GET  /api/publisher-tools/reports/revenue-by-dimension/
  GET  /api/publisher-tools/reports/fill-rate-issues/
  GET  /api/publisher-tools/reports/fill-impact/
  POST /api/publisher-tools/reports/export/

DRY:
  - PublisherViewMixin:  self.publisher, self.handle_errors(), self.ok()
  - No local _get_publisher() — uses mixin property
  - No local try/except blocks — uses handle_errors() context manager
"""

from datetime import date
from decimal import Decimal, InvalidOperation
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from core.views import BaseViewSet
from .mixins import PublisherViewMixin
from .permissions import IsPublisher


class ReportingViewSet(PublisherViewMixin, BaseViewSet):
    """
    Publisher reporting API — all floating performance_analytics functions wired।

    Inherits from PublisherViewMixin:
      - self.publisher            → cached publisher (PermissionDenied if missing)
      - self.handle_errors()      → collapses try/except boilerplate
      - self.ok(data, message)    → standardised success response
    """

    permission_classes = [IsAuthenticated, IsPublisher]

    # ─────────────────────────────────────────────────────────────────────────
    # MONTHLY REPORTS
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='monthly')
    def monthly_report(self, request):
        """
        Monthly earnings summary।
        Wires: performance_analytics.monthly_report.generate_monthly_report()

        GET ?year=2025&month=6
        """
        pub = self.publisher
        try:
            year  = int(request.query_params.get('year',  date.today().year))
            month = int(request.query_params.get('month', date.today().month))
        except (ValueError, TypeError):
            return self.error_response('year and month must be integers.', status_code=400)

        if not (1 <= month <= 12):
            return self.error_response('month must be 1–12.', status_code=400)
        if year < 2000 or year > date.today().year + 1:
            return self.error_response('year out of valid range.', status_code=400)

        with self.handle_errors() as guard:
            from .performance_analytics.monthly_report import generate_monthly_report
            data = generate_monthly_report(pub, year=year, month=month)
            return self.ok(data)
        return guard.response

    @action(detail=False, methods=['get'], url_path='monthly-trend')
    def monthly_trend(self, request):
        """
        Month-over-month growth trend।
        Wires: performance_analytics.monthly_report.get_monthly_growth_trend()

        GET ?months=6
        """
        pub = self.publisher
        try:
            months = int(request.query_params.get('months', 6))
        except (ValueError, TypeError):
            months = 6

        months = max(1, min(months, 24))

        with self.handle_errors() as guard:
            from .performance_analytics.monthly_report import get_monthly_growth_trend
            data = get_monthly_growth_trend(pub, months=months)
            return self.ok({'months': months, 'trend': data})
        return guard.response

    # ─────────────────────────────────────────────────────────────────────────
    # REVENUE FORECAST
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='revenue-forecast')
    def revenue_forecast(self, request):
        """
        ML-based revenue forecast (linear regression on historical data)।
        Wires: performance_analytics.revenue_forecast.forecast_publisher_revenue()

        GET ?days=30
        """
        pub = self.publisher
        try:
            days = int(request.query_params.get('days', 30))
        except (ValueError, TypeError):
            days = 30

        days = max(1, min(days, 365))

        with self.handle_errors() as guard:
            from .performance_analytics.revenue_forecast import forecast_publisher_revenue
            data = forecast_publisher_revenue(pub, days_ahead=days)
            return self.ok(data)
        return guard.response

    @action(detail=False, methods=['get'], url_path='next-month-forecast')
    def next_month_forecast(self, request):
        """
        Next month revenue forecast।
        Wires: performance_analytics.revenue_forecast.forecast_next_month()

        GET (no params)
        """
        pub = self.publisher
        with self.handle_errors() as guard:
            from .performance_analytics.revenue_forecast import forecast_next_month
            data = forecast_next_month(pub)
            return self.ok(data)
        return guard.response

    # ─────────────────────────────────────────────────────────────────────────
    # eCPM BREAKDOWN
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='ecpm-breakdown')
    def ecpm_breakdown(self, request):
        """
        eCPM breakdown by country or ad format।
        Wires:
          performance_analytics.ecpm_analyzer.get_ecpm_by_country()
          performance_analytics.ecpm_analyzer.get_ecpm_by_format()

        GET ?by=country|format&start=2025-01-01&end=2025-01-31&days=30
        """
        pub = self.publisher
        by    = request.query_params.get('by', 'country')
        days  = int(request.query_params.get('days', 30))
        start_str = request.query_params.get('start')
        end_str   = request.query_params.get('end')

        try:
            if start_str and end_str:
                start = date.fromisoformat(start_str)
                end   = date.fromisoformat(end_str)
            else:
                from datetime import timedelta
                end   = date.today()
                start = end - timedelta(days=days)
        except ValueError:
            return self.error_response(
                'Invalid date format. Use ISO 8601: YYYY-MM-DD.', status_code=400
            )

        if by not in ('country', 'format'):
            return self.error_response(
                "by must be 'country' or 'format'.", status_code=400
            )

        with self.handle_errors() as guard:
            from .performance_analytics.ecpm_analyzer import (
                get_ecpm_by_country,
                get_ecpm_by_format,
            )
            if by == 'country':
                data = get_ecpm_by_country(pub, start, end)
            else:
                data = get_ecpm_by_format(pub, start, end)

            return self.ok({
                'by':    by,
                'start': str(start),
                'end':   str(end),
                'rows':  data,
            })
        return guard.response

    @action(detail=False, methods=['get'], url_path='ecpm-trend')
    def ecpm_trend(self, request):
        """
        eCPM trend over time।
        Wires: performance_analytics.ecpm_analyzer.get_ecpm_trend()

        GET ?days=30
        """
        pub = self.publisher
        try:
            days = int(request.query_params.get('days', 30))
        except (ValueError, TypeError):
            days = 30

        with self.handle_errors() as guard:
            from .performance_analytics.ecpm_analyzer import get_ecpm_trend
            data = get_ecpm_trend(pub, days=days)
            return self.ok({'days': days, 'trend': data})
        return guard.response

    @action(detail=False, methods=['get'], url_path='ecpm-suggestions')
    def ecpm_suggestions(self, request):
        """
        eCPM optimization suggestions।
        Wires: performance_analytics.ecpm_analyzer.get_ecpm_optimization_suggestions()

        GET (no params)
        """
        pub = self.publisher
        with self.handle_errors() as guard:
            from .performance_analytics.ecpm_analyzer import get_ecpm_optimization_suggestions
            data = get_ecpm_optimization_suggestions(pub)
            return self.ok({'suggestions': data, 'count': len(data)})
        return guard.response

    # ─────────────────────────────────────────────────────────────────────────
    # CHART DATA
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='chart-data')
    def chart_data(self, request):
        """
        Earnings chart data (time-series for frontend graphs)।
        Wires: performance_analytics.publisher_dashboard.get_earnings_chart_data()

        GET ?period=last_30_days&metric=revenue|impressions|ecpm|ctr|fill_rate
        """
        pub = self.publisher
        period = request.query_params.get('period', 'last_30_days')
        metric = request.query_params.get('metric', 'revenue')

        valid_periods = (
            'today', 'yesterday', 'last_7_days', 'last_30_days',
            'last_90_days', 'this_month', 'last_month', 'this_year',
        )
        valid_metrics = ('revenue', 'impressions', 'ecpm', 'ctr', 'fill_rate')

        if period not in valid_periods:
            return self.error_response(
                f'Invalid period. Valid: {valid_periods}', status_code=400
            )
        if metric not in valid_metrics:
            return self.error_response(
                f'Invalid metric. Valid: {valid_metrics}', status_code=400
            )

        with self.handle_errors() as guard:
            from .performance_analytics.publisher_dashboard import get_earnings_chart_data
            data = get_earnings_chart_data(pub, period=period, metric=metric)
            return self.ok({'period': period, 'metric': metric, 'chart': data})
        return guard.response

    # ─────────────────────────────────────────────────────────────────────────
    # TOP UNITS / REVENUE TRACKER
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='top-units')
    def top_units(self, request):
        """
        Top performing ad units ranked by revenue।
        Wires: performance_analytics.revenue_tracker.get_top_performing_units()

        GET ?days=30&limit=10
        """
        pub = self.publisher
        try:
            days  = int(request.query_params.get('days', 30))
            limit = int(request.query_params.get('limit', 10))
        except (ValueError, TypeError):
            return self.error_response('days and limit must be integers.', status_code=400)

        limit = max(1, min(limit, 100))
        days  = max(1, min(days, 365))

        with self.handle_errors() as guard:
            from .performance_analytics.revenue_tracker import get_top_performing_units
            data = get_top_performing_units(pub, days=days, limit=limit)
            return self.ok({'days': days, 'limit': limit, 'units': data, 'count': len(data)})
        return guard.response

    @action(detail=False, methods=['get'], url_path='revenue-trend')
    def revenue_trend(self, request):
        """
        Day-by-day revenue trend।
        Wires: performance_analytics.revenue_tracker.get_revenue_trend()

        GET ?days=30
        """
        pub = self.publisher
        try:
            days = int(request.query_params.get('days', 30))
        except (ValueError, TypeError):
            days = 30

        days = max(1, min(days, 365))

        with self.handle_errors() as guard:
            from .performance_analytics.revenue_tracker import get_revenue_trend
            data = get_revenue_trend(pub, days=days)
            return self.ok({'days': days, 'trend': data})
        return guard.response

    @action(detail=False, methods=['get'], url_path='revenue-by-dimension')
    def revenue_by_dimension(self, request):
        """
        Revenue grouped by a dimension (country, format, device, site)।
        Wires: performance_analytics.revenue_tracker.get_revenue_by_dimension()

        GET ?dimension=country|format|device|site&days=30
        """
        pub = self.publisher
        dimension = request.query_params.get('dimension', 'country')
        try:
            days = int(request.query_params.get('days', 30))
        except (ValueError, TypeError):
            days = 30

        valid_dims = ('country', 'format', 'device', 'site', 'ad_unit')
        if dimension not in valid_dims:
            return self.error_response(
                f'Invalid dimension. Valid: {valid_dims}', status_code=400
            )

        with self.handle_errors() as guard:
            from .performance_analytics.revenue_tracker import get_revenue_by_dimension
            data = get_revenue_by_dimension(pub, dimension=dimension, days=days)
            return self.ok({'dimension': dimension, 'days': days, 'rows': data})
        return guard.response

    # ─────────────────────────────────────────────────────────────────────────
    # FILL RATE
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='fill-rate-issues')
    def fill_rate_issues(self, request):
        """
        Ad units with fill rate below threshold।
        Wires: performance_analytics.fill_rate_analyzer.identify_fill_rate_issues()

        GET ?threshold=50&days=30
        """
        pub = self.publisher
        try:
            threshold = float(request.query_params.get('threshold', 50.0))
            days      = int(request.query_params.get('days', 30))
        except (ValueError, TypeError):
            return self.error_response('threshold and days must be numbers.', status_code=400)

        with self.handle_errors() as guard:
            from .performance_analytics.fill_rate_analyzer import identify_fill_rate_issues
            data = identify_fill_rate_issues(pub, threshold=threshold)
            return self.ok({'threshold': threshold, 'issues': data, 'count': len(data)})
        return guard.response

    @action(detail=False, methods=['get'], url_path='fill-impact')
    def fill_impact(self, request):
        """
        Revenue impact of increasing fill rate for a specific ad unit।
        Wires: performance_analytics.fill_rate_analyzer.calculate_revenue_impact_of_low_fill()

        GET ?unit_id=<id>&target_fill=80
        """
        pub     = self.publisher
        unit_id = request.query_params.get('unit_id')
        if not unit_id:
            return self.error_response('unit_id is required.', status_code=400)

        try:
            target_fill = float(request.query_params.get('target_fill', 80.0))
        except (ValueError, TypeError):
            target_fill = 80.0

        with self.handle_errors() as guard:
            from .models import AdUnit
            try:
                unit = AdUnit.objects.get(
                    unit_id=unit_id,
                    publisher=pub,
                )
            except AdUnit.DoesNotExist:
                return self.error_response(
                    f'Ad unit {unit_id!r} not found.', status_code=404
                )

            from .performance_analytics.fill_rate_analyzer import (
                calculate_revenue_impact_of_low_fill,
            )
            data = calculate_revenue_impact_of_low_fill(unit, target_fill_rate=target_fill)
            return self.ok(data)
        return guard.response

    @action(detail=False, methods=['get'], url_path='fill-rate-by-unit')
    def fill_rate_by_unit(self, request):
        """
        Per-unit fill rate breakdown।
        Wires: performance_analytics.fill_rate_analyzer.get_fill_rate_by_unit()

        GET ?days=30
        """
        pub = self.publisher
        try:
            days = int(request.query_params.get('days', 30))
        except (ValueError, TypeError):
            days = 30

        with self.handle_errors() as guard:
            from .performance_analytics.fill_rate_analyzer import get_fill_rate_by_unit
            data = get_fill_rate_by_unit(pub, days=days)
            return self.ok({'days': days, 'units': data, 'count': len(data)})
        return guard.response

    # ─────────────────────────────────────────────────────────────────────────
    # PERFORMANCE ALERTS
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='alerts')
    def performance_alerts(self, request):
        """
        Publisher performance alerts (fill drop, eCPM drop, IVT spike, etc.)।
        Wires: performance_analytics.publisher_dashboard.get_performance_alerts()

        GET (no params)
        """
        pub = self.publisher
        with self.handle_errors() as guard:
            from .performance_analytics.publisher_dashboard import get_performance_alerts
            data = get_performance_alerts(pub)
            return self.ok({'alerts': data, 'count': len(data)})
        return guard.response

    # ─────────────────────────────────────────────────────────────────────────
    # CUSTOM REPORT / EXPORT
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='export')
    def export_report(self, request):
        """
        Build and export a custom report (CSV or JSON)।
        Wires:
          performance_analytics.custom_report.build_custom_report()
          performance_analytics.custom_report.export_report_to_csv()

        POST body:
          {
            "metrics":    ["revenue", "impressions", "ecpm"],
            "dimensions": ["date", "country"],
            "start_date": "2025-01-01",
            "end_date":   "2025-01-31",
            "format":     "csv" | "json"   (default: json)
          }
        """
        pub     = self.publisher
        data    = request.data
        metrics    = data.get('metrics',    ['revenue', 'impressions', 'ecpm'])
        dimensions = data.get('dimensions', ['date'])
        fmt        = data.get('format', 'json')
        start_str  = data.get('start_date')
        end_str    = data.get('end_date')

        if fmt not in ('csv', 'json'):
            return self.error_response("format must be 'csv' or 'json'.", status_code=400)

        if not isinstance(metrics, list) or not isinstance(dimensions, list):
            return self.error_response('metrics and dimensions must be lists.', status_code=400)

        try:
            if start_str and end_str:
                start = date.fromisoformat(start_str)
                end   = date.fromisoformat(end_str)
            else:
                from datetime import timedelta
                end   = date.today()
                start = end - timedelta(days=30)
        except ValueError:
            return self.error_response(
                'Invalid date format. Use YYYY-MM-DD.', status_code=400
            )

        if start > end:
            return self.error_response('start_date must be before end_date.', status_code=400)

        with self.handle_errors() as guard:
            from .performance_analytics.custom_report import build_custom_report
            report_data = build_custom_report(
                publisher=pub,
                metrics=metrics,
                dimensions=dimensions,
                start_date=start,
                end_date=end,
            )

            if fmt == 'csv':
                from .performance_analytics.custom_report import export_report_to_csv
                csv_str = export_report_to_csv(report_data)
                from django.http import HttpResponse
                resp = HttpResponse(csv_str, content_type='text/csv')
                resp['Content-Disposition'] = (
                    f'attachment; filename="report_{start}_{end}.csv"'
                )
                return resp

            return self.ok(report_data)
        return guard.response
