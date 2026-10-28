# publisher_tools/views_analytics_extended.py
"""
FILE 10 of 10 — Performance Analytics Extended API
===================================================
performance_analytics/ subfolder-এর 9টি floating function expose করা হয়েছে।

Previously floating (now wired):
  get_daily_impressions, get_hourly_impressions, get_realtime_fill_rate,
  get_click_through_rate, calculate_site_rpm, track_ad_request,
  track_impression, track_click, export_report_to_csv

Register in urls.py:
  router.register(r'analytics-ext', AnalyticsExtendedViewSet, basename='analytics-ext')
"""
import datetime
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher
from .models import Site, AdUnit


class AnalyticsExtendedViewSet(BaseViewSet):
    """
    Analytics Extended API — performance_analytics/ subfolder-এর
    সব floating functions expose করে।

    Tracking (event ingestion):
      POST /analytics-ext/track-impression/   — track impression event
      POST /analytics-ext/track-click/        — track click event
      POST /analytics-ext/track-request/      — track ad request event

    Impression data:
      GET  /analytics-ext/daily-impressions/  — daily impression counts
      GET  /analytics-ext/hourly-impressions/ — hourly impression breakdown
      GET  /analytics-ext/hourly-report/      — full hourly report

    CTR & RPM:
      GET  /analytics-ext/ctr/                — CTR data
      GET  /analytics-ext/ctr-trend/          — CTR over time
      GET  /analytics-ext/ctr-anomalies/      — CTR anomaly detection
      GET  /analytics-ext/site-rpm/           — site RPM
      GET  /analytics-ext/rpm-benchmark/      — RPM vs industry benchmark

    Fill rate:
      GET  /analytics-ext/fill-by-unit/       — fill rate per ad unit
      GET  /analytics-ext/fill-by-country/    — fill rate per country
      GET  /analytics-ext/fill-issues/        — low fill rate alerts
      GET  /analytics-ext/fill-impact/        — revenue impact of low fill

    Reports:
      POST /analytics-ext/custom-report/      — custom report builder
      GET  /analytics-ext/export-csv/         — export report to CSV
      GET  /analytics-ext/best-hours/         — best performing hours
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def _get_site(self, site_id, publisher):
        try:
            return Site.objects.get(pk=site_id, publisher=publisher)
        except Site.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Site not found.')

    def _get_unit(self, unit_id, publisher):
        try:
            return AdUnit.objects.get(pk=unit_id, publisher=publisher)
        except AdUnit.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Ad unit not found.')

    # ── TRACKING (event ingestion) ─────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='track-impression')
    def track_impression(self, request):
        """
        Impression event track করে।
        POST body: {
          "unit_id":    "UNIT-001",
          "context":    { "country": "US", "device": "mobile" }
        }
        """
        unit_id = request.data.get('unit_id', '')
        context = request.data.get('context', {})
        if not unit_id:
            return self.error_response('unit_id required.', status_code=400)
        try:
            from .performance_analytics.impression_tracker import track_impression
            result = track_impression(unit_id, context)
            return self.success_response(data=result)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='track-click')
    def track_click(self, request):
        """
        Click event track করে।
        POST body: { "unit_id": "UNIT-001", "context": {} }
        """
        unit_id = request.data.get('unit_id', '')
        context = request.data.get('context', {})
        if not unit_id:
            return self.error_response('unit_id required.', status_code=400)
        try:
            from .performance_analytics.click_tracker import track_click
            result = track_click(unit_id, context)
            return self.success_response(data=result)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='track-request')
    def track_request(self, request):
        """
        Ad request event track করে।
        POST body: { "unit_id": "UNIT-001", "context": {} }
        """
        unit_id = request.data.get('unit_id', '')
        context = request.data.get('context', {})
        if not unit_id:
            return self.error_response('unit_id required.', status_code=400)
        try:
            from .performance_analytics import track_ad_request
            result = track_ad_request(unit_id, context)
            return self.success_response(data=result)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── IMPRESSION DATA ────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='daily-impressions')
    def daily_impressions(self, request):
        """
        Daily impression counts।
        GET ?date=2025-06-01
        """
        publisher = self._get_publisher()
        date_str  = request.query_params.get('date')
        try:
            report_date = (
                datetime.date.fromisoformat(date_str) if date_str
                else datetime.date.today()
            )
        except ValueError:
            return self.error_response('Invalid date. Use YYYY-MM-DD.', status_code=400)
        try:
            from .performance_analytics.daily_report import generate_daily_report
            data = generate_daily_report(publisher, report_date=report_date)
            return self.success_response(data=data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='hourly-impressions')
    def hourly_impressions(self, request):
        """
        Hourly impression breakdown for a specific unit。
        GET ?unit_id=UNIT-001
        """
        unit_id = request.query_params.get('unit_id', '')
        if not unit_id:
            return self.error_response('unit_id required.', status_code=400)
        try:
            from .performance_analytics.impression_tracker import get_hourly_impressions
            count = get_hourly_impressions(unit_id)
            return self.success_response(data={
                'unit_id':           unit_id,
                'hourly_impressions': count,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='hourly-report')
    def hourly_report(self, request):
        """
        Publisher-এর hourly report।
        GET ?date=2025-06-01
        """
        publisher = self._get_publisher()
        date_str  = request.query_params.get('date')
        try:
            report_date = (
                datetime.date.fromisoformat(date_str) if date_str
                else datetime.date.today()
            )
        except ValueError:
            return self.error_response('Invalid date. Use YYYY-MM-DD.', status_code=400)
        try:
            from .performance_analytics.hourly_report import generate_hourly_report
            data = generate_hourly_report(publisher, report_date=report_date)
            return self.success_response(data=data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='best-hours')
    def best_hours(self, request):
        """Best performing hours of day।"""
        publisher = self._get_publisher()
        days = int(request.query_params.get('days', 30))
        try:
            from .performance_analytics.hourly_report import get_best_hours
            data = get_best_hours(publisher, days=days)
            return self.success_response(data={'best_hours': data})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── CTR ────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='ctr')
    def ctr(self, request):
        """
        Click-through rate data।
        GET ?unit_id=UNIT-001
        """
        unit_id = request.query_params.get('unit_id', '')
        if not unit_id:
            return self.error_response('unit_id required.', status_code=400)
        try:
            from .performance_analytics.click_tracker import get_click_through_rate
            rate = get_click_through_rate(unit_id)
            return self.success_response(data={
                'unit_id': unit_id,
                'ctr':     rate,
                'ctr_pct': round(rate * 100, 4),
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='ctr-by-format')
    def ctr_by_format(self, request):
        """CTR breakdown by ad format।"""
        publisher = self._get_publisher()
        days      = int(request.query_params.get('days', 30))
        try:
            from .performance_analytics.CTR_analyzer import get_ctr_by_format
            data = get_ctr_by_format(publisher, days=days)
            return self.success_response(data={'formats': data})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='ctr-trend')
    def ctr_trend(self, request):
        """CTR trend over time।"""
        publisher = self._get_publisher()
        days      = int(request.query_params.get('days', 30))
        try:
            from .performance_analytics.CTR_analyzer import get_ctr_trend
            data = get_ctr_trend(publisher, days=days)
            return self.success_response(data={'trend': data})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='ctr-anomalies')
    def ctr_anomalies(self, request):
        """CTR anomaly detection।"""
        publisher = self._get_publisher()
        days      = int(request.query_params.get('days', 7))
        try:
            from .performance_analytics.CTR_analyzer import identify_ctr_anomalies
            data = identify_ctr_anomalies(publisher, days=days)
            return self.success_response(data={'anomalies': data, 'count': len(data)})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── RPM ────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='site-rpm')
    def site_rpm(self, request):
        """
        Site-level RPM (Revenue Per Mille)。
        GET ?site_id=5&days=30
        """
        publisher = self._get_publisher()
        site_id   = request.query_params.get('site_id')
        days      = int(request.query_params.get('days', 30))
        if not site_id:
            return self.error_response('site_id required.', status_code=400)
        site = self._get_site(site_id, publisher)
        try:
            from .performance_analytics import calculate_site_rpm
            data = calculate_site_rpm(site, days=days)
            return self.success_response(data=data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='rpm-benchmark')
    def rpm_benchmark(self, request):
        """
        Site RPM vs industry benchmark।
        GET ?site_id=5&days=30
        """
        publisher = self._get_publisher()
        site_id   = request.query_params.get('site_id')
        days      = int(request.query_params.get('days', 30))
        if not site_id:
            return self.error_response('site_id required.', status_code=400)
        site = self._get_site(site_id, publisher)
        try:
            from .performance_analytics.RPM_analyzer import (
                calculate_site_rpm, get_rpm_benchmarks, compare_rpm_to_benchmark
            )
            site_rpm_data = calculate_site_rpm(site, days=days)
            benchmarks    = get_rpm_benchmarks()
            rpm_value     = site_rpm_data.get('rpm', 0)
            comparison    = compare_rpm_to_benchmark(site, float(rpm_value))
            return self.success_response(data={
                'site_rpm':   site_rpm_data,
                'benchmarks': benchmarks,
                'comparison': comparison,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── FILL RATE ──────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='fill-by-unit')
    def fill_by_unit(self, request):
        """Fill rate breakdown per ad unit।"""
        publisher = self._get_publisher()
        days      = int(request.query_params.get('days', 30))
        try:
            from .performance_analytics.fill_rate_analyzer import get_fill_rate_by_unit
            data = get_fill_rate_by_unit(publisher, days=days)
            return self.success_response(data={'fill_by_unit': data})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='fill-by-country')
    def fill_by_country(self, request):
        """Fill rate breakdown per country।"""
        publisher = self._get_publisher()
        days      = int(request.query_params.get('days', 30))
        try:
            from .performance_analytics.fill_rate_analyzer import get_fill_rate_by_country
            data = get_fill_rate_by_country(publisher, days=days)
            return self.success_response(data={'fill_by_country': data})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='fill-issues')
    def fill_issues(self, request):
        """Low fill rate alerts।"""
        publisher = self._get_publisher()
        threshold = float(request.query_params.get('threshold', 50.0))
        try:
            from .performance_analytics.fill_rate_analyzer import identify_fill_rate_issues
            issues = identify_fill_rate_issues(publisher, threshold=threshold)
            return self.success_response(data={'issues': issues, 'count': len(issues)})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='fill-impact')
    def fill_impact(self, request):
        """
        Revenue impact of low fill rate।
        GET ?unit_id=5&target_fill=80
        """
        publisher      = self._get_publisher()
        unit_id        = request.query_params.get('unit_id')
        target_fill    = float(request.query_params.get('target_fill', 80.0))
        if not unit_id:
            return self.error_response('unit_id required.', status_code=400)
        unit = self._get_unit(unit_id, publisher)
        try:
            from .performance_analytics.fill_rate_analyzer import (
                calculate_revenue_impact_of_low_fill
            )
            data = calculate_revenue_impact_of_low_fill(unit, target_fill_rate=target_fill)
            return self.success_response(data=data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── CUSTOM REPORT + CSV EXPORT ─────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='custom-report')
    def custom_report(self, request):
        """
        Custom report builder।
        POST body: {
          "metrics":    ["impressions","revenue","ecpm","ctr"],
          "dimensions": ["date","country","ad_format"],
          "start_date": "2025-01-01",
          "end_date":   "2025-01-31",
          "filters":    {}
        }
        """
        publisher = self._get_publisher()
        metrics    = request.data.get('metrics',    ['impressions', 'revenue'])
        dimensions = request.data.get('dimensions', ['date'])
        start_str  = request.data.get('start_date')
        end_str    = request.data.get('end_date')
        filters    = request.data.get('filters', {})
        today = datetime.date.today()
        try:
            start = (datetime.date.fromisoformat(start_str) if start_str
                     else today - datetime.timedelta(days=30))
            end   = datetime.date.fromisoformat(end_str) if end_str else today
        except ValueError:
            return self.error_response('Invalid date format. Use YYYY-MM-DD.', status_code=400)
        try:
            from .performance_analytics.custom_report import build_custom_report
            data = build_custom_report(publisher, metrics, dimensions, start, end, filters)
            return self.success_response(data=data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='export-csv')
    def export_csv(self, request):
        """
        Report data CSV export।
        POST body: same as custom-report
        """
        publisher = self._get_publisher()
        metrics    = request.data.get('metrics',    ['impressions', 'revenue', 'ecpm'])
        dimensions = request.data.get('dimensions', ['date'])
        start_str  = request.data.get('start_date')
        end_str    = request.data.get('end_date')
        filters    = request.data.get('filters', {})
        today = datetime.date.today()
        try:
            start = (datetime.date.fromisoformat(start_str) if start_str
                     else today - datetime.timedelta(days=30))
            end   = datetime.date.fromisoformat(end_str) if end_str else today
        except ValueError:
            return self.error_response('Invalid date format. Use YYYY-MM-DD.', status_code=400)
        try:
            from .performance_analytics.custom_report import (
                build_custom_report, export_report_to_csv
            )
            from .performance_analytics import export_report_to_csv as _export
            report_data = build_custom_report(publisher, metrics, dimensions, start, end, filters)
            csv_content = export_report_to_csv(report_data)
            from django.http import HttpResponse
            response = HttpResponse(csv_content, content_type='text/csv')
            filename  = f'report_{start}_{end}.csv'
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:
            return self.error_response(str(e), status_code=503)
