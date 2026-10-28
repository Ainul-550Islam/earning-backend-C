# publisher_tools/views_mediation_extended.py
"""
FILE 4 of 10 — Mediation Management Extended API
=================================================
mediation_management/ subfolder-এর 9টি floating function expose করা হয়েছে।

Previously floating (now wired):
  create_default_waterfall, reorder_by_ecpm, get_waterfall_stats,
  apply_floor_price_update, bulk_update_floor_prices,
  calculate_network_priority_score, get_optimal_priorities,
  apply_optimal_priorities, schedule_auto_optimization,
  get_optimization_opportunities, calculate_bid_win_rate

Register in urls.py:
  router.register(r'mediation-extended', MediationExtendedViewSet, basename='mediation-ext')
"""
from decimal import Decimal
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher, IsAdminOrPublisher
from .models import MediationGroup, AdUnit


class MediationExtendedViewSet(BaseViewSet):
    """
    Mediation Extended API — mediation_management/ subfolder-এর
    সব floating functions expose করে।

    Waterfall management:
      POST /mediation-extended/create-default/       — create default waterfall
      POST /mediation-extended/{pk}/reorder-by-ecpm/ — reorder items by eCPM
      GET  /mediation-extended/{pk}/waterfall-stats/ — waterfall performance stats
      POST /mediation-extended/{pk}/validate/         — validate waterfall config

    Floor price:
      POST /mediation-extended/{pk}/apply-floor/     — apply floor price to ad unit
      POST /mediation-extended/bulk-floor-update/    — bulk update publisher floors

    Priority optimization:
      GET  /mediation-extended/{pk}/priority-scores/ — per-network priority scores
      GET  /mediation-extended/{pk}/optimal-order/   — AI-suggested priority order
      POST /mediation-extended/{pk}/apply-optimal/   — apply optimal priorities
      POST /mediation-extended/{pk}/schedule-auto/   — schedule auto-optimization

    Bidding analysis:
      GET  /mediation-extended/{pk}/bid-win-rate/    — network bid win rates
      GET  /mediation-extended/{pk}/bid-density/     — bid density report
      GET  /mediation-extended/{pk}/lost-bids/       — lost bid analysis
      POST /mediation-extended/{pk}/optimize-timeout/ — optimize bid timeout

    Publisher-level:
      GET  /mediation-extended/opportunities/        — all optimization opportunities
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def _get_group(self, pk):
        publisher = self._get_publisher()
        try:
            return MediationGroup.objects.get(pk=pk, publisher=publisher)
        except MediationGroup.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Mediation group not found.')

    # ── WATERFALL MANAGEMENT ───────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='create-default')
    def create_default(self, request):
        """
        Ad unit-এর জন্য default waterfall তৈরি করে।
        POST body: {
          "ad_unit_id": 5,
          "networks": ["admob", "applovin", "facebook_an"]  ← optional
        }
        """
        publisher  = self._get_publisher()
        ad_unit_id = request.data.get('ad_unit_id')
        networks   = request.data.get('networks')
        if not ad_unit_id:
            return self.error_response('ad_unit_id required.', status_code=400)
        try:
            ad_unit = AdUnit.objects.get(pk=ad_unit_id, publisher=publisher)
        except AdUnit.DoesNotExist:
            return self.error_response('Ad unit not found.', status_code=404)
        try:
            from .mediation_management.waterfall_manager import create_default_waterfall
            items = create_default_waterfall(ad_unit, networks=networks)
            return self.success_response(
                data={
                    'ad_unit_id':    ad_unit_id,
                    'created_items': len(items),
                    'networks':      [getattr(i, 'network_name', str(i)) for i in items],
                },
                message='Default waterfall created.',
                status_code=201,
            )
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=True, methods=['post'], url_path='reorder-by-ecpm')
    def reorder_by_ecpm(self, request, pk=None):
        """
        Historical eCPM data-র ভিত্তিতে waterfall items reorder করে।
        """
        group = self._get_group(pk)
        try:
            from .mediation_management.waterfall_manager import reorder_by_ecpm
            reordered = reorder_by_ecpm(group)
            return self.success_response(data={
                'group_id':   group.pk,
                'new_order':  [
                    {'pk': i.pk, 'network': getattr(i, 'network_name', ''), 'priority': i.priority}
                    for i in reordered
                ],
            }, message='Waterfall reordered by eCPM.')
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=True, methods=['get'], url_path='waterfall-stats')
    def waterfall_stats(self, request, pk=None):
        """
        Waterfall performance stats — fill rate, win rates, revenue share।
        """
        group = self._get_group(pk)
        try:
            from .mediation_management.waterfall_manager import get_waterfall_stats
            stats = get_waterfall_stats(group)
            return self.success_response(data=stats)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=True, methods=['post'], url_path='validate')
    def validate(self, request, pk=None):
        """
        Waterfall configuration validate করে।
        """
        group = self._get_group(pk)
        try:
            from .mediation_management.waterfall_manager import validate_waterfall
            result = validate_waterfall(group)
            return self.success_response(data=result)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── FLOOR PRICE ────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='apply-floor')
    def apply_floor(self, request):
        """
        নির্দিষ্ট ad unit-এ নতুন floor price apply করে।
        POST body: { "ad_unit_id": 5, "floor_price": "0.75" }
        """
        publisher  = self._get_publisher()
        ad_unit_id = request.data.get('ad_unit_id')
        floor_str  = request.data.get('floor_price')
        if not ad_unit_id or floor_str is None:
            return self.error_response('ad_unit_id and floor_price required.', status_code=400)
        try:
            new_floor = Decimal(str(floor_str))
            if new_floor < 0:
                return self.error_response('floor_price must be ≥ 0.', status_code=400)
        except Exception:
            return self.error_response('Invalid floor_price value.', status_code=400)
        try:
            ad_unit = AdUnit.objects.get(pk=ad_unit_id, publisher=publisher)
            from .mediation_management.floor_price_manager import apply_floor_price_update
            success = apply_floor_price_update(ad_unit, new_floor)
            return self.success_response(data={
                'ad_unit_id': ad_unit_id,
                'new_floor':  str(new_floor),
                'applied':    success,
            })
        except AdUnit.DoesNotExist:
            return self.error_response('Ad unit not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='bulk-floor-update')
    def bulk_floor_update(self, request):
        """
        Publisher-এর সব ad units-এ strategy-based floor update।
        POST body: { "strategy": "conservative" | "aggressive" | "balanced" }
        """
        publisher = self._get_publisher()
        strategy  = request.data.get('strategy', 'conservative')
        if strategy not in ('conservative', 'aggressive', 'balanced'):
            return self.error_response(
                'strategy must be: conservative, aggressive, or balanced.', status_code=400
            )
        try:
            from .mediation_management.floor_price_manager import bulk_update_floor_prices
            result = bulk_update_floor_prices(publisher, strategy=strategy)
            return self.success_response(data=result, message='Bulk floor update complete.')
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='floor-recommendations')
    def floor_recommendations(self, request):
        """
        Publisher-এর ad units-এর জন্য floor price recommendations।
        """
        publisher = self._get_publisher()
        try:
            from .mediation_management.floor_price_manager import get_floor_price_recommendations
            recs = get_floor_price_recommendations(publisher)
            return self.success_response(data={'recommendations': recs, 'count': len(recs)})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── PRIORITY OPTIMIZATION ──────────────────────────────────────────────────

    @action(detail=True, methods=['get'], url_path='priority-scores')
    def priority_scores(self, request, pk=None):
        """
        প্রতিটি network-এর calculated priority score।
        Higher score = should be higher in waterfall।
        """
        group = self._get_group(pk)
        try:
            from .mediation_management.network_priority import calculate_network_priority_score
            items = group.waterfall_items.select_related().all()
            scores = [
                {
                    'item_pk':      item.pk,
                    'network':      getattr(item, 'network_name', ''),
                    'priority':     item.priority,
                    'score':        calculate_network_priority_score(item),
                }
                for item in items
            ]
            scores.sort(key=lambda x: x['score'], reverse=True)
            return self.success_response(data={'group_id': group.pk, 'scores': scores})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=True, methods=['get'], url_path='optimal-order')
    def optimal_order(self, request, pk=None):
        """
        AI-suggested optimal priority order (read-only, doesn't apply)。
        """
        group = self._get_group(pk)
        try:
            from .mediation_management.network_priority import get_optimal_priorities
            suggested = get_optimal_priorities(group)
            current   = list(
                group.waterfall_items.order_by('priority')
                     .values('pk', 'priority')
            )
            return self.success_response(data={
                'group_id':        group.pk,
                'current_order':   current,
                'suggested_order': suggested,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=True, methods=['post'], url_path='apply-optimal')
    def apply_optimal(self, request, pk=None):
        """
        Suggested optimal priorities を実際に apply する。
        """
        group = self._get_group(pk)
        try:
            from .mediation_management.network_priority import apply_optimal_priorities
            updated = apply_optimal_priorities(group)
            return self.success_response(
                data={'group_id': group.pk, 'items_updated': updated},
                message='Optimal priorities applied.'
            )
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='schedule-auto')
    def schedule_auto(self, request):
        """
        Publisher-এর জন্য auto-optimization schedule করে।
        POST body: { "interval_hours": 24 }
        """
        publisher      = self._get_publisher()
        interval_hours = int(request.data.get('interval_hours', 24))
        if not (1 <= interval_hours <= 168):
            return self.error_response('interval_hours must be 1–168.', status_code=400)
        try:
            from .mediation_management.mediation_optimizer import schedule_auto_optimization
            schedule_auto_optimization(publisher, interval_hours=interval_hours)
            return self.success_response(data={
                'publisher_id':  publisher.publisher_id,
                'interval_hours': interval_hours,
                'scheduled':     True,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='opportunities')
    def opportunities(self, request):
        """
        Publisher-এর সব mediation optimization opportunities।
        """
        publisher = self._get_publisher()
        try:
            from .mediation_management.mediation_optimizer import get_optimization_opportunities
            opps = get_optimization_opportunities(publisher)
            return self.success_response(data={'opportunities': opps, 'count': len(opps)})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── BIDDING ANALYSIS ───────────────────────────────────────────────────────

    @action(detail=True, methods=['get'], url_path='bid-win-rate')
    def bid_win_rate(self, request, pk=None):
        """
        প্রতিটি network-এর bid win rate analysis।
        GET ?days=30
        """
        group = self._get_group(pk)
        days  = int(request.query_params.get('days', 30))
        try:
            from .mediation_management import calculate_bid_win_rate
            data = calculate_bid_win_rate(group, days=days)
            return self.success_response(data=data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=True, methods=['get'], url_path='bid-density')
    def bid_density(self, request, pk=None):
        """Bid density report — কোন price range-এ কত bids আসছে।"""
        group = self._get_group(pk)
        try:
            from .mediation_management.bidding_optimizer import get_bid_density_report
            data = get_bid_density_report(group)
            return self.success_response(data=data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=True, methods=['get'], url_path='lost-bids')
    def lost_bids(self, request, pk=None):
        """Lost bid analysis — কোন bids floor price-এর কারণে miss হচ্ছে।"""
        group = self._get_group(pk)
        days  = int(request.query_params.get('days', 30))
        try:
            from .mediation_management.bidding_optimizer import analyze_lost_bids
            data = analyze_lost_bids(group, days=days)
            return self.success_response(data=data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=True, methods=['post'], url_path='optimize-timeout')
    def optimize_timeout(self, request, pk=None):
        """
        Bid timeout settings optimize করে।
        """
        group = self._get_group(pk)
        try:
            from .mediation_management.bidding_optimizer import optimize_bid_timeout
            result = optimize_bid_timeout(group)
            return self.success_response(data=result)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=True, methods=['get'], url_path='underperforming')
    def underperforming(self, request, pk=None):
        """
        Underperforming networks চিহ্নিত করে।
        GET ?min_impressions=1000
        """
        group          = self._get_group(pk)
        min_impressions = int(request.query_params.get('min_impressions', 1000))
        try:
            from .mediation_management.network_priority import detect_underperforming_networks
            result = detect_underperforming_networks(group, min_impressions=min_impressions)
            return self.success_response(data={'underperforming': result, 'count': len(result)})
        except Exception as e:
            return self.error_response(str(e), status_code=503)
