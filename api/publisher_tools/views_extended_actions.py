# publisher_tools/views_extended_actions.py
# ============================================================
# Extended @action methods for existing ViewSets.
# These are MIXIN classes — add them to the ViewSet in views.py.
#
# HOW TO APPLY:
#   1. Copy each Mixin into views.py (or import from here)
#   2. Add the Mixin to the ViewSet's MRO:
#        class AdUnitViewSet(AdUnitExtendedMixin, BaseViewSet):
#            ...
# ============================================================
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin


# ══════════════════════════════════════════════════════════════
# AdUnit extended actions
# ══════════════════════════════════════════════════════════════

class AdUnitExtendedMixin:
    """
    Add to AdUnitViewSet.
    Exposes: /ad-units/{id}/trend/  /ad-units/{id}/compare/  /ad-units/{id}/recommendations/
    """

    @action(detail=True, methods=['get'], url_path='trend')
    def trend(self, request, pk=None):
        """
        Ad unit daily performance trend।
        GET /ad-units/{id}/trend/?days=30
        """
        unit = self.get_object()
        days = int(request.query_params.get('days', 30))

        try:
            from .ad_unit_management.ad_unit_performance import get_unit_daily_trend
            trend_data = get_unit_daily_trend(unit, days=days)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'unit_id':    unit.unit_id,
            'days':       days,
            'trend':      trend_data,
        })

    @action(detail=True, methods=['get'], url_path='compare')
    def compare(self, request, pk=None):
        """
        Compare this unit against another।
        GET /ad-units/{id}/compare/?compare_with=<pk>&days=30
        """
        unit         = self.get_object()
        compare_pk   = request.query_params.get('compare_with')
        days         = int(request.query_params.get('days', 30))

        if not compare_pk:
            return self.error_response('compare_with parameter (ad unit pk) is required.', status_code=400)

        from .models import AdUnit
        try:
            other_unit = AdUnit.objects.get(
                id=compare_pk,
                publisher=unit.publisher,
            )
        except AdUnit.DoesNotExist:
            return self.error_response('Comparison ad unit not found.', status_code=404)

        try:
            from .ad_unit_management.ad_unit_performance import compare_unit_performance
            comparison = compare_unit_performance(unit, other_unit, days=days)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=comparison)

    @action(detail=True, methods=['get'], url_path='recommendations')
    def recommendations(self, request, pk=None):
        """
        Placement recommendations for this ad unit's format।
        GET /ad-units/{id}/recommendations/
        """
        unit = self.get_object()

        try:
            from .ad_unit_management.ad_unit_placement import (
                get_recommendations,
                get_viewability_benchmark,
                analyze_placement_performance,
            )
            placement_recs       = get_recommendations(unit.format)
            viewability_benchmarks = {
                pos: get_viewability_benchmark(pos)
                for pos in ['above_fold', 'below_fold', 'sidebar', 'sticky']
            }
            placements = list(unit.placements.all())
            placement_analysis = analyze_placement_performance(placements) if placements else []
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'unit_id':               unit.unit_id,
            'format':                unit.format,
            'placement_recommendations': placement_recs,
            'viewability_benchmarks':    viewability_benchmarks,
            'current_placement_analysis': placement_analysis,
        })

    @action(detail=True, methods=['get'], url_path='format-score')
    def format_score(self, request, pk=None):
        """
        Format optimization score for this unit।
        GET /ad-units/{id}/format-score/
        """
        unit = self.get_object()
        try:
            from .optimization_tools.ad_format_optimizer import get_format_optimization_score
            score = get_format_optimization_score(unit)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'unit_id': unit.unit_id,
            'format':  unit.format,
            'optimization_score': score,
            'max_score': 100,
        })


# ══════════════════════════════════════════════════════════════
# AdPlacement extended actions
# ══════════════════════════════════════════════════════════════

class AdPlacementExtendedMixin:
    """
    Add to AdPlacementViewSet.
    Exposes:
      /placements/{id}/suggest-floor/
      /placements/{id}/optimize/
      /placements/{id}/report/
      /placements/{id}/position-alternatives/
    """

    @action(detail=True, methods=['get'], url_path='suggest-floor')
    def suggest_floor(self, request, pk=None):
        """
        Floor price suggestion for this placement।
        GET /placements/{id}/suggest-floor/?days=30
        """
        placement = self.get_object()
        days      = int(request.query_params.get('days', 30))

        try:
            from .ad_placements.placement_floor_price import (
                get_effective_floor_price,
                suggest_floor_price,
            )
            current_floor = get_effective_floor_price(placement)
            suggestion    = suggest_floor_price(placement, days=days)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'placement_id':   str(placement.id),
            'current_floor':  float(current_floor),
            'suggestion':     suggestion,
        })

    @action(detail=True, methods=['post'], url_path='optimize')
    def optimize(self, request, pk=None):
        """
        Auto-optimize this placement।
        POST /placements/{id}/optimize/
        """
        placement = self.get_object()

        try:
            from .ad_placements.placement_optimizer import auto_optimize_placement
            result = auto_optimize_placement(placement)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=result, message='Placement optimized.')

    @action(detail=True, methods=['get'], url_path='report')
    def report(self, request, pk=None):
        """
        Placement performance report।
        GET /placements/{id}/report/
        """
        placement = self.get_object()
        days      = int(request.query_params.get('days', 30))

        try:
            from .ad_placements.placement_manager import get_placement_performance_summary
            from .ad_placements.placement_reporting import get_placement_efficiency_score
            summary    = get_placement_performance_summary(placement, days=days)
            efficiency = get_placement_efficiency_score(placement)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            **summary,
            'efficiency': efficiency,
        })

    @action(detail=True, methods=['get'], url_path='position-alternatives')
    def position_alternatives(self, request, pk=None):
        """
        Better position alternatives for this placement।
        GET /placements/{id}/position-alternatives/
        """
        placement = self.get_object()

        try:
            from .ad_placements.placement_position import (
                get_position_score,
                suggest_better_position,
                rank_positions_by_performance,
            )
            current_position  = getattr(placement, 'position', 'above_fold')
            inventory_type    = getattr(placement.ad_unit, 'inventory_type', 'site')
            current_score     = get_position_score(current_position)
            better_position   = suggest_better_position(current_position, inventory_type)
            ranked_positions  = rank_positions_by_performance(
                ['above_fold', 'below_fold', 'sidebar', 'sticky', 'interstitial', 'footer']
            )
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'current_position':  current_position,
            'current_score':     current_score,
            'better_position':   better_position,
            'all_positions_ranked': ranked_positions,
        })

    @action(detail=False, methods=['get'], url_path='analysis')
    def analysis(self, request):
        """
        All placements analysis for the publisher।
        GET /placements/analysis/
        """
        try:
            publisher = self.request.user.publisher_profile
        except Exception:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No publisher profile.')

        try:
            from .ad_placements.placement_optimizer import analyze_all_placements
            data = analyze_all_placements(publisher)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=data)


# ══════════════════════════════════════════════════════════════
# MediationGroup extended actions
# ══════════════════════════════════════════════════════════════

class MediationGroupExtendedMixin:
    """
    Add to MediationGroupViewSet.
    Exposes:
      /mediation-groups/{id}/bid-analysis/
      /mediation-groups/{id}/floor-recommendations/
      /mediation-groups/{id}/network-comparison/
    """

    @action(detail=True, methods=['get'], url_path='bid-analysis')
    def bid_analysis(self, request, pk=None):
        """
        Waterfall bid analysis।
        GET /mediation-groups/{id}/bid-analysis/?days=30
        """
        group = self.get_object()
        days  = int(request.query_params.get('days', 30))

        try:
            from .mediation_management.bidding_optimizer import (
                optimize_bid_timeout,
                analyze_lost_bids,
                get_bid_density_report,
            )
            timeout_opt    = optimize_bid_timeout(group)
            lost_bids      = analyze_lost_bids(group, days=days)
            bid_density    = get_bid_density_report(group)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'timeout_optimization': timeout_opt,
            'lost_bids_analysis':   lost_bids,
            'bid_density':          bid_density,
        })

    @action(detail=True, methods=['get'], url_path='floor-recommendations')
    def floor_recommendations(self, request, pk=None):
        """
        Floor price recommendations for this group's publisher।
        GET /mediation-groups/{id}/floor-recommendations/
        """
        group     = self.get_object()
        publisher = group.ad_unit.publisher

        try:
            from .mediation_management.floor_price_manager import (
                get_floor_price_recommendations,
                calculate_optimal_floor,
            )
            recommendations = get_floor_price_recommendations(publisher)
            optimal_floor   = calculate_optimal_floor(group)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'group_id':         str(group.id),
            'optimal_floor':    optimal_floor,
            'recommendations':  recommendations,
        })

    @action(detail=True, methods=['get'], url_path='network-comparison')
    def network_comparison(self, request, pk=None):
        """
        Network performance comparison for this group।
        GET /mediation-groups/{id}/network-comparison/?days=30
        """
        group = self.get_object()
        days  = int(request.query_params.get('days', 30))

        try:
            from .mediation_management.mediation_analytics import (
                get_network_comparison,
                calculate_mediation_efficiency,
            )
            comparison  = get_network_comparison(group, days=days)
            efficiency  = calculate_mediation_efficiency(group)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'network_comparison':     comparison,
            'mediation_efficiency':   efficiency,
        })


# ══════════════════════════════════════════════════════════════
# Publisher extended actions
# ══════════════════════════════════════════════════════════════

class PublisherExtendedMixin:
    """
    Add to PublisherViewSet.
    Exposes:
      /publishers/{id}/overview/
      /publishers/{id}/top-content/
      /publishers/{id}/compare/
      /publishers/{id}/profile-completion/
    """

    @action(detail=True, methods=['get'], url_path='overview')
    def overview(self, request, pk=None):
        """
        Full publisher revenue breakdown + performance overview।
        GET /publishers/{id}/overview/?period=last_30_days
        """
        publisher = self.get_object()
        period    = request.query_params.get('period', 'last_30_days')

        # Ownership check
        if not request.user.is_staff:
            try:
                if publisher != request.user.publisher_profile:
                    from rest_framework.exceptions import PermissionDenied
                    raise PermissionDenied()
            except AttributeError:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied()

        try:
            from .publisher_management.publisher_analytics import (
                get_publisher_overview,
                get_revenue_breakdown,
            )
            from .utils import get_date_range
            start_date, end_date = get_date_range(period)
            overview   = get_publisher_overview(publisher, period=period)
            breakdown  = get_revenue_breakdown(publisher, start_date, end_date)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={**overview, 'revenue_breakdown': breakdown})

    @action(detail=True, methods=['get'], url_path='top-content')
    def top_content(self, request, pk=None):
        """
        Top earning content/pages।
        GET /publishers/{id}/top-content/?days=30&limit=10
        """
        publisher = self.get_object()
        days      = int(request.query_params.get('days', 30))
        limit     = int(request.query_params.get('limit', 10))

        if not request.user.is_staff:
            try:
                if publisher != request.user.publisher_profile:
                    from rest_framework.exceptions import PermissionDenied
                    raise PermissionDenied()
            except AttributeError:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied()

        try:
            from .publisher_management.publisher_analytics import get_top_earning_content
            data = get_top_earning_content(publisher, days=days, limit=limit)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=data)

    @action(detail=True, methods=['get'], url_path='profile-completion')
    def profile_completion(self, request, pk=None):
        """
        Profile completion % + missing fields।
        GET /publishers/{id}/profile-completion/
        """
        publisher = self.get_object()

        if not request.user.is_staff:
            try:
                if publisher != request.user.publisher_profile:
                    from rest_framework.exceptions import PermissionDenied
                    raise PermissionDenied()
            except AttributeError:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied()

        try:
            from .publisher_management.publisher_profile import (
                get_publisher_profile_completion,
                get_publisher_level,
                calculate_publisher_health_score,
            )
            completion   = get_publisher_profile_completion(publisher)
            level        = get_publisher_level(publisher)
            health_score = calculate_publisher_health_score(publisher)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'profile_completion': completion,
            'publisher_level':    level,
            'health_score':       health_score,
        })
