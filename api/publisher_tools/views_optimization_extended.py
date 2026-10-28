# publisher_tools/views_optimization_extended.py
"""
FILE 7 of 10 — Optimization Tools Extended API
===============================================
optimization_tools/ subfolder-এর 6টি floating function expose করা হয়েছে।

Previously floating (now wired):
  analyze_time_of_day_performance, analyze_timeout_settings,
  calculate_viewability_lift, get_ad_load_optimization,
  get_best_serving_windows, suggest_waterfall_optimization

Register in urls.py:
  router.register(r'optimizations-ext', OptimizationExtendedViewSet, basename='opt-ext')
"""
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher
from .models import Site, AdUnit


class OptimizationExtendedViewSet(BaseViewSet):
    """
    Optimization Extended API — optimization_tools/ subfolder-এর
    সব floating functions expose করে।

    GET  /optimizations-ext/time-of-day/         — time-of-day performance
    GET  /optimizations-ext/serving-windows/     — best serving windows
    GET  /optimizations-ext/day-of-week/         — day of week analysis
    GET  /optimizations-ext/viewability-lift/    — viewability impact on eCPM
    GET  /optimizations-ext/viewability-recs/    — viewability recommendations
    GET  /optimizations-ext/ad-load/             — ad density analysis
    GET  /optimizations-ext/optimal-unit-count/  — optimal units per page
    POST /optimizations-ext/timeout-analysis/    — timeout settings analysis
    GET  /optimizations-ext/waterfall-suggest/   — waterfall optimization suggestions
    GET  /optimizations-ext/peak-hours/          — platform peak hours
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def _get_site(self, site_id, publisher):
        try:
            return Site.objects.get(pk=site_id, publisher=publisher)
        except Site.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Site not found.')

    # ── TIME OF DAY ────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='time-of-day')
    def time_of_day(self, request):
        """
        Hour-by-hour performance analysis।
        GET ?ad_unit_id=5&days=30
        """
        publisher  = self._get_publisher()
        ad_unit_id = request.query_params.get('ad_unit_id')
        days       = int(request.query_params.get('days', 30))
        ad_unit    = None
        if ad_unit_id:
            try:
                ad_unit = AdUnit.objects.get(pk=ad_unit_id, publisher=publisher)
            except AdUnit.DoesNotExist:
                return self.error_response('Ad unit not found.', status_code=404)
        try:
            from .optimization_tools import analyze_time_of_day_performance
            data = analyze_time_of_day_performance(publisher, ad_unit=ad_unit, days=days)
            return self.success_response(data=data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='serving-windows')
    def serving_windows(self, request):
        """
        Publisher-এর জন্য best serving time windows।
        GET ?ad_unit_id=5
        """
        publisher  = self._get_publisher()
        ad_unit_id = request.query_params.get('ad_unit_id')
        ad_unit    = None
        if ad_unit_id:
            try:
                ad_unit = AdUnit.objects.get(pk=ad_unit_id, publisher=publisher)
            except AdUnit.DoesNotExist:
                return self.error_response('Ad unit not found.', status_code=404)
        try:
            from .optimization_tools import get_best_serving_windows
            windows = get_best_serving_windows(publisher, ad_unit=ad_unit)
            return self.success_response(data={'windows': windows})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='peak-hours')
    def peak_hours(self, request):
        """Platform-wide peak hours (publisher-agnostic)।"""
        try:
            from .optimization_tools.time_optimizer import get_peak_hours
            hours = get_peak_hours()
            return self.success_response(data={'peak_hours': hours})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='day-of-week')
    def day_of_week(self, request):
        """Day-of-week performance analysis।"""
        publisher = self._get_publisher()
        days      = int(request.query_params.get('days', 28))
        try:
            from .optimization_tools.time_optimizer import get_day_of_week_analysis
            data = get_day_of_week_analysis(publisher, days=days)
            return self.success_response(data={'analysis': data})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── VIEWABILITY ────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='viewability-lift')
    def viewability_lift(self, request):
        """
        Viewability improvement-এর eCPM lift calculation।
        GET ?viewability_pct=65&current_ecpm=2.50
        """
        try:
            viewability_pct = float(request.query_params.get('viewability_pct', 65))
            current_ecpm    = float(request.query_params.get('current_ecpm', 2.0))
        except ValueError:
            return self.error_response('Invalid numeric parameters.', status_code=400)
        try:
            from .optimization_tools import calculate_viewability_lift
            result = calculate_viewability_lift(viewability_pct, current_ecpm)
            return self.success_response(data=result)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='viewability-recs')
    def viewability_recs(self, request):
        """
        Site-specific viewability improvement recommendations।
        GET ?site_id=5
        """
        publisher = self._get_publisher()
        site_id   = request.query_params.get('site_id')
        if not site_id:
            return self.error_response('site_id required.', status_code=400)
        site = self._get_site(site_id, publisher)
        try:
            from .optimization_tools.viewability_optimizer import get_viewability_recommendations
            recs = get_viewability_recommendations(site)
            return self.success_response(data={'site_id': site_id, 'recommendations': recs})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── AD LOAD / DENSITY ──────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='ad-load')
    def ad_load(self, request):
        """
        Ad density analysis — কতগুলো ad unit দেওয়া উচিত।
        GET ?site_id=5
        """
        publisher = self._get_publisher()
        site_id   = request.query_params.get('site_id')
        if not site_id:
            return self.error_response('site_id required.', status_code=400)
        site = self._get_site(site_id, publisher)
        try:
            from .optimization_tools import get_ad_load_optimization
            data = get_ad_load_optimization(site)
            return self.success_response(data=data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='optimal-unit-count')
    def optimal_unit_count(self, request):
        """
        Site category + page type-এর জন্য optimal ad unit count।
        GET ?category=news&page_type=article
        """
        category  = request.query_params.get('category', 'general')
        page_type = request.query_params.get('page_type', 'article')
        try:
            from .optimization_tools.ad_load_optimizer import get_optimal_ad_unit_count
            count = get_optimal_ad_unit_count(category, page_type)
            return self.success_response(data={
                'category':     category,
                'page_type':    page_type,
                'optimal_count': count,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── TIMEOUT ANALYSIS ───────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='timeout-analysis')
    def timeout_analysis(self, request):
        """
        Bid timeout settings analyze ও optimize করে।
        POST body: { "ad_unit_id": 5 }
        """
        publisher  = self._get_publisher()
        ad_unit_id = request.data.get('ad_unit_id')
        if not ad_unit_id:
            return self.error_response('ad_unit_id required.', status_code=400)
        try:
            ad_unit = AdUnit.objects.get(pk=ad_unit_id, publisher=publisher)
            from .optimization_tools import analyze_timeout_settings
            result = analyze_timeout_settings(ad_unit)
            return self.success_response(data=result)
        except AdUnit.DoesNotExist:
            return self.error_response('Ad unit not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── WATERFALL SUGGESTIONS ──────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='waterfall-suggest')
    def waterfall_suggest(self, request):
        """
        AI-driven waterfall optimization suggestions।
        GET ?ad_unit_id=5
        """
        publisher  = self._get_publisher()
        ad_unit_id = request.query_params.get('ad_unit_id')
        if not ad_unit_id:
            return self.error_response('ad_unit_id required.', status_code=400)
        try:
            ad_unit = AdUnit.objects.get(pk=ad_unit_id, publisher=publisher)
            from .optimization_tools import suggest_waterfall_optimization
            suggestions = suggest_waterfall_optimization(ad_unit)
            return self.success_response(data={
                'ad_unit_id':  ad_unit_id,
                'suggestions': suggestions,
            })
        except AdUnit.DoesNotExist:
            return self.error_response('Ad unit not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)
