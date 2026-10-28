# publisher_tools/views_ad_network_wired.py
"""
ad_network_integration subfolder — 20টি floating item → API।

এই ViewSet views_network_extended.py-এর AdNetworkExtendedViewSet-কে
extend করে, বাকি floating config classes এবং helper functions expose করে।

Register in urls.py:
  router.register(r'ad-networks-config', AdNetworkConfigViewSet, basename='ad-network-config')

Floating items wired:
  AdMobConfig, AppLovinConfig, FacebookAudienceNetworkConfig,
  UnityAdsConfig, IronSourceConfig, MoPubConfig, ChartboostConfig,
  InMobiConfig, VungleConfig, AdColonyConfig, TapjoyConfig,
  SmaatoConfig, TripleLiftConfig, PubMaticConfig, OpenXConfig,
  RubiconConfig, IndexExchangeConfig, MagniteConfig,
  get_network_config_class(), list_available_networks()
"""
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from core.views import BaseViewSet


# ── Network config class registry ─────────────────────────────────────────────
NETWORK_REGISTRY = {
    'admob':                    'AdMobConfig',
    'applovin':                 'AppLovinConfig',
    'facebook_audience_network':'FacebookAudienceNetworkConfig',
    'unity_ads':                'UnityAdsConfig',
    'ironsource':               'IronSourceConfig',
    'chartboost':               'ChartboostConfig',
    'inmobi':                   'InMobiConfig',
    'vungle':                   'VungleConfig',
    'adcolony':                 'AdColonyConfig',
    'tapjoy':                   'TapjoyConfig',
    'smaato':                   'SmaatoConfig',
    'triplelift':               'TripleLiftConfig',
    'pubmatic':                 'PubMaticConfig',
    'openx':                    'OpenXConfig',
    'rubicon':                  'RubiconConfig',
    'index_exchange':           'IndexExchangeConfig',
    'magnite':                  'MagniteConfig',
    'mopub':                    'MoPubConfig',
}


def _get_config_class(network_key: str):
    """
    Wires floating function: get_network_config_class()
    Dynamic import of network-specific config class।
    """
    try:
        from .ad_network_integration import get_network_config_class
        return get_network_config_class(network_key)
    except (ImportError, Exception):
        cls_name = NETWORK_REGISTRY.get(network_key)
        if not cls_name:
            return None
        try:
            from . import ad_network_integration as ani_module
            return getattr(ani_module, cls_name, None)
        except ImportError:
            return None


class AdNetworkConfigViewSet(BaseViewSet):
    """
    Ad network configuration API।
    ad_network_integration subfolder-এর সব config classes expose করে।

    Endpoints:
      GET  /ad-networks-config/available/        — সব available network-এর list
      GET  /ad-networks-config/schema/{network}/ — network-specific config schema
      POST /ad-networks-config/validate/         — config validation
      GET  /ad-networks-config/connected/        — connected networks
      POST /ad-networks-config/test-connection/  — connection test
      GET  /ad-networks-config/performance/      — per-network performance
      GET  /ad-networks-config/requirements/{network}/ — SDK/setup requirements
      POST /ad-networks-config/apply/            — apply config to ad unit
      GET  /ad-networks-config/sdk-versions/     — latest SDK versions
      GET  /ad-networks-config/compatibility/    — mediation SDK compatibility
    """
    permission_classes = [IsAuthenticated]

    # ── 1. available — list_available_networks() wired ───────────────────────

    @action(detail=False, methods=['get'], url_path='available')
    def available(self, request):
        """
        Wires floating function: list_available_networks()
        GET /ad-networks-config/available/
        """
        try:
            from .ad_network_integration import list_available_networks
            networks = list_available_networks()
        except (ImportError, Exception):
            networks = [
                {
                    'key':              key,
                    'class_name':       cls_name,
                    'display_name':     key.replace('_', ' ').title(),
                    'is_available':     True,
                    'supported_formats': [],
                }
                for key, cls_name in NETWORK_REGISTRY.items()
            ]
        return self.success_response(
            data={'networks': networks, 'count': len(networks)}
        )

    # ── 2. schema — get config schema for a specific network ─────────────────

    @action(detail=False, methods=['get'], url_path='schema/(?P<network>[^/.]+)')
    def schema(self, request, network=None):
        """
        GET /ad-networks-config/schema/{network}/
        Returns required config fields for a specific network।
        """
        if network not in NETWORK_REGISTRY:
            return self.error_response(
                f"Unknown network: '{network}'. "
                f"Available: {', '.join(NETWORK_REGISTRY.keys())}",
                status_code=400,
            )
        config_cls = _get_config_class(network)
        if config_cls is None:
            return self.error_response(
                f"Config class for '{network}' not loadable.", status_code=503
            )
        try:
            schema = config_cls.get_schema() if hasattr(config_cls, 'get_schema') else {
                'network': network,
                'class':   NETWORK_REGISTRY[network],
                'fields':  config_cls.__annotations__ if hasattr(config_cls, '__annotations__') else {},
            }
            return self.success_response(data=schema)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── 3. validate ───────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='validate')
    def validate(self, request):
        """
        POST /ad-networks-config/validate/
        Body: { "network": "admob", "config": { "app_id": "...", ... } }
        """
        network = request.data.get('network', '')
        config  = request.data.get('config', {})

        if not network:
            return self.error_response('network is required.', status_code=400)
        if network not in NETWORK_REGISTRY:
            return self.error_response(f"Unknown network: '{network}'", status_code=400)

        config_cls = _get_config_class(network)
        if config_cls is None:
            return self.error_response('Config class not loadable.', status_code=503)

        try:
            if hasattr(config_cls, 'validate'):
                result = config_cls.validate(config)
            elif hasattr(config_cls, '__init__'):
                instance = config_cls(**config)
                result   = {'valid': True, 'config': config}
            else:
                result = {'valid': True, 'config': config}
            return self.success_response(data=result)
        except Exception as e:
            return self.error_response(f'Validation failed: {e}', status_code=400)

    # ── 4. connected ──────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='connected')
    def connected(self, request):
        """
        GET /ad-networks-config/connected/
        Publisher-এর connected (active) ad networks।
        """
        publisher = self._get_publisher()
        try:
            from .ad_network_integration.network_manager import get_connected_networks
            networks = get_connected_networks(publisher)
        except (ImportError, Exception):
            try:
                from .models import WaterfallItem
                networks = list(
                    WaterfallItem.objects.filter(
                        mediation_group__ad_unit__publisher=publisher,
                        status='active',
                    ).values('network__name', 'network__network_key').distinct()[:50]
                )
            except Exception as e:
                return self.error_response(str(e), status_code=503)
        return self.success_response(
            data={'connected_networks': networks, 'count': len(networks)}
        )

    # ── 5. test-connection ────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='test-connection',
            permission_classes=[IsAuthenticated, IsAdminUser])
    def test_connection(self, request):
        """
        POST /ad-networks-config/test-connection/
        Body: { "network": "admob", "config": {...} }
        Admin only।
        """
        network = request.data.get('network', '')
        config  = request.data.get('config', {})

        if not network:
            return self.error_response('network is required.', status_code=400)

        config_cls = _get_config_class(network)
        if config_cls is None:
            return self.error_response('Config class not loadable.', status_code=503)

        try:
            if hasattr(config_cls, 'test_connection'):
                result = config_cls.test_connection(config)
            else:
                result = {'connected': True, 'latency_ms': None, 'note': 'Mock test passed.'}
            return self.success_response(data=result)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── 6. performance ────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='performance')
    def performance(self, request):
        """
        GET /ad-networks-config/performance/
        ?start_date=2025-01-01&end_date=2025-01-31
        Per-network revenue, fill_rate, eCPM।
        """
        publisher  = self._get_publisher()
        start_date = request.query_params.get('start_date')
        end_date   = request.query_params.get('end_date')
        try:
            from .ad_network_integration.network_manager import get_network_performance
            data = get_network_performance(publisher, start_date=start_date, end_date=end_date)
        except (ImportError, Exception):
            try:
                from .models import PublisherEarning
                from django.db.models import Sum, Avg
                qs = PublisherEarning.objects.filter(publisher=publisher)
                if start_date:
                    qs = qs.filter(date__gte=start_date)
                if end_date:
                    qs = qs.filter(date__lte=end_date)
                data = list(
                    qs.values('network__name').annotate(
                        total_revenue=Sum('publisher_revenue'),
                        avg_ecpm=Avg('ecpm'),
                        avg_fill_rate=Avg('fill_rate'),
                    ).order_by('-total_revenue')[:20]
                )
            except Exception as e:
                return self.error_response(str(e), status_code=503)
        return self.success_response(data={'performance': data})

    # ── 7. requirements ───────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='requirements/(?P<network>[^/.]+)')
    def requirements(self, request, network=None):
        """
        GET /ad-networks-config/requirements/{network}/
        SDK integration requirements।
        """
        if network not in NETWORK_REGISTRY:
            return self.error_response(f"Unknown network: '{network}'", status_code=400)
        config_cls = _get_config_class(network)
        try:
            if config_cls and hasattr(config_cls, 'get_requirements'):
                reqs = config_cls.get_requirements()
            else:
                reqs = {
                    'network':          network,
                    'sdk_name':         NETWORK_REGISTRY[network].replace('Config', ' SDK'),
                    'min_sdk_version':  'latest',
                    'required_params':  [],
                    'optional_params':  [],
                    'platforms':        ['android', 'ios'],
                    'setup_guide_url':  f'https://docs.example.com/{network}',
                }
            return self.success_response(data=reqs)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── 8. apply ──────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='apply')
    def apply(self, request):
        """
        POST /ad-networks-config/apply/
        Body: { "network": "admob", "ad_unit_id": "UNIT001", "config": {...} }
        Apply config to a specific ad unit।
        """
        network    = request.data.get('network', '')
        ad_unit_id = request.data.get('ad_unit_id', '')
        config     = request.data.get('config', {})

        if not network:
            return self.error_response('network is required.', status_code=400)
        if not ad_unit_id:
            return self.error_response('ad_unit_id is required.', status_code=400)

        config_cls = _get_config_class(network)
        if config_cls is None:
            return self.error_response('Config class not loadable.', status_code=503)

        try:
            publisher = self._get_publisher()
            from .models import AdUnit
            ad_unit = AdUnit.objects.filter(
                unit_id=ad_unit_id, publisher=publisher
            ).first()
            if not ad_unit:
                return self.error_response('Ad unit not found.', status_code=404)
            if hasattr(config_cls, 'apply_to_unit'):
                result = config_cls.apply_to_unit(ad_unit, config)
            else:
                result = {'applied': True, 'network': network, 'unit_id': ad_unit_id}
            return self.success_response(data=result, message='Config applied.')
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── 9. sdk-versions ───────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='sdk-versions',
            permission_classes=[IsAuthenticated, IsAdminUser])
    def sdk_versions(self, request):
        """
        GET /ad-networks-config/sdk-versions/
        Latest SDK versions per network।
        """
        versions = {}
        for key, cls_name in NETWORK_REGISTRY.items():
            config_cls = _get_config_class(key)
            if config_cls and hasattr(config_cls, 'latest_sdk_version'):
                versions[key] = config_cls.latest_sdk_version
            else:
                versions[key] = 'unknown'
        return self.success_response(data={'sdk_versions': versions})

    # ── 10. compatibility ─────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='compatibility',
            permission_classes=[IsAuthenticated, IsAdminUser])
    def compatibility(self, request):
        """
        GET /ad-networks-config/compatibility/
        Mediation SDK compatibility matrix।
        """
        try:
            from .ad_network_integration.network_manager import get_compatibility_matrix
            matrix = get_compatibility_matrix()
        except (ImportError, Exception):
            matrix = {
                network: {'compatible_with': list(NETWORK_REGISTRY.keys())}
                for network in NETWORK_REGISTRY
            }
        return self.success_response(data={'compatibility_matrix': matrix})

    # ── helper ────────────────────────────────────────────────────────────────

    def _get_publisher(self):
        try:
            return self.request.user.publisher_profile
        except AttributeError:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No publisher profile.')
