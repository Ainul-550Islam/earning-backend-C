# publisher_tools/views_network_config.py
# ============================================================
# NEW FILE — NetworkConfigViewSet
# ad_network_integration/ subfolder expose করে।
# Admin-only CRUD for network configurations.
#
# Register in urls.py:
#   router.register(r'network-configs', NetworkConfigViewSet, basename='network-config')
# ============================================================
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet


class NetworkConfigViewSet(BaseViewSet):
    """
    Ad Network Configuration Management (Admin Only)।
    20টি ad network config model manage করে।

    Actions:
      list_networks    — সব available network slugs
      get_config       — specific network config
      create_config    — নতুন config তৈরি
      update_config    — config update
      test_connection  — network connectivity test
      performance      — network performance data
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    http_method_names  = ['get', 'post', 'patch', 'head', 'options']

    def _get_network_class(self, network_slug):
        try:
            from .ad_network_integration import get_network_config_class
            return get_network_config_class(network_slug)
        except (ImportError, ValueError) as e:
            return None, str(e)

    # ── LIST AVAILABLE NETWORKS ───────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='networks')
    def list_networks(self, request):
        """
        সব available network slugs।
        GET /network-configs/networks/
        """
        try:
            from .ad_network_integration import NETWORK_CONFIG_MAP, get_enabled_networks
            enabled  = get_enabled_networks()
            all_nets = list(NETWORK_CONFIG_MAP.keys())
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'all_networks':      all_nets,
            'enabled_networks':  enabled,
            'total_count':       len(all_nets),
        })

    # ── GET CONFIG ────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='config')
    def get_config(self, request):
        """
        Network config retrieve।
        GET /network-configs/config/?network=admob&publisher_id=PUB123456
        """
        network_slug  = request.query_params.get('network')
        publisher_id  = request.query_params.get('publisher_id')

        if not network_slug:
            return self.error_response('network parameter is required.', status_code=400)

        NetworkModel = self._get_network_class(network_slug)
        if NetworkModel is None:
            return self.error_response(f'Unknown network: {network_slug}', status_code=400)

        qs = NetworkModel.objects.all()
        if publisher_id:
            qs = qs.filter(publisher__publisher_id=publisher_id)

        configs = list(qs.values())
        return self.success_response(data={
            'network':  network_slug,
            'configs':  configs,
            'count':    len(configs),
        })

    # ── CREATE CONFIG ─────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='config/create')
    def create_config(self, request):
        """
        নতুন network config তৈরি।
        POST /network-configs/config/create/
        Body: {"network": "admob", "publisher_id": "PUB123456", "app_id": "ca-app-pub-xxx", ...}
        """
        network_slug  = request.data.get('network')
        publisher_id  = request.data.get('publisher_id')

        if not network_slug or not publisher_id:
            return self.error_response('network and publisher_id are required.', status_code=400)

        from .models import Publisher
        try:
            publisher = Publisher.objects.get(publisher_id=publisher_id)
        except Publisher.DoesNotExist:
            return self.error_response(f'Publisher {publisher_id} not found.', status_code=404)

        NetworkModel = self._get_network_class(network_slug)
        if NetworkModel is None:
            return self.error_response(f'Unknown network: {network_slug}', status_code=400)

        config_data = {
            k: v for k, v in request.data.items()
            if k not in ('network', 'publisher_id')
        }

        try:
            config, created = NetworkModel.objects.get_or_create(
                publisher=publisher,
                defaults=config_data,
            )
            if not created:
                for key, val in config_data.items():
                    setattr(config, key, val)
                config.save()
        except Exception as e:
            return self.error_response(f'Config creation failed: {str(e)}', status_code=400)

        return self.success_response(
            data={'network': network_slug, 'config_id': str(config.id), 'created': created},
            message='Config created.' if created else 'Config updated.',
        )

    # ── TEST CONNECTION ────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='test-connection')
    def test_connection(self, request):
        """
        Network connectivity test।
        POST /network-configs/test-connection/
        Body: {"network": "admob", "publisher_id": "PUB123456"}
        """
        network_slug  = request.data.get('network')
        publisher_id  = request.data.get('publisher_id')

        if not network_slug or not publisher_id:
            return self.error_response('network and publisher_id are required.', status_code=400)

        NetworkModel = self._get_network_class(network_slug)
        if NetworkModel is None:
            return self.error_response(f'Unknown network: {network_slug}', status_code=400)

        from .models import Publisher
        try:
            publisher = Publisher.objects.get(publisher_id=publisher_id)
        except Publisher.DoesNotExist:
            return self.error_response(f'Publisher {publisher_id} not found.', status_code=404)

        config = NetworkModel.objects.filter(publisher=publisher).first()
        if not config:
            return self.error_response(
                f'No {network_slug} config found for {publisher_id}.',
                status_code=404,
            )

        try:
            result = config.test_connection()
        except Exception as e:
            result = {'success': False, 'error': str(e)}

        return self.success_response(data={
            'network':    network_slug,
            'publisher':  publisher_id,
            'connection': result,
        })

    # ── NETWORK PERFORMANCE ────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='performance')
    def performance(self, request):
        """
        Network performance comparison।
        GET /network-configs/performance/?days=30
        """
        days = int(request.query_params.get('days', 30))

        try:
            from .ad_network_integration import get_network_performance
            data = get_network_performance(days=days)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=data)
