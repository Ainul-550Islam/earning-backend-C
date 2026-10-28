# publisher_tools/views_mediation_full.py
# Exposes mediation_management/ subfolder logic via DRF.
# Register: router.register(r'mediation-tools', MediationToolsViewSet, basename='mediation-tool')

from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher


class MediationToolsViewSet(BaseViewSet):
    """
    Mediation Tools API.
    mediation_management/ subfolder expose করা হয়েছে।

    Endpoints:
      GET  /mediation-tools/performance/      — mediation group performance
      GET  /mediation-tools/network-compare/  — network ROI comparison
      GET  /mediation-tools/waterfall-report/ — waterfall performance report
      GET  /mediation-tools/efficiency/       — mediation efficiency score
      GET  /mediation-tools/hybrid-config/    — header bidding + waterfall config
      GET  /mediation-tools/floor-recs/       — floor price recommendations
      POST /mediation-tools/full-optimize/    — full optimization run
      GET  /mediation-tools/bid-analysis/     — bid density + lost bid analysis
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def _get_publisher(self):
        try:
            return self.request.user.publisher_profile
        except Exception:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No active publisher profile.')

    def _get_group(self, group_id, publisher):
        from .models import MediationGroup
        return MediationGroup.objects.filter(
            id=group_id, ad_unit__publisher=publisher
        ).first()

    @action(detail=False, methods=['get'], url_path='performance')
    def performance(self, request):
        """
        Mediation group performance.
        GET /mediation-tools/performance/?group_id=<pk>&days=30
        """
        publisher = self._get_publisher()
        group_id  = request.query_params.get('group_id')
        days      = int(request.query_params.get('days', 30))

        if not group_id:
            return self.error_response('group_id is required.', status_code=400)
        group = self._get_group(group_id, publisher)
        if not group:
            return self.error_response('Mediation group not found.', status_code=404)

        try:
            from .mediation_management import get_mediation_performance
            data = get_mediation_performance(group, days=days)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=data)

    @action(detail=False, methods=['get'], url_path='network-compare')
    def network_compare(self, request):
        """
        Network ROI comparison for the publisher.
        GET /mediation-tools/network-compare/?days=30
        """
        publisher = self._get_publisher()
        days      = int(request.query_params.get('days', 30))

        try:
            from .mediation_management import get_network_comparison, generate_network_roi_report
            comparison = get_network_comparison(publisher, days=days)
            roi_report = generate_network_roi_report(publisher, days=days)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'comparison': comparison,
            'roi_report': roi_report,
        })

    @action(detail=False, methods=['get'], url_path='waterfall-report')
    def waterfall_report(self, request):
        """
        Waterfall performance report.
        GET /mediation-tools/waterfall-report/?start_date=2025-01-01&end_date=2025-01-31
        """
        publisher = self._get_publisher()
        from .serializers import DateRangeSerializer
        s = DateRangeSerializer(data=request.query_params)
        if not s.is_valid():
            return self.error_response(s.errors, status_code=400)

        try:
            from .mediation_management import generate_waterfall_report
            data = generate_waterfall_report(
                publisher,
                s.validated_data['start_date'],
                s.validated_data['end_date'],
            )
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=data)

    @action(detail=False, methods=['get'], url_path='efficiency')
    def efficiency(self, request):
        """
        Mediation efficiency score for a group.
        GET /mediation-tools/efficiency/?group_id=<pk>
        """
        publisher = self._get_publisher()
        group_id  = request.query_params.get('group_id')

        if not group_id:
            return self.error_response('group_id is required.', status_code=400)
        group = self._get_group(group_id, publisher)
        if not group:
            return self.error_response('Mediation group not found.', status_code=404)

        try:
            from .mediation_management import calculate_mediation_efficiency
            score = calculate_mediation_efficiency(group)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'group_id':   str(group.id),
            'efficiency': score,
            'grade':      'A' if score >= 85 else 'B' if score >= 70 else 'C' if score >= 55 else 'D',
        })

    @action(detail=False, methods=['get'], url_path='hybrid-config')
    def hybrid_config(self, request):
        """
        Header bidding + waterfall hybrid config.
        GET /mediation-tools/hybrid-config/?group_id=<pk>
        """
        publisher = self._get_publisher()
        group_id  = request.query_params.get('group_id')

        if not group_id:
            return self.error_response('group_id is required.', status_code=400)
        group = self._get_group(group_id, publisher)
        if not group:
            return self.error_response('Mediation group not found.', status_code=404)

        try:
            from .mediation_management import get_hybrid_ad_response, get_bidder_configurations
            bidder_configs = get_bidder_configurations(group)
            context        = {'publisher_id': publisher.publisher_id}
            hybrid_recs    = get_hybrid_ad_response(group, context)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'bidder_configs': bidder_configs,
            'hybrid_recs':    hybrid_recs,
        })

    @action(detail=False, methods=['get'], url_path='floor-recs')
    def floor_recs(self, request):
        """
        Floor price recommendations.
        GET /mediation-tools/floor-recs/?group_id=<pk>
        """
        publisher = self._get_publisher()
        group_id  = request.query_params.get('group_id')

        if not group_id:
            return self.error_response('group_id is required.', status_code=400)
        group = self._get_group(group_id, publisher)
        if not group:
            return self.error_response('Mediation group not found.', status_code=404)

        try:
            from .mediation_management import get_floor_price_recommendations, calculate_optimal_floor
            recommendations = get_floor_price_recommendations(publisher)
            optimal         = calculate_optimal_floor(group)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'group_id':       str(group.id),
            'optimal_floor':  optimal,
            'recommendations': recommendations,
        })

    @action(detail=False, methods=['post'], url_path='full-optimize')
    def full_optimize(self, request):
        """
        Run full mediation optimization for all auto-optimize groups.
        POST /mediation-tools/full-optimize/
        """
        publisher = self._get_publisher()

        try:
            from .mediation_management import run_full_optimization, get_optimization_opportunities
            from .models import MediationGroup
            groups     = MediationGroup.objects.filter(
                ad_unit__publisher=publisher, auto_optimize=True, is_active=True
            )
            results    = [run_full_optimization(g) for g in groups]
            opportunities = get_optimization_opportunities(publisher)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'optimized_groups': len(results),
            'opportunities':    opportunities,
        }, message=f'{len(results)} groups optimized.')

    @action(detail=False, methods=['get'], url_path='bid-analysis')
    def bid_analysis(self, request):
        """
        Bid density + lost bid analysis.
        GET /mediation-tools/bid-analysis/?group_id=<pk>&days=30
        """
        publisher = self._get_publisher()
        group_id  = request.query_params.get('group_id')
        days      = int(request.query_params.get('days', 30))

        if not group_id:
            return self.error_response('group_id is required.', status_code=400)
        group = self._get_group(group_id, publisher)
        if not group:
            return self.error_response('Mediation group not found.', status_code=404)

        try:
            from .mediation_management import (
                analyze_lost_bids, get_bid_density_report, optimize_bid_timeout
            )
            lost_bids  = analyze_lost_bids(group, days=days)
            density    = get_bid_density_report(group)
            timeout_rec = optimize_bid_timeout(group)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'lost_bids':    lost_bids,
            'bid_density':  density,
            'timeout_rec':  timeout_rec,
        })
