# publisher_tools/views_integrations_embed.py
"""
FILE 6 of 10 — Integrations Embed Code API
===========================================
integrations/ remaining 9 floating functions exposed.
Previously floating: get_embed_code (all 6 integrations),
  is_token_valid, sync_traffic_data, get_ga_tag_code

Register in urls.py:
  router.register(r'integrations-embed', IntegrationsEmbedViewSet, basename='int-embed')
"""
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher

EMBED_INTEGRATIONS = [
    'amplitude', 'mixpanel', 'segment', 'google_analytics',
    'google_tag_manager', 'mparticle',
]
INTEGRATION_CLASS_MAP = {
    'amplitude':          ('amplitude_integration',          'AmplitudeAnalyticsIntegration'),
    'mixpanel':           ('mixpanel_integration',           'MixpanelAnalyticsIntegration'),
    'segment':            ('segment_integration',            'SegmentioIntegration'),
    'google_analytics':   ('google_analytics_integration',   'GoogleAnalyticsIntegration'),
    'google_tag_manager': ('google_tag_manager',             'GoogleTagManagerIntegration'),
    'mparticle':          ('mparticle_integration',          'mParticleIntegration'),
}


class IntegrationsEmbedViewSet(BaseViewSet):
    """
    Embed Code & Analytics Sync API.

    GET  /integrations-embed/embed-code/     — get embed snippet for integration
    GET  /integrations-embed/all-embed-codes/ — all embed codes in one response
    POST /integrations-embed/sync-ga/        — sync GA traffic data
    POST /integrations-embed/validate-token/ — validate GA/GTM token
    GET  /integrations-embed/ga-tag/         — get GA tag code
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    @action(detail=False, methods=['get'], url_path='embed-code')
    def embed_code(self, request):
        """
        Integration embed code snippet।
        GET ?slug=amplitude | mixpanel | segment | google_analytics | ...
        """
        slug      = (request.query_params.get('slug') or '').lower()
        publisher = self._get_publisher()
        if not slug or slug not in INTEGRATION_CLASS_MAP:
            return self.error_response(
                f'slug required. Valid: {", ".join(INTEGRATION_CLASS_MAP)}', status_code=400
            )
        mod_name, cls_name = INTEGRATION_CLASS_MAP[slug]
        try:
            mod = __import__(f'publisher_tools.integrations.{mod_name}', fromlist=[cls_name])
            cls = getattr(mod, cls_name, None)
            if cls is None:
                return self.error_response(f'Class {cls_name} not found.', status_code=503)
            obj = cls.objects.filter(publisher=publisher).first()
            if obj is None:
                return self.success_response(data={
                    'slug':       slug,
                    'embed_code': None,
                    'message':    f'{slug} is not connected. Use /integrations/connect/ first.',
                })
            code = obj.get_embed_code() if hasattr(obj, 'get_embed_code') else None
            return self.success_response(data={'slug': slug, 'embed_code': code})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='all-embed-codes')
    def all_embed_codes(self, request):
        """All connected integrations' embed codes in one response।"""
        publisher = self._get_publisher()
        results   = {}
        for slug, (mod_name, cls_name) in INTEGRATION_CLASS_MAP.items():
            try:
                mod = __import__(f'publisher_tools.integrations.{mod_name}', fromlist=[cls_name])
                cls = getattr(mod, cls_name, None)
                if cls is None:
                    continue
                obj = cls.objects.filter(publisher=publisher).first()
                if obj and hasattr(obj, 'get_embed_code'):
                    results[slug] = obj.get_embed_code()
            except Exception:
                continue
        return self.success_response(data={'embed_codes': results, 'count': len(results)})

    @action(detail=False, methods=['post'], url_path='sync-ga')
    def sync_ga(self, request):
        """Sync traffic data from Google Analytics।"""
        publisher = self._get_publisher()
        try:
            from .integrations.google_analytics_integration import GoogleAnalyticsIntegration
            obj = GoogleAnalyticsIntegration.objects.filter(publisher=publisher).first()
            if not obj:
                return self.error_response('Google Analytics not connected.', status_code=404)
            if hasattr(obj, 'sync_traffic_data'):
                result = obj.sync_traffic_data()
                return self.success_response(data=result if isinstance(result, dict)
                                              else {'synced': bool(result)})
            return self.error_response('sync_traffic_data not available.', status_code=503)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='validate-token')
    def validate_token(self, request):
        """Validate GA/GTM API token।"""
        publisher = self._get_publisher()
        slug      = (request.data.get('slug') or 'google_analytics').lower()
        try:
            mod_name, cls_name = INTEGRATION_CLASS_MAP.get(slug, (None, None))
            if not mod_name:
                return self.error_response(f'Unknown slug: {slug}', status_code=400)
            mod = __import__(f'publisher_tools.integrations.{mod_name}', fromlist=[cls_name])
            cls = getattr(mod, cls_name, None)
            obj = cls.objects.filter(publisher=publisher).first() if cls else None
            if not obj:
                return self.error_response(f'{slug} not connected.', status_code=404)
            if hasattr(obj, 'is_token_valid'):
                valid = obj.is_token_valid()
                return self.success_response(data={'slug': slug, 'token_valid': valid})
            return self.success_response(data={'slug': slug, 'token_valid': None,
                                               'note': 'Token validation not available.'})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='ga-tag')
    def ga_tag(self, request):
        """Get Google Analytics tag code snippet।"""
        publisher = self._get_publisher()
        try:
            from .integrations.google_analytics_integration import GoogleAnalyticsIntegration
            obj = GoogleAnalyticsIntegration.objects.filter(publisher=publisher).first()
            if not obj:
                return self.success_response(data={'tag_code': None,
                                                   'message': 'Google Analytics not connected.'})
            tag = obj.get_ga_tag_code() if hasattr(obj, 'get_ga_tag_code') else None
            return self.success_response(data={'tag_code': tag})
        except Exception as e:
            return self.error_response(str(e), status_code=503)
