# publisher_tools/views_placements_extended.py
"""
FILE 8 of 10 — Ad Placements Extended API
==========================================
ad_placements/ subfolder-এর 8টি floating function expose করা হয়েছে।

Previously floating (now wired):
  get_active_placements_for_site, get_active_placements_for_app,
  get_placement_config, get_placement_waterfall,
  get_recommended_sizes_for_position, get_size_ecpm_multiplier,
  parse_size_string, generate_placement_report

Register in urls.py:
  router.register(r'placement-tools', PlacementExtendedViewSet, basename='placement-tools')
"""
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher
from .models import AdPlacement, Site, App


class PlacementExtendedViewSet(BaseViewSet):
    """
    Ad Placements Extended API — ad_placements/ subfolder-এর
    সব floating functions expose করে।

    GET  /placement-tools/for-site/              — active placements for site
    GET  /placement-tools/for-app/               — active placements for app
    GET  /placement-tools/config/                — placement config
    GET  /placement-tools/waterfall/             — placement waterfall
    GET  /placement-tools/recommended-sizes/     — recommended ad sizes
    GET  /placement-tools/size-multiplier/       — eCPM multiplier by size
    POST /placement-tools/parse-size/            — parse size string
    GET  /placement-tools/report/                — placement report
    GET  /placement-tools/clone/                 → clone a placement
    GET  /placement-tools/position-scores/       — rank positions by revenue
    GET  /placement-tools/suggest-position/      — suggest better position
    GET  /placement-tools/optimize-all/          — analyze all placements
    POST /placement-tools/auto-optimize/         — auto-optimize a placement
    GET  /placement-tools/efficiency/            — placement efficiency scores
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    # ── ACTIVE PLACEMENTS ──────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='for-site')
    def for_site(self, request):
        """
        Site-এর সব active placements।
        GET ?site_id=5
        """
        publisher = self._get_publisher()
        site_id   = request.query_params.get('site_id')
        if not site_id:
            return self.error_response('site_id required.', status_code=400)
        try:
            site = Site.objects.get(pk=site_id, publisher=publisher)
            from .ad_placements.placement_manager import get_active_placements_for_site
            placements = get_active_placements_for_site(site)
            return self.success_response(data={
                'site_id':    site_id,
                'placements': [
                    {'pk': p.pk, 'name': p.name, 'position': getattr(p, 'position', ''),
                     'ad_format': getattr(p, 'ad_format', '')}
                    for p in placements
                ],
                'count': len(placements),
            })
        except Site.DoesNotExist:
            return self.error_response('Site not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='for-app')
    def for_app(self, request):
        """
        App-এর সব active placements।
        GET ?app_id=5
        """
        publisher = self._get_publisher()
        app_id    = request.query_params.get('app_id')
        if not app_id:
            return self.error_response('app_id required.', status_code=400)
        try:
            app = App.objects.get(pk=app_id, publisher=publisher)
            from .ad_placements.placement_manager import get_active_placements_for_app
            placements = get_active_placements_for_app(app)
            return self.success_response(data={
                'app_id':     app_id,
                'placements': [
                    {'pk': p.pk, 'name': p.name, 'ad_format': getattr(p, 'ad_format', '')}
                    for p in placements
                ],
                'count': len(placements),
            })
        except App.DoesNotExist:
            return self.error_response('App not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── PLACEMENT CONFIG + WATERFALL ───────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='config')
    def placement_config(self, request):
        """
        Placement-এর serving configuration।
        GET ?placement_id=5
        """
        publisher    = self._get_publisher()
        placement_id = request.query_params.get('placement_id')
        if not placement_id:
            return self.error_response('placement_id required.', status_code=400)
        try:
            placement = AdPlacement.objects.get(pk=placement_id, publisher=publisher)
            from .ad_placements.placement_manager import get_placement_config
            config = get_placement_config(placement)
            return self.success_response(data=config)
        except AdPlacement.DoesNotExist:
            return self.error_response('Placement not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='waterfall')
    def placement_waterfall(self, request):
        """
        Placement-এর ad network waterfall।
        GET ?placement_id=5
        """
        publisher    = self._get_publisher()
        placement_id = request.query_params.get('placement_id')
        if not placement_id:
            return self.error_response('placement_id required.', status_code=400)
        try:
            placement = AdPlacement.objects.get(pk=placement_id, publisher=publisher)
            from .ad_placements.placement_waterfall import get_placement_waterfall
            waterfall = get_placement_waterfall(placement)
            return self.success_response(data={
                'placement_id': placement_id,
                'waterfall':    waterfall,
                'count':        len(waterfall),
            })
        except AdPlacement.DoesNotExist:
            return self.error_response('Placement not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── SIZE TOOLS ─────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='recommended-sizes')
    def recommended_sizes(self, request):
        """
        Position-এর জন্য recommended ad sizes।
        GET ?position=top_of_page | sidebar | in_article | ...
        """
        position = request.query_params.get('position', 'top_of_page')
        try:
            from .ad_placements.placement_size import get_recommended_sizes_for_position
            sizes = get_recommended_sizes_for_position(position)
            return self.success_response(data={
                'position': position,
                'sizes':    sizes,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='size-multiplier')
    def size_multiplier(self, request):
        """
        Ad size-এর eCPM multiplier।
        GET ?size=300x250
        Multiple sizes: GET ?size=300x250,728x90,320x50
        """
        size_param = request.query_params.get('size', '')
        if not size_param:
            return self.error_response('size required (e.g. 300x250).', status_code=400)
        sizes = [s.strip() for s in size_param.split(',')]
        try:
            from .ad_placements.placement_size import get_size_ecpm_multiplier
            result = {s: get_size_ecpm_multiplier(s) for s in sizes}
            return self.success_response(data={'multipliers': result})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='parse-size')
    def parse_size(self, request):
        """
        Size string parse করে width/height বের করে।
        POST body: { "size": "300x250" }
        """
        size_str = request.data.get('size', '')
        if not size_str:
            return self.error_response('size required.', status_code=400)
        try:
            from .ad_placements.placement_size import parse_size_string, get_responsive_config
            width, height = parse_size_string(size_str)
            responsive    = get_responsive_config(width, height)
            return self.success_response(data={
                'size':          size_str,
                'width':         width,
                'height':        height,
                'aspect_ratio':  round(width / height, 3) if height else None,
                'responsive':    responsive,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── POSITION TOOLS ─────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='position-scores')
    def position_scores(self, request):
        """
        Positions ranked by historical revenue performance।
        GET ?positions=top_of_page,sidebar,in_article
        """
        pos_param = request.query_params.get('positions', '')
        positions = [p.strip() for p in pos_param.split(',')] if pos_param else [
            'top_of_page', 'sidebar', 'in_article', 'below_fold',
            'sticky_footer', 'interstitial',
        ]
        try:
            from .ad_placements.placement_position import rank_positions_by_performance
            ranked = rank_positions_by_performance(positions)
            return self.success_response(data={'ranked_positions': ranked})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='suggest-position')
    def suggest_position(self, request):
        """
        Better position suggestion।
        GET ?current_position=below_fold&inventory_type=site
        """
        current  = request.query_params.get('current_position', 'below_fold')
        inv_type = request.query_params.get('inventory_type', 'site')
        try:
            from .ad_placements.placement_position import (
                suggest_better_position, get_position_score, get_viewability_benchmark
            )
            suggested    = suggest_better_position(current, inv_type)
            curr_score   = get_position_score(current)
            sug_score    = get_position_score(suggested)
            curr_view    = get_viewability_benchmark(current)
            sug_view     = get_viewability_benchmark(suggested)
            return self.success_response(data={
                'current_position':   current,
                'suggested_position': suggested,
                'current_score':      curr_score,
                'suggested_score':    sug_score,
                'viewability_improvement': sug_view - curr_view,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── REPORTING & OPTIMIZATION ───────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='report')
    def placement_report(self, request):
        """
        Publisher-এর সব placements-এর report।
        GET ?start=2025-01-01&end=2025-01-31
        """
        import datetime
        publisher = self._get_publisher()
        today     = datetime.date.today()
        start_str = request.query_params.get('start')
        end_str   = request.query_params.get('end')
        try:
            start = datetime.date.fromisoformat(start_str) if start_str else (
                today.replace(day=1)
            )
            end   = datetime.date.fromisoformat(end_str) if end_str else today
        except ValueError:
            return self.error_response('Invalid date format. Use YYYY-MM-DD.', status_code=400)
        try:
            from .ad_placements.placement_reporting import generate_placement_report
            data = generate_placement_report(publisher, start, end)
            return self.success_response(data=data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='optimize-all')
    def optimize_all(self, request):
        """Publisher-এর সব placements-এর optimization analysis।"""
        publisher = self._get_publisher()
        try:
            from .ad_placements.placement_optimizer import analyze_all_placements
            data = analyze_all_placements(publisher)
            return self.success_response(data={'analysis': data, 'count': len(data)})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='auto-optimize')
    def auto_optimize(self, request):
        """
        Single placement auto-optimize।
        POST body: { "placement_id": 5 }
        """
        publisher    = self._get_publisher()
        placement_id = request.data.get('placement_id')
        if not placement_id:
            return self.error_response('placement_id required.', status_code=400)
        try:
            placement = AdPlacement.objects.get(pk=placement_id, publisher=publisher)
            from .ad_placements.placement_optimizer import auto_optimize_placement
            result = auto_optimize_placement(placement)
            return self.success_response(data=result)
        except AdPlacement.DoesNotExist:
            return self.error_response('Placement not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='efficiency')
    def efficiency(self, request):
        """
        Placement efficiency scores।
        GET ?placement_id=5 (single) or omit for all publisher placements
        """
        publisher    = self._get_publisher()
        placement_id = request.query_params.get('placement_id')
        try:
            from .ad_placements.placement_reporting import get_placement_efficiency_score
            if placement_id:
                placement = AdPlacement.objects.get(pk=placement_id, publisher=publisher)
                score     = get_placement_efficiency_score(placement)
                return self.success_response(data=score)
            else:
                placements = AdPlacement.objects.filter(publisher=publisher)
                scores     = [get_placement_efficiency_score(p) for p in placements]
                return self.success_response(data={
                    'scores': scores, 'count': len(scores)
                })
        except AdPlacement.DoesNotExist:
            return self.error_response('Placement not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)
