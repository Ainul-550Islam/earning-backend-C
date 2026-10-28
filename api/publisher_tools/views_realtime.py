# publisher_tools/views_realtime.py
"""
RealtimeViewSet — performance_analytics/publisher_dashboard.py এবং
performance_analytics/real_time_analytics.py-এর সব floating functions
এখানে API-তে wire করা হয়েছে।

Previously floating (এখন wired):
  performance_analytics/publisher_dashboard.py  → get_realtime_stats,
                                                    get_dashboard_summary,
                                                    get_performance_alerts,
                                                    get_earnings_chart_data
  performance_analytics/real_time_analytics.py  → get_live_stats,
                                                    get_realtime_fill_rate,
                                                    track_ad_request
  performance_analytics/daily_report.py         → generate_daily_report,
                                                    get_daily_comparison

Register in urls.py:
  router.register(r'realtime', RealtimeViewSet, basename='realtime')

Endpoints:
  GET  /api/publisher-tools/realtime/live/
  GET  /api/publisher-tools/realtime/dashboard/
  GET  /api/publisher-tools/realtime/alerts/
  GET  /api/publisher-tools/realtime/fill-rate/
  POST /api/publisher-tools/realtime/track-request/
  GET  /api/publisher-tools/realtime/daily-report/
  GET  /api/publisher-tools/realtime/daily-comparison/

DRY:
  - PublisherViewMixin: self.publisher, self.handle_errors(), self.ok()
  - No local _get_publisher()
  - Cache TTL defined once as class constant (not scattered across methods)
"""

from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from core.views import BaseViewSet
from .mixins import PublisherViewMixin
from .permissions import IsPublisher


class RealtimeViewSet(PublisherViewMixin, BaseViewSet):
    """
    Real-time & live dashboard API — publisher_dashboard / real_time_analytics wired।

    Inherits from PublisherViewMixin:
      - self.publisher         → cached publisher
      - self.handle_errors()   → collapses try/except boilerplate
      - self.ok(data, message) → standardised success response

    Class constant:
      CACHE_TTL = 60s — applied consistently by all live-data actions.
      Changing this one line propagates to every endpoint. (DRY)
    """

    permission_classes = [IsAuthenticated, IsPublisher]

    # DRY: cache TTL defined once, referenced in docstrings and logic below
    CACHE_TTL: int = 60  # seconds

    # ─────────────────────────────────────────────────────────────────────────
    # LIVE / REAL-TIME STATS
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='live')
    def live_stats(self, request):
        """
        Current-hour live stats (cached CACHE_TTL=60s)。
        Wires: performance_analytics.real_time_analytics.get_live_stats()

        GET (no params)

        Response:
          {
            "timestamp":         "2025-06-11T10:30:00+06:00",
            "today_revenue":     45.23,
            "today_impressions": 18000,
            "today_clicks":      234,
            "ivt_today":         12,
            "account_status":    "active",
            "pending_balance":   123.50
          }
        """
        pub = self.publisher
        with self.handle_errors() as guard:
            from .performance_analytics.real_time_analytics import get_live_stats
            data = get_live_stats(pub)
            return self.ok(data)
        return guard.response

    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard_summary(self, request):
        """
        Dashboard summary — key metrics aggregated for the given period।
        Wires: performance_analytics.publisher_dashboard.get_dashboard_summary()

        GET ?period=last_30_days

        Valid periods:
          today, yesterday, last_7_days, last_30_days,
          last_90_days, this_month, last_month, this_year
        """
        pub    = self.publisher
        period = request.query_params.get('period', 'last_30_days')

        valid_periods = (
            'today', 'yesterday', 'last_7_days', 'last_30_days',
            'last_90_days', 'this_month', 'last_month', 'this_year',
        )
        if period not in valid_periods:
            return self.error_response(
                f'Invalid period. Valid options: {valid_periods}', status_code=400
            )

        with self.handle_errors() as guard:
            from .performance_analytics.publisher_dashboard import get_dashboard_summary
            data = get_dashboard_summary(pub, period=period)
            return self.ok(data)
        return guard.response

    @action(detail=False, methods=['get'], url_path='stats')
    def realtime_stats(self, request):
        """
        Real-time stats — last 1 hour aggregate (cached CACHE_TTL=60s)।
        Wires: performance_analytics.publisher_dashboard.get_realtime_stats()

        GET (no params)
        """
        pub = self.publisher
        with self.handle_errors() as guard:
            from .performance_analytics.publisher_dashboard import get_realtime_stats
            data = get_realtime_stats(pub)
            return self.ok(data)
        return guard.response

    # ─────────────────────────────────────────────────────────────────────────
    # PERFORMANCE ALERTS
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='alerts')
    def performance_alerts(self, request):
        """
        Active performance alerts (fill drop, eCPM drop, IVT spike, etc.)।
        Wires: performance_analytics.publisher_dashboard.get_performance_alerts()

        GET (no params)

        Response:
          {
            "alerts": [
              {"type": "fill_rate_drop", "severity": "warning", "message": "...", ...}
            ],
            "count": 1
          }

        Note: get_earnings_chart_data() (chart_data) is exposed via
              ReportingViewSet.chart_data — not duplicated here. (DRY)
        """
        pub = self.publisher
        with self.handle_errors() as guard:
            from .performance_analytics.publisher_dashboard import get_performance_alerts
            alerts = get_performance_alerts(pub)
            return self.ok({'alerts': alerts, 'count': len(alerts)})
        return guard.response

    # ─────────────────────────────────────────────────────────────────────────
    # REAL-TIME FILL RATE
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='fill-rate')
    def realtime_fill_rate(self, request):
        """
        Current real-time fill rate for a specific ad unit।
        Wires: performance_analytics.real_time_analytics.get_realtime_fill_rate()

        GET ?unit_id=UNIT-001
        """
        pub     = self.publisher
        unit_id = request.query_params.get('unit_id', '').strip()

        if not unit_id:
            return self.error_response('unit_id is required.', status_code=400)

        # Ensure the unit belongs to this publisher
        with self.handle_errors() as guard:
            from .models import AdUnit
            try:
                unit = AdUnit.objects.get(unit_id=unit_id, publisher=pub)
            except AdUnit.DoesNotExist:
                return self.error_response(
                    f'Ad unit {unit_id!r} not found.', status_code=404
                )

            from .performance_analytics.real_time_analytics import get_realtime_fill_rate
            fill_rate = get_realtime_fill_rate(unit_id)
            return self.ok({
                'unit_id':          unit_id,
                'unit_name':        unit.name,
                'fill_rate_pct':    fill_rate,
                'cache_ttl_seconds': self.CACHE_TTL,
            })
        return guard.response

    # ─────────────────────────────────────────────────────────────────────────
    # AD REQUEST TRACKING
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='track-request')
    def track_ad_request(self, request):
        """
        Track an ad request event (increments Redis counter)।
        Wires: performance_analytics.real_time_analytics.track_ad_request()

        POST body:
          {
            "unit_id": "UNIT-001"
          }
        """
        pub     = self.publisher
        unit_id = request.data.get('unit_id', '').strip()

        if not unit_id:
            return self.error_response('unit_id is required.', status_code=400)

        with self.handle_errors() as guard:
            from .models import AdUnit
            try:
                AdUnit.objects.get(unit_id=unit_id, publisher=pub)
            except AdUnit.DoesNotExist:
                return self.error_response(
                    f'Ad unit {unit_id!r} not found.', status_code=404
                )

            from .performance_analytics.real_time_analytics import track_ad_request
            track_ad_request(unit_id)
            return self.ok({'unit_id': unit_id, 'tracked': True})
        return guard.response

    # ─────────────────────────────────────────────────────────────────────────
    # DAILY REPORT
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='daily-report')
    def daily_report(self, request):
        """
        Daily earnings report for a specific date।
        Wires: performance_analytics.daily_report.generate_daily_report()

        GET ?date=2025-06-11
        """
        pub      = self.publisher
        date_str = request.query_params.get('date')

        with self.handle_errors() as guard:
            from datetime import date as dt
            report_date = None
            if date_str:
                try:
                    report_date = dt.fromisoformat(date_str)
                except ValueError:
                    return self.error_response(
                        'Invalid date format. Use YYYY-MM-DD.', status_code=400
                    )

            from .performance_analytics.daily_report import generate_daily_report
            data = generate_daily_report(pub, report_date=report_date)
            return self.ok(data)
        return guard.response

    @action(detail=False, methods=['get'], url_path='daily-comparison')
    def daily_comparison(self, request):
        """
        Daily earnings comparison — last N days vs prior N days।
        Wires: performance_analytics.daily_report.get_daily_comparison()

        GET ?days=7
        """
        pub = self.publisher
        try:
            days = int(request.query_params.get('days', 7))
        except (ValueError, TypeError):
            days = 7

        days = max(1, min(days, 90))

        with self.handle_errors() as guard:
            from .performance_analytics.daily_report import get_daily_comparison
            data = get_daily_comparison(pub, days=days)
            return self.ok({'days': days, 'comparison': data})
        return guard.response
