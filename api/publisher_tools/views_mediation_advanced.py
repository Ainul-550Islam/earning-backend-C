# publisher_tools/views_mediation_advanced.py
"""
FILE 10 of 10 — Mediation Management Advanced API
==================================================
mediation_management/ remaining floating functions exposed.
Previously floating: compare_strategies, get_demand_partner_health,
  add_demand_partner, remove_demand_partner, get_ad_source_fill_rate,
  get_ad_source_ecpm, get_hybrid_strategy_recommendation

Register in urls.py:
  router.register(r'mediation-adv', MediationAdvancedViewSet, basename='mediation-adv')
"""
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher, IsAdminOrPublisher
from .models import MediationGroup


class MediationAdvancedViewSet(BaseViewSet):
    """
    Mediation Advanced API.

    Hybrid mediation:
      GET  /mediation-adv/strategy-comparison/   — compare cascade vs bidding
      GET  /mediation-adv/strategy-recommendation/ — recommended strategy
      POST /mediation-adv/switch-strategy/        — switch mediation strategy

    Demand partners:
      GET  /mediation-adv/demand-partners/        — list demand partners
      POST /mediation-adv/add-demand-partner/     — add demand partner
      POST /mediation-adv/remove-demand-partner/  — remove demand partner
      GET  /mediation-adv/partner-health/         — demand partner health

    Ad sources:
      GET  /mediation-adv/ad-source-fill/         — ad source fill rates
      GET  /mediation-adv/ad-source-ecpm/         — ad source eCPM
      GET  /mediation-adv/source-ranking/         — rank ad sources by performance
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def _get_group(self, group_id, publisher):
        try:
            return MediationGroup.objects.get(pk=group_id, publisher=publisher)
        except MediationGroup.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Mediation group not found.')

    # ── HYBRID MEDIATION ───────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='strategy-comparison')
    def strategy_comparison(self, request):
        """
        Cascade vs bidding strategy comparison for a mediation group.
        GET ?group_id=5&days=30
        """
        publisher = self._get_publisher()
        group_id  = request.query_params.get('group_id')
        days      = int(request.query_params.get('days', 30))
        if not group_id:
            return self.error_response('group_id required.', status_code=400)
        group = self._get_group(group_id, publisher)
        try:
            from .mediation_management.hybrid_mediation import compare_strategies
            result = compare_strategies(group, days=days)
            return self.success_response(data=result if isinstance(result, dict) else {
                'comparison': result
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='strategy-recommendation')
    def strategy_recommendation(self, request):
        """
        AI-recommended mediation strategy based on historical performance.
        GET ?group_id=5
        """
        publisher = self._get_publisher()
        group_id  = request.query_params.get('group_id')
        if not group_id:
            return self.error_response('group_id required.', status_code=400)
        group = self._get_group(group_id, publisher)
        try:
            from .mediation_management.hybrid_mediation import get_hybrid_strategy_recommendation
            result = get_hybrid_strategy_recommendation(group)
            return self.success_response(data=result if isinstance(result, dict) else {
                'recommended_strategy': result
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='switch-strategy')
    def switch_strategy(self, request):
        """
        Switch mediation strategy for a group.
        POST body: { "group_id": 5, "strategy": "cascade" | "bidding" | "hybrid" }
        """
        publisher = self._get_publisher()
        group_id  = request.data.get('group_id')
        strategy  = request.data.get('strategy', '')
        if not group_id or not strategy:
            return self.error_response('group_id and strategy required.', status_code=400)
        if strategy not in ('cascade', 'bidding', 'hybrid'):
            return self.error_response(
                'strategy must be cascade, bidding, or hybrid.', status_code=400
            )
        group = self._get_group(group_id, publisher)
        try:
            group.strategy = strategy
            group.save(update_fields=['strategy', 'updated_at'])
            return self.success_response(data={
                'group_id': group_id,
                'strategy': strategy,
                'switched': True,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── DEMAND PARTNERS ────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='demand-partners')
    def demand_partners(self, request):
        """
        All demand partners for publisher's mediation groups.
        GET ?group_id=5 (optional filter)
        """
        publisher = self._get_publisher()
        group_id  = request.query_params.get('group_id')
        try:
            from .mediation_management.demand_partner_manager import DemandPartner
            qs = DemandPartner.objects.filter(publisher=publisher)
            if group_id:
                qs = qs.filter(mediation_group_id=group_id)
            return self.success_response(data={
                'demand_partners': [
                    {
                        'pk':          p.pk,
                        'network':     getattr(p, 'network_name', ''),
                        'status':      getattr(p, 'status', ''),
                        'is_active':   getattr(p, 'is_active', True),
                        'priority':    getattr(p, 'priority', 0),
                        'floor_price': str(getattr(p, 'floor_price', 0)),
                    }
                    for p in qs
                ],
                'count': qs.count(),
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='add-demand-partner')
    def add_demand_partner(self, request):
        """
        Add demand partner to mediation group.
        POST body: { "group_id": 5, "network": "admob", "floor_price": "0.50" }
        """
        publisher  = self._get_publisher()
        group_id   = request.data.get('group_id')
        network    = request.data.get('network', '')
        floor_str  = request.data.get('floor_price', '0.00')
        if not group_id or not network:
            return self.error_response('group_id and network required.', status_code=400)
        group = self._get_group(group_id, publisher)
        try:
            from .mediation_management.demand_partner_manager import add_demand_partner
            partner = add_demand_partner(group, network, floor_price=floor_str)
            return self.success_response(
                data={'pk': getattr(partner, 'pk', None), 'network': network},
                message=f'{network} added to mediation group.',
                status_code=201,
            )
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='remove-demand-partner')
    def remove_demand_partner(self, request):
        """
        Remove demand partner.
        POST body: { "partner_id": 42 }
        """
        publisher  = self._get_publisher()
        partner_id = request.data.get('partner_id')
        if not partner_id:
            return self.error_response('partner_id required.', status_code=400)
        try:
            from .mediation_management.demand_partner_manager import DemandPartner
            partner = DemandPartner.objects.get(
                pk=partner_id, publisher=publisher
            )
            partner.delete()
            return self.success_response(
                data={'partner_id': partner_id, 'removed': True}
            )
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='partner-health')
    def partner_health(self, request):
        """
        Demand partner health — fill rate, latency, error rate.
        GET ?group_id=5&days=7
        """
        publisher = self._get_publisher()
        group_id  = request.query_params.get('group_id')
        days      = int(request.query_params.get('days', 7))
        if not group_id:
            return self.error_response('group_id required.', status_code=400)
        group = self._get_group(group_id, publisher)
        try:
            from .mediation_management.demand_partner_manager import get_demand_partner_health
            data = get_demand_partner_health(group, days=days)
            return self.success_response(data=data if isinstance(data, (dict, list))
                                          else {'health': data})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── AD SOURCES ─────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='ad-source-fill')
    def ad_source_fill(self, request):
        """
        Fill rate per ad source.
        GET ?group_id=5&days=30
        """
        publisher = self._get_publisher()
        group_id  = request.query_params.get('group_id')
        days      = int(request.query_params.get('days', 30))
        if not group_id:
            return self.error_response('group_id required.', status_code=400)
        group = self._get_group(group_id, publisher)
        try:
            from .mediation_management.ad_source_manager import get_ad_source_fill_rate
            data = get_ad_source_fill_rate(group, days=days)
            return self.success_response(data={'fill_rates': data})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='ad-source-ecpm')
    def ad_source_ecpm(self, request):
        """
        eCPM per ad source.
        GET ?group_id=5&days=30
        """
        publisher = self._get_publisher()
        group_id  = request.query_params.get('group_id')
        days      = int(request.query_params.get('days', 30))
        if not group_id:
            return self.error_response('group_id required.', status_code=400)
        group = self._get_group(group_id, publisher)
        try:
            from .mediation_management.ad_source_manager import get_ad_source_ecpm
            data = get_ad_source_ecpm(group, days=days)
            return self.success_response(data={'ecpm_by_source': data})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='source-ranking')
    def source_ranking(self, request):
        """
        Rank ad sources by combined performance score.
        GET ?group_id=5&days=30&metric=revenue | ecpm | fill_rate
        """
        publisher = self._get_publisher()
        group_id  = request.query_params.get('group_id')
        days      = int(request.query_params.get('days', 30))
        metric    = request.query_params.get('metric', 'revenue')
        if not group_id:
            return self.error_response('group_id required.', status_code=400)
        group = self._get_group(group_id, publisher)
        try:
            from .mediation_management.ad_source_manager import rank_ad_sources
            ranked = rank_ad_sources(group, days=days, metric=metric)
            return self.success_response(data={
                'group_id': group_id,
                'metric':   metric,
                'ranked':   ranked,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)
