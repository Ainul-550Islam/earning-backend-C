# publisher_tools/views_optimization.py
# ============================================================
# NEW FILE — OptimizationViewSet
# optimization_tools/ subfolder-এর সব logic expose করে।
#
# Register in urls.py:
#   router.register(r'optimizations', OptimizationViewSet, basename='optimization')
# ============================================================
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher


class OptimizationViewSet(BaseViewSet):
    """
    Revenue Optimization Tools।
    optimization_tools/ subfolder-এর সব functions API হিসেবে expose করা হয়েছে।

    Actions:
      yield_analysis     — floor price optimization + revenue opportunity
      format             — ad format recommendations + comparison
      geo                — geo-specific eCPM optimization
      device             — device-specific floor prices + best formats
      refresh            — optimal refresh rate for placements
      viewability        — viewability improvement recommendations
      latency            — waterfall timeout optimization
      frequency          — frequency cap recommendations
      placement          — full placement optimization score
      audience           — audience targeting value + demographics
      time               — peak hours + day-of-week analysis
    """
    permission_classes = [IsAuthenticated, IsPublisher]
    http_method_names  = ['get', 'head', 'options']

    def _get_publisher(self):
        try:
            return self.request.user.publisher_profile
        except Exception:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No active publisher profile.')

    # ── YIELD / REVENUE OPPORTUNITY ───────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='yield')
    def yield_analysis(self, request):
        """
        Floor price optimization + revenue opportunity।
        GET /optimizations/yield/
        """
        publisher = self._get_publisher()
        try:
            from .optimization_tools.yield_optimizer import (
                optimize_floor_prices,
                calculate_revenue_opportunity,
            )
            floor_suggestions    = optimize_floor_prices(publisher)
            revenue_opportunity  = calculate_revenue_opportunity(publisher)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'floor_price_suggestions': floor_suggestions,
            'revenue_opportunity':     revenue_opportunity,
        })

    # ── AD FORMAT ─────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='format')
    def format(self, request):
        """
        Ad format recommendations।
        GET /optimizations/format/?site_id=SITE123456&days=30
        """
        publisher = self._get_publisher()
        site_id   = request.query_params.get('site_id')
        days      = int(request.query_params.get('days', 30))

        try:
            from .optimization_tools.ad_format_optimizer import (
                recommend_formats_for_site,
                compare_formats,
            )
            comparison = compare_formats(publisher, days=days)
            recommendations = []
            if site_id:
                from .models import Site
                site = Site.objects.filter(
                    site_id=site_id, publisher=publisher
                ).first()
                if site:
                    recommendations = recommend_formats_for_site(site)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'format_comparison':   comparison,
            'recommendations':     recommendations,
        })

    # ── GEO ───────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='geo')
    def geo(self, request):
        """
        Geo-specific eCPM optimization।
        GET /optimizations/geo/?days=30
        """
        publisher = self._get_publisher()
        days      = int(request.query_params.get('days', 30))

        try:
            from .optimization_tools.geo_optimizer import (
                get_geo_optimization_recommendations,
                get_ecpm_by_country_benchmark,
            )
            recommendations = get_geo_optimization_recommendations(publisher, days=days)
            benchmarks      = get_ecpm_by_country_benchmark()
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'recommendations': recommendations,
            'benchmarks':      benchmarks,
        })

    # ── DEVICE ────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='device')
    def device(self, request):
        """
        Device-specific floor prices + best ad formats।
        GET /optimizations/device/?ad_unit_id=<pk>&days=30
        """
        publisher   = self._get_publisher()
        ad_unit_id  = request.query_params.get('ad_unit_id')
        days        = int(request.query_params.get('days', 30))

        try:
            from .optimization_tools.device_optimizer import (
                get_device_performance,
                recommend_device_specific_floor_prices,
                get_best_format_for_device,
            )
            performance  = get_device_performance(publisher, days=days)
            floor_recs   = {}
            format_recs  = {
                'mobile':  get_best_format_for_device('mobile'),
                'desktop': get_best_format_for_device('desktop'),
                'tablet':  get_best_format_for_device('tablet'),
            }
            if ad_unit_id:
                from .models import AdUnit
                unit = AdUnit.objects.filter(
                    id=ad_unit_id, publisher=publisher
                ).first()
                if unit:
                    floor_recs = recommend_device_specific_floor_prices(unit)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'device_performance':       performance,
            'floor_price_by_device':    floor_recs,
            'best_formats_by_device':   format_recs,
        })

    # ── REFRESH RATE ──────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='refresh')
    def refresh(self, request):
        """
        Optimal ad refresh rate।
        GET /optimizations/refresh/?placement_id=<pk>&days=30
        """
        publisher    = self._get_publisher()
        placement_id = request.query_params.get('placement_id')
        days         = int(request.query_params.get('days', 30))

        if not placement_id:
            return self.error_response('placement_id is required.', status_code=400)

        from .models import AdPlacement
        placement = AdPlacement.objects.filter(
            id=placement_id,
            ad_unit__publisher=publisher,
        ).first()
        if not placement:
            return self.error_response('Placement not found.', status_code=404)

        try:
            from .optimization_tools.ad_refresh_optimizer import (
                calculate_optimal_refresh_rate,
                estimate_refresh_revenue_lift,
            )
            result = calculate_optimal_refresh_rate(placement, days=days)
            current_rate     = getattr(placement.ad_unit, 'refresh_interval', 30)
            recommended_rate = result.get('recommended_refresh_rate', current_rate)
            lift = estimate_refresh_revenue_lift(
                current_rate,
                recommended_rate,
                result.get('avg_daily_revenue', 0.0),
            )
            result['estimated_revenue_lift'] = lift
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=result)

    # ── VIEWABILITY ───────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='viewability')
    def viewability(self, request):
        """
        Viewability improvement recommendations।
        GET /optimizations/viewability/?site_id=SITE123456
        """
        publisher = self._get_publisher()
        site_id   = request.query_params.get('site_id')

        if not site_id:
            return self.error_response('site_id is required.', status_code=400)

        from .models import Site
        site = Site.objects.filter(
            site_id=site_id, publisher=publisher
        ).first()
        if not site:
            return self.error_response('Site not found.', status_code=404)

        try:
            from .optimization_tools.viewability_optimizer import (
                get_viewability_recommendations,
                calculate_viewability_impact_on_ecpm,
            )
            recommendations = get_viewability_recommendations(site)
            # Calculate revenue impact at current viewability
            current_viewability = float(getattr(site, 'viewability_rate', 65.0))
            current_ecpm        = float(site.ad_units.filter(
                status='active'
            ).aggregate(
                avg=__import__('django.db.models', fromlist=['Avg']).Avg('avg_ecpm')
            ).get('avg') or 2.0)
            impact = calculate_viewability_impact_on_ecpm(current_viewability, current_ecpm)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'current_viewability_pct': current_viewability,
            'recommendations':         recommendations,
            'ecpm_impact':             impact,
        })

    # ── LATENCY ───────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='latency')
    def latency(self, request):
        """
        Waterfall timeout optimization।
        GET /optimizations/latency/?group_id=<pk>
        """
        publisher = self._get_publisher()
        group_id  = request.query_params.get('group_id')

        if not group_id:
            return self.error_response('group_id is required.', status_code=400)

        from .models import MediationGroup
        group = MediationGroup.objects.filter(
            id=group_id,
            ad_unit__publisher=publisher,
        ).first()
        if not group:
            return self.error_response('Mediation group not found.', status_code=404)

        try:
            from .optimization_tools.latency_optimizer import (
                get_latency_recommendations,
                estimate_revenue_impact_of_latency,
                classify_latency,
            )
            recommendations = get_latency_recommendations(group)
            avg_latency_ms  = int(request.query_params.get('avg_latency_ms', 500))
            latency_class   = classify_latency(avg_latency_ms)
            avg_ecpm        = float(group.ad_unit.avg_ecpm or 2.0)
            revenue_impact  = estimate_revenue_impact_of_latency(avg_latency_ms, avg_ecpm)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'avg_latency_ms':   avg_latency_ms,
            'latency_class':    latency_class,
            'recommendations':  recommendations,
            'revenue_impact':   revenue_impact,
        })

    # ── FREQUENCY CAP ─────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='frequency')
    def frequency(self, request):
        """
        Frequency cap recommendations।
        GET /optimizations/frequency/?ad_format=banner
        """
        publisher  = self._get_publisher()
        ad_format  = request.query_params.get('ad_format', 'banner')

        try:
            from .optimization_tools.frequency_capper import (
                get_recommended_frequency_cap,
                analyze_frequency_caps,
                estimate_ctr_improvement,
            )
            recommendation  = get_recommended_frequency_cap(ad_format)
            analysis        = analyze_frequency_caps(publisher)
            current_freq    = int(request.query_params.get('current_frequency', 5))
            recommended_freq = recommendation.get('recommended_frequency', current_freq)
            ctr_improvement = estimate_ctr_improvement(current_freq, recommended_freq)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'ad_format':         ad_format,
            'recommendation':    recommendation,
            'publisher_analysis':analysis,
            'ctr_improvement_pct': ctr_improvement,
        })

    # ── PLACEMENT SCORE ───────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='placement-score')
    def placement_score(self, request):
        """
        Full placement optimization score।
        GET /optimizations/placement-score/
        """
        publisher = self._get_publisher()

        try:
            from .optimization_tools.placement_optimizer import (
                run_placement_optimization,
                score_all_placements,
            )
            scores          = score_all_placements(publisher)
            optimization    = run_placement_optimization(publisher)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'placement_scores':  scores,
            'optimization_plan': optimization,
        })

    # ── AUDIENCE ──────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='audience')
    def audience(self, request):
        """
        Audience targeting value + demographics।
        GET /optimizations/audience/?site_id=SITE123456
        """
        publisher = self._get_publisher()
        site_id   = request.query_params.get('site_id')

        try:
            from .optimization_tools.audience_optimizer import (
                get_audience_value_recommendations,
                estimate_audience_targeting_revenue_lift,
                analyze_audience_demographics,
            )
            publisher_recs = get_audience_value_recommendations(publisher)
            avg_ecpm       = float(request.query_params.get('current_ecpm', 2.0))
            revenue_lift   = estimate_audience_targeting_revenue_lift(publisher, avg_ecpm)
            demographics   = {}
            if site_id:
                from .models import Site
                site = Site.objects.filter(
                    site_id=site_id, publisher=publisher
                ).first()
                if site:
                    demographics = analyze_audience_demographics(site)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'targeting_recommendations': publisher_recs,
            'revenue_lift_estimate':     revenue_lift,
            'demographics':              demographics,
        })

    # ── TIME ──────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='time')
    def time(self, request):
        """
        Peak hours + day-of-week performance analysis।
        GET /optimizations/time/?ad_unit_id=<pk>&days=28
        """
        publisher   = self._get_publisher()
        ad_unit_id  = request.query_params.get('ad_unit_id')
        days        = int(request.query_params.get('days', 28))

        try:
            from .optimization_tools.time_optimizer import (
                get_peak_hours,
                get_day_of_week_analysis,
                get_optimal_schedule,
            )
            peak_hours   = get_peak_hours()
            day_analysis = get_day_of_week_analysis(publisher, days=days)
            schedule     = {}
            if ad_unit_id:
                from .models import AdUnit
                unit = AdUnit.objects.filter(
                    id=ad_unit_id, publisher=publisher
                ).first()
                if unit:
                    schedule = get_optimal_schedule(publisher, unit)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'peak_hours':           peak_hours,
            'day_of_week_analysis': day_analysis,
            'optimal_schedule':     schedule,
        })

    # ── AD LOAD ───────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='ad-load')
    def ad_load(self, request):
        """
        Ad load optimization — optimal unit count per page।
        GET /optimizations/ad-load/?site_id=SITE123456
        """
        publisher = self._get_publisher()
        site_id   = request.query_params.get('site_id')

        if not site_id:
            return self.error_response('site_id is required.', status_code=400)

        from .models import Site
        site = Site.objects.filter(
            site_id=site_id, publisher=publisher
        ).first()
        if not site:
            return self.error_response('Site not found.', status_code=404)

        try:
            from .optimization_tools.ad_load_optimizer import (
                analyze_ad_load,
                get_optimal_ad_unit_count,
            )
            analysis      = analyze_ad_load(site)
            category      = getattr(site, 'category', 'news')
            optimal_count = get_optimal_ad_unit_count(
                site_category=category,
                page_type=request.query_params.get('page_type', 'article'),
            )
            analysis['optimal_unit_count'] = optimal_count
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=analysis)
