# publisher_tools/views_adunit_extended.py
"""
FILE 9 of 10 — Ad Unit Management Extended API
===============================================
ad_unit_management/ subfolder-এর 7টি floating function expose করা হয়েছে।

Previously floating (now wired):
  get_unit_performance_report, get_unit_daily_trend,
  compare_unit_performance, get_recommendations,
  get_viewability_benchmark, analyze_placement_performance,
  apply_targeting_rules

Register in urls.py:
  router.register(r'ad-unit-tools', AdUnitExtendedViewSet, basename='adunit-tools')
"""
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher
from .models import AdUnit, AdPlacement


class AdUnitExtendedViewSet(BaseViewSet):
    """
    Ad Unit Management Extended API।

    GET  /ad-unit-tools/performance-report/ — full performance report
    GET  /ad-unit-tools/daily-trend/        — daily trend data
    GET  /ad-unit-tools/compare/            — compare two units
    GET  /ad-unit-tools/recommendations/    — format placement recommendations
    GET  /ad-unit-tools/viewability/        — viewability benchmark by position
    GET  /ad-unit-tools/placement-analysis/ — analyze placement performance
    POST /ad-unit-tools/apply-targeting/    — apply targeting rules (simulation)
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def _get_unit(self, unit_id, publisher):
        try:
            return AdUnit.objects.get(pk=unit_id, publisher=publisher)
        except AdUnit.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Ad unit not found.')

    # ── PERFORMANCE REPORT ─────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='performance-report')
    def performance_report(self, request):
        """
        Ad unit-এর full performance report।
        GET ?unit_id=5&days=30
        """
        publisher = self._get_publisher()
        unit_id   = request.query_params.get('unit_id')
        days      = int(request.query_params.get('days', 30))
        if not unit_id:
            return self.error_response('unit_id required.', status_code=400)
        unit = self._get_unit(unit_id, publisher)
        try:
            from .ad_unit_management.ad_unit_performance import get_unit_performance_report
            data = get_unit_performance_report(unit, days=days)
            return self.success_response(data=data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='daily-trend')
    def daily_trend(self, request):
        """
        Day-by-day trend data for charts。
        GET ?unit_id=5&days=30
        """
        publisher = self._get_publisher()
        unit_id   = request.query_params.get('unit_id')
        days      = int(request.query_params.get('days', 30))
        if not unit_id:
            return self.error_response('unit_id required.', status_code=400)
        unit = self._get_unit(unit_id, publisher)
        try:
            from .ad_unit_management.ad_unit_performance import get_unit_daily_trend
            trend = get_unit_daily_trend(unit, days=days)
            return self.success_response(data={
                'unit_id': unit_id,
                'days':    days,
                'trend':   trend,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── COMPARE ────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='compare')
    def compare(self, request):
        """
        দুটি ad unit-এর side-by-side comparison।
        GET ?unit_a=5&unit_b=8&days=30
        """
        publisher = self._get_publisher()
        unit_a_id = request.query_params.get('unit_a')
        unit_b_id = request.query_params.get('unit_b')
        days      = int(request.query_params.get('days', 30))
        if not unit_a_id or not unit_b_id:
            return self.error_response('unit_a and unit_b required.', status_code=400)
        unit_a = self._get_unit(unit_a_id, publisher)
        unit_b = self._get_unit(unit_b_id, publisher)
        try:
            from .ad_unit_management.ad_unit_performance import compare_unit_performance
            data = compare_unit_performance(unit_a, unit_b, days=days)
            return self.success_response(data=data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── RECOMMENDATIONS ────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='recommendations')
    def recommendations(self, request):
        """
        Ad format-এর জন্য placement recommendations।
        GET ?format=banner | interstitial | rewarded | native
        """
        ad_format = request.query_params.get('format', 'banner')
        try:
            from .ad_unit_management.ad_unit_placement import get_recommendations
            recs = get_recommendations(ad_format)
            return self.success_response(data={
                'format':          ad_format,
                'recommendations': recs,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='viewability')
    def viewability_benchmark(self, request):
        """
        Position-এর viewability benchmark %।
        GET ?position=top_of_page | sidebar | in_article
        Multiple: GET ?position=top_of_page,sidebar,in_article
        """
        pos_param = request.query_params.get('position', 'top_of_page')
        positions = [p.strip() for p in pos_param.split(',')]
        try:
            from .ad_unit_management.ad_unit_placement import get_viewability_benchmark
            result = {p: get_viewability_benchmark(p) for p in positions}
            return self.success_response(data={'benchmarks': result})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── PLACEMENT ANALYSIS ─────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='placement-analysis')
    def placement_analysis(self, request):
        """
        Ad unit-এর সব placements-এর performance analysis।
        GET ?unit_id=5
        """
        publisher = self._get_publisher()
        unit_id   = request.query_params.get('unit_id')
        if not unit_id:
            return self.error_response('unit_id required.', status_code=400)
        unit = self._get_unit(unit_id, publisher)
        try:
            placements = AdPlacement.objects.filter(
                ad_unit=unit, publisher=publisher
            )
            from .ad_unit_management.ad_unit_placement import analyze_placement_performance
            analysis = analyze_placement_performance(list(placements))
            return self.success_response(data={
                'unit_id':  unit_id,
                'analysis': analysis,
                'count':    len(analysis),
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── TARGETING RULES ────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='apply-targeting')
    def apply_targeting(self, request):
        """
        Targeting rules simulation — request context-এ ad unit show হবে কিনা।
        POST body: {
          "unit_id": 5,
          "context": {
            "country": "US",
            "device":  "mobile",
            "os":      "ios",
            "browser": "safari",
            "language":"en"
          }
        }
        """
        publisher = self._get_publisher()
        unit_id   = request.data.get('unit_id')
        context   = request.data.get('context', {})
        if not unit_id:
            return self.error_response('unit_id required.', status_code=400)
        unit = self._get_unit(unit_id, publisher)
        try:
            from .ad_unit_management.ad_unit_targeting import apply_targeting_rules
            eligible = apply_targeting_rules(unit, context)
            return self.success_response(data={
                'unit_id':  unit_id,
                'context':  context,
                'eligible': eligible,
                'decision': 'serve' if eligible else 'skip',
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)
