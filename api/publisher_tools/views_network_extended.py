# publisher_tools/views_network_extended.py
"""
FILE 2 of 10 — Ad Network Integration Extended API
===================================================
ad_network_integration/ subfolder-এর 25টি floating item expose করা হয়েছে।

Previously floating (now wired):
  get_admob_config, get_applovin_config, get_facebook_an_config,
  get_ironsource_config, get_unity_ads_config, get_google_ad_manager_config,
  get_prebid_config, get_amazon_publisher_config,
  20 NETWORK_CONFIG_MAP keys (admob, applovin, facebook_an, etc.)

Register in urls.py:
  router.register(r'ad-networks', AdNetworkExtendedViewSet, basename='ad-network')
"""
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher, IsAdminOrPublisher


# ── Network metadata map (not requiring DB calls) ─────────────────────────────
NETWORK_META = {
    'admob':             {'name': 'Google AdMob',            'type': 'mobile',  'formats': ['banner','interstitial','rewarded','native']},
    'applovin':          {'name': 'AppLovin MAX',            'type': 'mobile',  'formats': ['banner','interstitial','rewarded','mrec']},
    'facebook_an':       {'name': 'Meta Audience Network',   'type': 'mobile',  'formats': ['banner','interstitial','rewarded','native']},
    'ironsource':        {'name': 'IronSource',              'type': 'mobile',  'formats': ['interstitial','rewarded','banner','offerwall']},
    'unity_ads':         {'name': 'Unity Ads',               'type': 'mobile',  'formats': ['interstitial','rewarded','banner']},
    'google_ad_manager': {'name': 'Google Ad Manager (GAM)', 'type': 'web',     'formats': ['display','video','native','rich_media']},
    'prebid':            {'name': 'Prebid.js',               'type': 'web',     'formats': ['display','video','native']},
    'amazon_publisher':  {'name': 'Amazon Publisher Services','type': 'web',    'formats': ['display','video']},
    'pubmatic':          {'name': 'PubMatic',                'type': 'web',     'formats': ['display','video','native']},
    'rubicon':           {'name': 'Magnite (Rubicon)',        'type': 'web',     'formats': ['display','video']},
    'index_exchange':    {'name': 'Index Exchange',          'type': 'web',     'formats': ['display','video','native']},
    'openx':             {'name': 'OpenX',                   'type': 'web',     'formats': ['display','video']},
    'sovrn':             {'name': 'Sovrn',                   'type': 'web',     'formats': ['display','video']},
    'vungle':            {'name': 'Vungle (Liftoff)',        'type': 'mobile',  'formats': ['interstitial','rewarded','native']},
    'tapjoy':            {'name': 'Tapjoy',                  'type': 'mobile',  'formats': ['rewarded','interstitial','offerwall']},
    'chartboost':        {'name': 'Chartboost',              'type': 'mobile',  'formats': ['interstitial','rewarded']},
    'fyber':             {'name': 'Digital Turbine (Fyber)', 'type': 'mobile',  'formats': ['interstitial','rewarded','banner','offerwall']},
    'triplelift':        {'name': 'TripleLift',              'type': 'web',     'formats': ['native','display','video']},
    'verizon_media':     {'name': 'Yahoo/Verizon Media',     'type': 'web',     'formats': ['display','video','native']},
    'mparticle':         {'name': 'mParticle Analytics',     'type': 'analytics','formats': []},
}

NETWORK_CONFIG_GETTER_MAP = {
    'admob':             'get_admob_config',
    'applovin':          'get_applovin_config',
    'facebook_an':       'get_facebook_an_config',
    'ironsource':        'get_ironsource_config',
    'unity_ads':         'get_unity_ads_config',
    'google_ad_manager': 'get_google_ad_manager_config',
    'prebid':            'get_prebid_config',
    'amazon_publisher':  'get_amazon_publisher_config',
}


class AdNetworkExtendedViewSet(BaseViewSet):
    """
    Ad Network Integration Extended API.

    Publisher endpoints:
      GET  /ad-networks/catalog/            — all networks with metadata
      GET  /ad-networks/my-networks/        — publisher's enabled networks
      GET  /ad-networks/per-network/        — get config for a specific network
      POST /ad-networks/per-network/save/   — save network config
      POST /ad-networks/per-network/enable/ — enable/disable network
      GET  /ad-networks/recommend/          — AI-recommended networks
      GET  /ad-networks/{network}/detail/   — full detail for one network

    Admin endpoints:
      GET  /ad-networks/platform-stats/     — platform-wide network performance
      POST /ad-networks/bulk-enable/        — bulk enable for publisher
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    # ── CATALOG ────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='catalog')
    def catalog(self, request):
        """
        সব available network-এর metadata।
        GET ?type=mobile | web | analytics
        """
        type_filter = request.query_params.get('type')
        networks = [
            {'slug': slug, **meta}
            for slug, meta in NETWORK_META.items()
            if not type_filter or meta['type'] == type_filter
        ]
        return self.success_response(data={
            'networks': networks,
            'total':    len(networks),
        })

    @action(detail=False, methods=['get'], url_path='my-networks')
    def my_networks(self, request):
        """
        Publisher-এর enabled networks + config summary।
        """
        publisher = self._get_publisher()
        try:
            from .ad_network_integration import get_enabled_networks
            enabled = get_enabled_networks(publisher)
            return self.success_response(data={
                'enabled':       enabled,
                'enabled_count': len(enabled),
                'available_count': len(NETWORK_META),
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='per-network')
    def per_network(self, request):
        """
        নির্দিষ্ট network-এর config।
        GET /ad-networks/per-network/?network=admob
        """
        network = request.query_params.get('network', '').lower()
        if not network:
            return self.error_response('network query param required.', status_code=400)
        if network not in NETWORK_META:
            return self.error_response(
                f'Unknown network: {network}. Valid: {", ".join(NETWORK_META.keys())}',
                status_code=400,
            )
        publisher = self._get_publisher()
        getter_name = NETWORK_CONFIG_GETTER_MAP.get(network)
        config_data = None
        if getter_name:
            try:
                from .ad_network_integration import get_network_config_class
                config_cls = get_network_config_class(network)
                if config_cls:
                    qs = config_cls.objects.filter(publisher=publisher)
                    config_data = [
                        {
                            'pk':            obj.pk,
                            'is_enabled':    obj.is_enabled,
                            'is_test_mode':  getattr(obj, 'is_test_mode', False),
                            'sync_status':   getattr(obj, 'sync_status', 'unknown'),
                            'last_sync_at':  getattr(obj, 'last_sync_at', None),
                        }
                        for obj in qs
                    ]
            except Exception:
                config_data = None
        return self.success_response(data={
            'network':  network,
            'meta':     NETWORK_META[network],
            'configs':  config_data or [],
            'count':    len(config_data) if config_data else 0,
        })

    @action(detail=False, methods=['post'], url_path='per-network/save')
    def save_network_config(self, request):
        """
        Network config save/update করে।
        POST body: { "network": "admob", "publisher_id": "...", "app_id": "...", ... }
        """
        network = (request.data.get('network') or '').lower()
        if not network:
            return self.error_response('network required.', status_code=400)
        if network not in NETWORK_META:
            return self.error_response(f'Unknown network: {network}', status_code=400)
        publisher = self._get_publisher()
        try:
            from .ad_network_integration import get_network_config_class
            config_cls = get_network_config_class(network)
            if config_cls is None:
                return self.error_response(
                    f'No config model found for {network}.', status_code=400
                )
            extra = {k: v for k, v in request.data.items()
                     if k not in ('network', 'publisher_id')}
            obj, created = config_cls.objects.update_or_create(
                publisher=publisher,
                defaults={**extra, 'is_enabled': True},
            )
            return self.success_response(
                data={'pk': obj.pk, 'network': network, 'created': created},
                message=f'{"Created" if created else "Updated"} {NETWORK_META[network]["name"]} config.',
                status_code=201 if created else 200,
            )
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='per-network/enable')
    def toggle_network(self, request):
        """
        Network enable/disable করে।
        POST body: { "network": "admob", "enabled": true }
        """
        network = (request.data.get('network') or '').lower()
        enabled = bool(request.data.get('enabled', True))
        if not network:
            return self.error_response('network required.', status_code=400)
        publisher = self._get_publisher()
        try:
            from .ad_network_integration import get_network_config_class
            config_cls = get_network_config_class(network)
            if not config_cls:
                return self.error_response(f'No config model for {network}.', status_code=400)
            updated = config_cls.objects.filter(publisher=publisher).update(
                is_enabled=enabled
            )
            if updated == 0:
                return self.error_response(
                    f'No config found for {network}. Create one first via /per-network/save/',
                    status_code=404,
                )
            return self.success_response(data={
                'network': network,
                'enabled': enabled,
                'updated_count': updated,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='recommend')
    def recommend(self, request):
        """
        Publisher-এর inventory-এর জন্য recommended networks।
        GET ?format=banner | interstitial | rewarded | native
        """
        publisher   = self._get_publisher()
        ad_format   = request.query_params.get('format', 'banner')
        try:
            from .ad_network_integration.network_manager import recommend_networks
            recs = recommend_networks(publisher, ad_format)
            return self.success_response(data={
                'format':           ad_format,
                'recommendations':  recs,
                'count':            len(recs),
            })
        except Exception as e:
            # Fallback: return all networks supporting this format
            fallback = [
                {'slug': slug, **meta}
                for slug, meta in NETWORK_META.items()
                if ad_format in meta.get('formats', [])
            ]
            return self.success_response(data={
                'format':          ad_format,
                'recommendations': fallback,
                'count':           len(fallback),
                'note':            'Recommendation engine unavailable — showing all compatible networks.',
            })

    @action(detail=False, methods=['get'], url_path='performance')
    def performance(self, request):
        """
        Publisher-এর network-by-network performance।
        GET ?days=30
        """
        publisher = self._get_publisher()
        days = int(request.query_params.get('days', 30))
        try:
            from .ad_network_integration import get_network_performance
            data = get_network_performance(publisher, days=days)
            return self.success_response(data={
                'days': days,
                'networks': data,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='detail')
    def network_detail(self, request):
        """
        একটি network-এর full detail (meta + publisher config + performance)।
        GET /ad-networks/detail/?network=admob&days=30
        """
        network   = (request.query_params.get('network') or '').lower()
        days      = int(request.query_params.get('days', 30))
        if not network or network not in NETWORK_META:
            return self.error_response(
                'Valid network param required.', status_code=400
            )
        publisher = self._get_publisher()
        meta      = NETWORK_META[network]
        config_data = None
        perf_data   = None
        try:
            from .ad_network_integration import get_network_config_class
            config_cls = get_network_config_class(network)
            if config_cls:
                qs = config_cls.objects.filter(publisher=publisher)
                config_data = [
                    {'pk': o.pk, 'is_enabled': o.is_enabled,
                     'sync_status': getattr(o, 'sync_status', 'unknown')}
                    for o in qs
                ]
        except Exception:
            pass
        try:
            from .ad_network_integration import get_network_performance
            all_perf = get_network_performance(publisher, days=days)
            perf_data = next(
                (p for p in all_perf if p.get('network') == network), None
            )
        except Exception:
            pass
        return self.success_response(data={
            'network':     network,
            'meta':        meta,
            'configs':     config_data or [],
            'performance': perf_data,
            'days':        days,
        })

    # ── ADMIN ──────────────────────────────────────────────────────────────────

    @action(
        detail=False, methods=['get'], url_path='platform-stats',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def platform_stats(self, request):
        """
        [Admin] Platform-wide network stats।
        GET ?days=30&network=admob
        """
        days    = int(request.query_params.get('days', 30))
        network = request.query_params.get('network')
        stats = {
            'days':        days,
            'network_filter': network,
            'networks':    [],
        }
        for slug, meta in NETWORK_META.items():
            if network and slug != network:
                continue
            stats['networks'].append({'slug': slug, 'name': meta['name'], 'type': meta['type']})
        return self.success_response(data=stats)

    @action(
        detail=False, methods=['post'], url_path='bulk-enable',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def bulk_enable(self, request):
        """
        [Admin] Publisher-এর জন্য একাধিক network একসাথে enable করে।
        POST body: { "publisher_id": "PUB-001", "networks": ["admob","applovin"] }
        """
        from .models import Publisher
        pub_id   = request.data.get('publisher_id')
        networks = request.data.get('networks', [])
        if not pub_id or not networks:
            return self.error_response('publisher_id and networks required.', status_code=400)
        try:
            publisher = Publisher.objects.get(publisher_id=pub_id)
        except Publisher.DoesNotExist:
            return self.error_response('Publisher not found.', status_code=404)
        results = []
        from .ad_network_integration import get_network_config_class
        for net in networks:
            if net not in NETWORK_META:
                results.append({'network': net, 'status': 'unknown_network'})
                continue
            try:
                config_cls = get_network_config_class(net)
                if config_cls:
                    obj, created = config_cls.objects.get_or_create(
                        publisher=publisher,
                        defaults={'is_enabled': True},
                    )
                    if not created:
                        config_cls.objects.filter(pk=obj.pk).update(is_enabled=True)
                    results.append({'network': net, 'status': 'enabled', 'created': created})
                else:
                    results.append({'network': net, 'status': 'no_model'})
            except Exception as exc:
                results.append({'network': net, 'status': 'error', 'error': str(exc)})
        return self.success_response(data={
            'publisher_id': pub_id,
            'results':      results,
        })
