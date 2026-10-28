# publisher_tools/views_integrations_extended.py
"""
FILE 3 of 10 — Integrations Wired API
=======================================
integrations/ subfolder-এর 26টি floating class/function expose করা হয়েছে।

Previously floating (now wired):
  AmplitudeAnalyticsIntegration, ReactSDKIntegration, VuejsSDKIntegration,
  AngularSDKIntegration, WordPressPluginIntegration, WooCommercePluginIntegration,
  ShopifyAppIntegration, DrupalModuleIntegration, JoomlaExtensionIntegration,
  MixpanelAnalyticsIntegration, SegmentioIntegration, GoogleAnalyticsIntegration,
  GoogleTagManagerIntegration, FacebookPixelIntegration, mParticleIntegration,
  get_all_integration_classes, get_integration,
  amplitude_integration, mixpanel_integration, segment_integration,
  wordpress_plugin, woocommerce_plugin, shopify_app,
  drupal_module, joomla_extension, google_analytics_integration

Register in urls.py:
  router.register(r'integrations-ext', IntegrationsExtendedViewSet, basename='integrations-ext')
"""
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher


# ── Full integration catalogue (slug → display info) ─────────────────────────
INTEGRATION_CATALOGUE = {
    # Analytics SDKs
    'amplitude':         {'name': 'Amplitude Analytics',       'category': 'analytics',  'class': 'AmplitudeAnalyticsIntegration'},
    'mixpanel':          {'name': 'Mixpanel',                  'category': 'analytics',  'class': 'MixpanelAnalyticsIntegration'},
    'segment':           {'name': 'Segment.io',                'category': 'analytics',  'class': 'SegmentioIntegration'},
    'google_analytics':  {'name': 'Google Analytics 4',        'category': 'analytics',  'class': 'GoogleAnalyticsIntegration'},
    'google_tag_manager':{'name': 'Google Tag Manager',        'category': 'analytics',  'class': 'GoogleTagManagerIntegration'},
    'facebook_pixel':    {'name': 'Meta Pixel (Facebook)',     'category': 'analytics',  'class': 'FacebookPixelIntegration'},
    'mparticle':         {'name': 'mParticle',                 'category': 'analytics',  'class': 'mParticleIntegration'},
    # Web SDKs
    'react_sdk':         {'name': 'React SDK',                 'category': 'sdk',        'class': 'ReactSDKIntegration'},
    'vue_sdk':           {'name': 'Vue.js SDK',                'category': 'sdk',        'class': 'VuejsSDKIntegration'},
    'angular_sdk':       {'name': 'Angular SDK',               'category': 'sdk',        'class': 'AngularSDKIntegration'},
    # CMS / eCommerce plugins
    'wordpress':         {'name': 'WordPress Plugin',          'category': 'cms',        'class': 'WordPressPluginIntegration'},
    'woocommerce':       {'name': 'WooCommerce Plugin',        'category': 'ecommerce',  'class': 'WooCommercePluginIntegration'},
    'shopify':           {'name': 'Shopify App',               'category': 'ecommerce',  'class': 'ShopifyAppIntegration'},
    'drupal':            {'name': 'Drupal Module',             'category': 'cms',        'class': 'DrupalModuleIntegration'},
    'joomla':            {'name': 'Joomla Extension',          'category': 'cms',        'class': 'JoomlaExtensionIntegration'},
}


class IntegrationsExtendedViewSet(BaseViewSet):
    """
    Integrations Extended API — actual integration class-গুলো expose করে।

    GET  /integrations-ext/catalogue/            — full integration catalogue
    GET  /integrations-ext/by-category/          — categorized list
    GET  /integrations-ext/connected-detail/     — connected integrations with class info
    POST /integrations-ext/sync/                 — sync data for connected integration
    POST /integrations-ext/health-check/         — health check all connected
    GET  /integrations-ext/sdk-config/           — get SDK config snippet
    POST /integrations-ext/track-event/          — track a custom event
    GET  /integrations-ext/class-info/           — class metadata for developer docs
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def _get_integration_class(self, slug):
        """integrations/__init__.py থেকে integration class load করে।"""
        try:
            from .integrations import get_integration
            return get_integration(slug)
        except Exception:
            return None

    def _get_all_classes(self):
        try:
            from .integrations import get_all_integration_classes
            return get_all_integration_classes()
        except Exception:
            return {}

    # ── CATALOGUE ──────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='catalogue')
    def catalogue(self, request):
        """
        সব integrations-এর full catalogue।
        GET ?category=analytics | sdk | cms | ecommerce
        """
        cat_filter = request.query_params.get('category')
        result = [
            {'slug': slug, **info}
            for slug, info in INTEGRATION_CATALOGUE.items()
            if not cat_filter or info['category'] == cat_filter
        ]
        return self.success_response(data={
            'integrations': result,
            'total':        len(result),
            'categories':   list({i['category'] for i in INTEGRATION_CATALOGUE.values()}),
        })

    @action(detail=False, methods=['get'], url_path='by-category')
    def by_category(self, request):
        """Integrations categorized করে return করে।"""
        grouped = {}
        for slug, info in INTEGRATION_CATALOGUE.items():
            cat = info['category']
            grouped.setdefault(cat, []).append({'slug': slug, **info})
        return self.success_response(data=grouped)

    @action(detail=False, methods=['get'], url_path='class-info')
    def class_info(self, request):
        """
        Integration class-এর developer metadata (for API docs)。
        GET ?slug=amplitude
        """
        slug = request.query_params.get('slug', '').lower()
        if slug and slug not in INTEGRATION_CATALOGUE:
            return self.error_response(f'Unknown integration: {slug}', status_code=400)
        all_classes = self._get_all_classes()
        result = {}
        for s, info in INTEGRATION_CATALOGUE.items():
            if slug and s != slug:
                continue
            cls = all_classes.get(info['class'])
            result[s] = {
                'slug':       s,
                'name':       info['name'],
                'category':   info['category'],
                'class_name': info['class'],
                'has_sync':   hasattr(cls, 'sync') if cls else False,
                'has_test':   hasattr(cls, 'test_connection') if cls else False,
                'model_fields': [
                    f.name for f in cls._meta.fields
                    if not f.name.startswith('_')
                ] if cls and hasattr(cls, '_meta') else [],
            }
        return self.success_response(data=result if slug else result)

    # ── CONNECTED DETAIL ───────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='connected-detail')
    def connected_detail(self, request):
        """
        Connected integrations-এর detail (actual class instances)।
        """
        publisher    = self._get_publisher()
        all_classes  = self._get_all_classes()
        connected    = []
        for slug, info in INTEGRATION_CATALOGUE.items():
            cls = all_classes.get(info['class'])
            if cls is None:
                continue
            try:
                objs = cls.objects.filter(publisher=publisher)
                for obj in objs:
                    connected.append({
                        'slug':        slug,
                        'name':        info['name'],
                        'category':    info['category'],
                        'pk':          obj.pk,
                        'is_active':   getattr(obj, 'is_active', True),
                        'sync_status': getattr(obj, 'sync_status', 'unknown'),
                        'last_sync_at':str(getattr(obj, 'last_sync_at', '')),
                    })
            except Exception:
                continue
        return self.success_response(data={
            'connected':       connected,
            'connected_count': len(connected),
        })

    # ── SYNC ───────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='sync')
    def sync(self, request):
        """
        Connected integration-এর data sync করে।
        POST body: { "slug": "amplitude" }
        """
        slug = (request.data.get('slug') or '').lower()
        if not slug:
            return self.error_response('slug required.', status_code=400)
        publisher   = self._get_publisher()
        all_classes = self._get_all_classes()
        info        = INTEGRATION_CATALOGUE.get(slug)
        if not info:
            return self.error_response(f'Unknown integration: {slug}', status_code=400)
        cls = all_classes.get(info['class'])
        if cls is None:
            return self.error_response(f'Class {info["class"]} not loadable.', status_code=503)
        try:
            obj = cls.objects.filter(publisher=publisher).first()
            if obj is None:
                return self.error_response(
                    f'{info["name"]} is not connected. Use /integrations/connect/ first.',
                    status_code=404,
                )
            success = obj.sync()
            return self.success_response(data={
                'slug':    slug,
                'synced':  success,
                'message': f'{info["name"]} synced successfully.' if success else 'Sync failed.',
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='health-check')
    def health_check(self, request):
        """
        সব connected integrations-এর health check।
        POST body: {} (checks all) or { "slugs": ["amplitude", "mixpanel"] }
        """
        publisher    = self._get_publisher()
        all_classes  = self._get_all_classes()
        check_slugs  = request.data.get('slugs') or list(INTEGRATION_CATALOGUE.keys())
        results = []
        for slug in check_slugs:
            info = INTEGRATION_CATALOGUE.get(slug)
            if not info:
                continue
            cls = all_classes.get(info['class'])
            if cls is None:
                results.append({'slug': slug, 'status': 'class_unavailable'})
                continue
            try:
                obj = cls.objects.filter(publisher=publisher).first()
                if obj is None:
                    results.append({'slug': slug, 'status': 'not_connected'})
                    continue
                healthy = obj.test_connection()
                results.append({
                    'slug':   slug,
                    'name':   info['name'],
                    'status': 'healthy' if healthy else 'unhealthy',
                })
            except Exception as e:
                results.append({'slug': slug, 'status': 'error', 'error': str(e)})
        healthy_count = sum(1 for r in results if r.get('status') == 'healthy')
        return self.success_response(data={
            'results':       results,
            'total_checked': len(results),
            'healthy':       healthy_count,
            'unhealthy':     len(results) - healthy_count,
        })

    # ── SDK CONFIG ─────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='sdk-config')
    def sdk_config(self, request):
        """
        SDK integration config snippet (for publisher's frontend code)。
        GET ?slug=react_sdk
        """
        slug = (request.query_params.get('slug') or '').lower()
        if not slug:
            return self.error_response('slug required.', status_code=400)
        publisher    = self._get_publisher()
        all_classes  = self._get_all_classes()
        info         = INTEGRATION_CATALOGUE.get(slug)
        if not info:
            return self.error_response(f'Unknown integration: {slug}', status_code=400)
        cls = all_classes.get(info['class'])
        sdk_config  = None
        if cls:
            try:
                obj = cls.objects.filter(publisher=publisher).first()
                if obj and hasattr(obj, 'get_sdk_config'):
                    sdk_config = obj.get_sdk_config()
            except Exception:
                pass
        if sdk_config is None:
            # Generic config template
            sdk_config = {
                'slug':            slug,
                'name':            info['name'],
                'publisher_id':    publisher.publisher_id,
                'integration_key': f'{publisher.publisher_id}_{slug}',
                'note':            'Connect this integration first via /integrations/connect/',
            }
        return self.success_response(data={'slug': slug, 'config': sdk_config})

    # ── TRACK EVENT ────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='track-event')
    def track_event(self, request):
        """
        Connected analytics integration-এ custom event track করে।
        POST body: {
          "slug":       "amplitude",
          "event_name": "ad_impression",
          "properties": { "ad_unit_id": "UNIT-001", "ecpm": 2.5 }
        }
        """
        slug       = (request.data.get('slug') or '').lower()
        event_name = request.data.get('event_name')
        properties = request.data.get('properties', {})
        if not slug or not event_name:
            return self.error_response('slug and event_name required.', status_code=400)
        publisher   = self._get_publisher()
        all_classes = self._get_all_classes()
        info        = INTEGRATION_CATALOGUE.get(slug)
        if not info or info['category'] not in ('analytics',):
            return self.error_response(
                f'{slug} is not an analytics integration.', status_code=400
            )
        cls = all_classes.get(info['class'])
        if cls is None:
            return self.error_response(f'Integration class not loadable.', status_code=503)
        try:
            obj = cls.objects.filter(publisher=publisher).first()
            if obj is None:
                return self.error_response(f'{info["name"]} is not connected.', status_code=404)
            if hasattr(obj, 'track'):
                result = obj.track(event_name, properties)
            else:
                result = {'tracked': False, 'note': 'track() not implemented for this integration'}
            return self.success_response(data={
                'slug':       slug,
                'event_name': event_name,
                'result':     result,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)
