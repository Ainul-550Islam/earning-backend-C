# publisher_tools/views_analytics_advanced.py
"""
FILE 4 of 10 — Performance Analytics Advanced API
==================================================
performance_analytics/ remaining 9 floating functions exposed.

Previously floating (now wired):
  linear_regression, get_seasonal_adjustment, calculate_revenue_growth,
  forecast_monthly_revenue, get_period_revenue, get_ecpm_optimization_suggestions,
  get_realtime_fill_rate, get_daily_impressions, change_pct

Register in urls.py:
  router.register(r'analytics-adv', AnalyticsAdvancedViewSet, basename='analytics-adv')
"""
import datetime
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher
from .models import Site, AdUnit


class AnalyticsAdvancedViewSet(BaseViewSet):
    """
    Analytics Advanced API.

    Revenue Forecasting:
      GET  /analytics-adv/revenue-forecast/         — monthly revenue forecast
      GET  /analytics-adv/revenue-growth/           — revenue growth calculation
      GET  /analytics-adv/period-revenue/           — revenue for custom period
      GET  /analytics-adv/seasonal-adjustment/      — seasonal adjustment factors

    eCPM Optimization:
      GET  /analytics-adv/ecpm-suggestions/         — eCPM improvement suggestions
      GET  /analytics-adv/ecpm-by-country/          — eCPM breakdown by country
      GET  /analytics-adv/ecpm-by-format/           — eCPM breakdown by ad format
      GET  /analytics-adv/ecpm-trend/               — eCPM historical trend

    Real-time:
      GET  /analytics-adv/realtime-fill/            — real-time fill rate
      GET  /analytics-adv/realtime-impressions/     — live impression count
      GET  /analytics-adv/realtime-ecpm/            — real-time eCPM

    Publisher Dashboard:
      GET  /analytics-adv/dashboard-kpis/           — key performance indicators
      GET  /analytics-adv/revenue-vs-goal/          — revenue vs monthly goal
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    # ── REVENUE FORECASTING ────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='revenue-forecast')
    def revenue_forecast(self, request):
        """
        Monthly revenue forecast।
        GET ?months=3&include_seasonal=true
        """
        publisher        = self._get_publisher()
        months           = int(request.query_params.get('months', 3))
        include_seasonal = request.query_params.get('include_seasonal', 'true').lower() == 'true'
        if not 1 <= months <= 12:
            return self.error_response('months must be 1–12.', status_code=400)
        try:
            from .performance_analytics.revenue_forecast import forecast_monthly_revenue
            forecast = forecast_monthly_revenue(
                publisher, months=months, include_seasonal=include_seasonal
            )
            return self.success_response(data={
                'months':           months,
                'include_seasonal': include_seasonal,
                'forecast':         forecast,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='revenue-growth')
    def revenue_growth(self, request):
        """
        Revenue growth % vs previous period।
        GET ?period=30d | 90d | ytd
        """
        publisher = self._get_publisher()
        period    = request.query_params.get('period', '30d')
        try:
            from .performance_analytics.revenue_tracker import calculate_revenue_growth
            data = calculate_revenue_growth(publisher, period=period)
            return self.success_response(data=data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='period-revenue')
    def period_revenue(self, request):
        """
        Revenue for a custom date range।
        GET ?start=2025-01-01&end=2025-01-31
        """
        publisher = self._get_publisher()
        start_str = request.query_params.get('start')
        end_str   = request.query_params.get('end')
        try:
            today = datetime.date.today()
            start = datetime.date.fromisoformat(start_str) if start_str else (
                today.replace(day=1)
            )
            end = datetime.date.fromisoformat(end_str) if end_str else today
        except ValueError:
            return self.error_response('Invalid date format. Use YYYY-MM-DD.', status_code=400)
        try:
            from .performance_analytics.revenue_tracker import get_period_revenue
            data = get_period_revenue(publisher, start, end)
            return self.success_response(data=data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='seasonal-adjustment')
    def seasonal_adjustment(self, request):
        """
        Seasonal adjustment factors by month।
        """
        publisher = self._get_publisher()
        try:
            from .performance_analytics.revenue_forecast import get_seasonal_adjustment
            factors = get_seasonal_adjustment(publisher)
            return self.success_response(data={'seasonal_factors': factors})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='forecast-accuracy')
    def forecast_accuracy(self, request):
        """Previous forecast vs actual revenue comparison।"""
        publisher = self._get_publisher()
        try:
            from .performance_analytics.revenue_tracker import forecast_monthly_revenue
            data = forecast_monthly_revenue(publisher)
            return self.success_response(data=data if isinstance(data, dict) else {
                'forecast': str(data)
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── ECPM OPTIMIZATION ──────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='ecpm-suggestions')
    def ecpm_suggestions(self, request):
        """
        eCPM improvement suggestions।
        GET ?unit_id=5 (specific unit) or omit for publisher-wide
        """
        publisher = self._get_publisher()
        unit_id   = request.query_params.get('unit_id')
        try:
            from .performance_analytics.ecpm_analyzer import get_ecpm_optimization_suggestions
            if unit_id:
                try:
                    ad_unit = AdUnit.objects.get(pk=unit_id, publisher=publisher)
                    data    = get_ecpm_optimization_suggestions(ad_unit)
                except AdUnit.DoesNotExist:
                    return self.error_response('Ad unit not found.', status_code=404)
            else:
                data = get_ecpm_optimization_suggestions(publisher)
            return self.success_response(data=data if isinstance(data, (dict, list))
                                          else {'suggestions': data})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='ecpm-by-country')
    def ecpm_by_country(self, request):
        """eCPM breakdown by country।"""
        publisher = self._get_publisher()
        days      = int(request.query_params.get('days', 30))
        limit     = int(request.query_params.get('limit', 20))
        try:
            from .performance_analytics.ecpm_analyzer import get_ecpm_by_country
            data = get_ecpm_by_country(publisher, days=days, limit=limit)
            return self.success_response(data={'countries': data})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='ecpm-by-format')
    def ecpm_by_format(self, request):
        """eCPM breakdown by ad format।"""
        publisher = self._get_publisher()
        days      = int(request.query_params.get('days', 30))
        try:
            from .performance_analytics.ecpm_analyzer import get_ecpm_by_format
            data = get_ecpm_by_format(publisher, days=days)
            return self.success_response(data={'formats': data})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='ecpm-trend')
    def ecpm_trend(self, request):
        """eCPM historical trend।"""
        publisher = self._get_publisher()
        days      = int(request.query_params.get('days', 30))
        try:
            from .performance_analytics.ecpm_analyzer import get_ecpm_trend
            data = get_ecpm_trend(publisher, days=days)
            return self.success_response(data={'trend': data})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── REAL-TIME ──────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='realtime-fill')
    def realtime_fill(self, request):
        """
        Real-time fill rate।
        GET ?unit_id=UNIT-001
        """
        unit_id = request.query_params.get('unit_id', '')
        if not unit_id:
            return self.error_response('unit_id required.', status_code=400)
        try:
            from .performance_analytics import get_realtime_fill_rate
            rate = get_realtime_fill_rate(unit_id)
            return self.success_response(data={
                'unit_id':  unit_id,
                'fill_rate': rate,
                'fill_pct':  round(float(rate) * 100, 2) if rate else 0,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='realtime-impressions')
    def realtime_impressions(self, request):
        """
        Live impression count (last N minutes)。
        GET ?unit_id=UNIT-001&minutes=60
        """
        unit_id = request.query_params.get('unit_id', '')
        minutes = int(request.query_params.get('minutes', 60))
        if not unit_id:
            return self.error_response('unit_id required.', status_code=400)
        try:
            from .performance_analytics.impression_tracker import get_hourly_impressions
            count = get_hourly_impressions(unit_id)
            return self.success_response(data={
                'unit_id':    unit_id,
                'window_min': minutes,
                'impressions': count,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── PUBLISHER DASHBOARD KPIs ───────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='dashboard-kpis')
    def dashboard_kpis(self, request):
        """
        Publisher dashboard key performance indicators।
        """
        publisher = self._get_publisher()
        try:
            from .performance_analytics.publisher_dashboard import get_publisher_kpis
            data = get_publisher_kpis(publisher)
            return self.success_response(data=data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='revenue-vs-goal')
    def revenue_vs_goal(self, request):
        """
        Current month revenue vs goal।
        """
        publisher = self._get_publisher()
        try:
            from .performance_analytics.revenue_tracker import get_period_revenue
            today      = datetime.date.today()
            month_start = today.replace(day=1)
            data        = get_period_revenue(publisher, month_start, today)
            return self.success_response(data=data if isinstance(data, dict) else {
                'period_revenue': str(data)
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)
