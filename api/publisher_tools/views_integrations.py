# publisher_tools/views_integrations.py
# ============================================================
# NEW FILE — IntegrationsViewSet
# integrations/ subfolder expose করে।
# Publisher-এর third-party SDK + analytics integrations manage করে।
#
# Register in urls.py:
#   router.register(r'integrations', IntegrationsViewSet, basename='integration')
# ============================================================
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher


class IntegrationsViewSet(BaseViewSet):
    """
    Third-Party Integrations Management।
    15টি SDK/analytics integration configure + manage করে।

    Integrations available:
      amplitude, mixpanel, segment, mparticle,
      google_analytics, google_tag_manager, facebook_pixel,
      wordpress, woocommerce, shopify, drupal, joomla,
      react_sdk, vue_sdk, angular_sdk

    Actions:
      list_available   — সব available integrations
      list_connected   — publisher-এর connected integrations
      get_integration  — specific integration config
      connect          — integration connect
      disconnect       — integration disconnect
      test_connection  — connectivity test
      get_install_guide — SDK/plugin install guide
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def _get_publisher(self):
        try:
            return self.request.user.publisher_profile
        except Exception:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No active publisher profile.')

    # ── LIST AVAILABLE ────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='available')
    def list_available(self, request):
        """
        সব available integration slugs + metadata।
        GET /integrations/available/
        """
        try:
            from .integrations import AVAILABLE_INTEGRATIONS, INTEGRATION_REGISTRY
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        INTEGRATION_META = {
            'amplitude':         {'category': 'analytics',   'name': 'Amplitude',               'type': 'sdk'},
            'mixpanel':          {'category': 'analytics',   'name': 'Mixpanel',                'type': 'sdk'},
            'segment':           {'category': 'analytics',   'name': 'Segment',                 'type': 'sdk'},
            'mparticle':         {'category': 'analytics',   'name': 'mParticle',               'type': 'sdk'},
            'google_analytics':  {'category': 'analytics',   'name': 'Google Analytics',        'type': 'sdk'},
            'google_tag_manager':{'category': 'tag_manager', 'name': 'Google Tag Manager',      'type': 'tag'},
            'facebook_pixel':    {'category': 'advertising', 'name': 'Facebook Pixel',          'type': 'pixel'},
            'wordpress':         {'category': 'cms',         'name': 'WordPress Plugin',        'type': 'plugin'},
            'woocommerce':       {'category': 'ecommerce',   'name': 'WooCommerce Plugin',      'type': 'plugin'},
            'shopify':           {'category': 'ecommerce',   'name': 'Shopify App',             'type': 'app'},
            'drupal':            {'category': 'cms',         'name': 'Drupal Module',           'type': 'module'},
            'joomla':            {'category': 'cms',         'name': 'Joomla Extension',        'type': 'extension'},
            'react_sdk':         {'category': 'sdk',         'name': 'React SDK',               'type': 'sdk'},
            'vue_sdk':           {'category': 'sdk',         'name': 'Vue.js SDK',              'type': 'sdk'},
            'angular_sdk':       {'category': 'sdk',         'name': 'Angular SDK',             'type': 'sdk'},
        }

        return self.success_response(data={
            'integrations': [
                {'slug': slug, **INTEGRATION_META.get(slug, {})}
                for slug in AVAILABLE_INTEGRATIONS
            ],
            'total': len(AVAILABLE_INTEGRATIONS),
        })

    # ── LIST CONNECTED ────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='connected')
    def list_connected(self, request):
        """
        Publisher-এর connected integrations।
        GET /integrations/connected/
        """
        publisher = self._get_publisher()

        try:
            from .integrations import AVAILABLE_INTEGRATIONS, get_integration
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        connected = []
        for slug in AVAILABLE_INTEGRATIONS:
            try:
                IntModel = get_integration(slug)
                instance = IntModel.objects.filter(publisher=publisher).first()
                if instance:
                    connected.append({
                        'slug':       slug,
                        'is_active':  getattr(instance, 'is_active', True),
                        'connected_at': str(instance.created_at),
                    })
            except Exception:
                continue

        return self.success_response(data={
            'connected':       connected,
            'connected_count': len(connected),
        })

    # ── GET SPECIFIC INTEGRATION ──────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='detail')
    def get_integration_detail(self, request):
        """
        Specific integration config।
        GET /integrations/detail/?slug=amplitude
        """
        slug      = request.query_params.get('slug')
        publisher = self._get_publisher()

        if not slug:
            return self.error_response('slug parameter is required.', status_code=400)

        try:
            from .integrations import get_integration
            IntModel = get_integration(slug)
            instance = IntModel.objects.filter(publisher=publisher).first()
        except ValueError as e:
            return self.error_response(str(e), status_code=400)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        if not instance:
            return self.success_response(data=None,
                message=f'{slug} not connected. POST /integrations/connect/ to connect.')

        # Return safe fields only (exclude API keys from response)
        safe_fields = {
            'id':          str(instance.id),
            'slug':        slug,
            'is_active':   getattr(instance, 'is_active', True),
            'created_at':  str(instance.created_at),
            'updated_at':  str(instance.updated_at),
        }
        return self.success_response(data=safe_fields)

    # ── CONNECT ───────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='connect')
    def connect(self, request):
        """
        Integration connect।
        POST /integrations/connect/
        Body: {"slug": "amplitude", "api_key": "xxx", ...}
        """
        slug      = request.data.get('slug')
        publisher = self._get_publisher()

        if not slug:
            return self.error_response('slug is required.', status_code=400)

        try:
            from .integrations import get_integration
            IntModel = get_integration(slug)
        except ValueError as e:
            return self.error_response(str(e), status_code=400)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        config_data = {k: v for k, v in request.data.items() if k != 'slug'}

        try:
            instance, created = IntModel.objects.get_or_create(
                publisher=publisher,
                defaults=config_data,
            )
            if not created:
                for key, val in config_data.items():
                    setattr(instance, key, val)
                instance.save()
        except Exception as e:
            return self.error_response(f'Connection failed: {str(e)}', status_code=400)

        return self.success_response(
            data={'slug': slug, 'id': str(instance.id), 'created': created},
            message=f'{slug} connected.' if created else f'{slug} updated.',
        )

    # ── DISCONNECT ────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='disconnect')
    def disconnect(self, request):
        """
        Integration disconnect।
        POST /integrations/disconnect/
        Body: {"slug": "amplitude"}
        """
        slug      = request.data.get('slug')
        publisher = self._get_publisher()

        if not slug:
            return self.error_response('slug is required.', status_code=400)

        try:
            from .integrations import get_integration
            IntModel  = get_integration(slug)
            deleted_count, _ = IntModel.objects.filter(publisher=publisher).delete()
        except ValueError as e:
            return self.error_response(str(e), status_code=400)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        if deleted_count == 0:
            return self.error_response(f'{slug} was not connected.', status_code=404)

        return self.success_response(message=f'{slug} disconnected.')

    # ── TEST CONNECTION ────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='test')
    def test_connection(self, request):
        """
        Integration connectivity test।
        POST /integrations/test/
        Body: {"slug": "amplitude"}
        """
        slug      = request.data.get('slug')
        publisher = self._get_publisher()

        if not slug:
            return self.error_response('slug is required.', status_code=400)

        try:
            from .integrations import get_integration
            IntModel = get_integration(slug)
            instance = IntModel.objects.filter(publisher=publisher).first()
        except (ValueError, ImportError, Exception) as e:
            return self.error_response(str(e), status_code=400)

        if not instance:
            return self.error_response(f'{slug} not connected.', status_code=404)

        try:
            result = instance.test_connection()
        except Exception as e:
            result = {'success': False, 'error': str(e)}

        return self.success_response(data={
            'slug':   slug,
            'result': result,
        })

    # ── INSTALL GUIDE ─────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='install-guide')
    def get_install_guide(self, request):
        """
        SDK/plugin install guide।
        GET /integrations/install-guide/?slug=react_sdk
        """
        slug = request.query_params.get('slug')
        if not slug:
            return self.error_response('slug is required.', status_code=400)

        INSTALL_GUIDES = {
            'react_sdk':    {'package': 'publisher-tools-react', 'manager': 'npm', 'docs': 'https://docs.publishertools.io/sdk/react'},
            'vue_sdk':      {'package': 'publisher-tools-vue',   'manager': 'npm', 'docs': 'https://docs.publishertools.io/sdk/vue'},
            'angular_sdk':  {'package': 'publisher-tools-angular','manager': 'npm','docs': 'https://docs.publishertools.io/sdk/angular'},
            'wordpress':    {'plugin': 'publisher-tools-for-wordpress', 'source': 'wordpress.org', 'docs': 'https://docs.publishertools.io/plugins/wordpress'},
            'woocommerce':  {'plugin': 'publisher-tools-woocommerce',   'source': 'wordpress.org', 'docs': 'https://docs.publishertools.io/plugins/woocommerce'},
            'shopify':      {'app': 'publisher-tools', 'source': 'Shopify App Store', 'docs': 'https://docs.publishertools.io/apps/shopify'},
            'drupal':       {'module': 'publisher_tools', 'source': 'drupal.org', 'docs': 'https://docs.publishertools.io/plugins/drupal'},
            'joomla':       {'extension': 'publisher-tools', 'source': 'JED', 'docs': 'https://docs.publishertools.io/plugins/joomla'},
        }

        guide = INSTALL_GUIDES.get(slug, {
            'docs': f'https://docs.publishertools.io/integrations/{slug}',
            'note': 'Configure via API key in settings.',
        })

        return self.success_response(data={'slug': slug, 'install_guide': guide})
