"""
IntegrationViewSet
Exposes per-SmartLink integration config for TikTok, Snapchat,
Facebook Pixel, Google Ads, and Push Network routing.
"""
import logging
import time

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from api.smartlink.models import SmartLink
from api.smartlink.permissions import IsSmartLinkOwnerOrAdmin
from api.smartlink.serializers.IntegrationConfigSerializer import (
    AllIntegrationsSerializer,
    TikTokIntegrationSerializer,
    SnapchatIntegrationSerializer,
    FacebookPixelIntegrationSerializer,
    GoogleAdsIntegrationSerializer,
    TwitterAdsIntegrationSerializer,
    GA4IntegrationSerializer,
    PushNetworkIntegrationSerializer,
    IntegrationTestResultSerializer,
)

logger = logging.getLogger('smartlink.viewsets.integration')

_INTEGRATION_KEYS = ['tiktok', 'snapchat', 'facebook', 'google_ads', 'twitter', 'ga4', 'push_network']

_SERIALIZER_MAP = {
    'tiktok':       TikTokIntegrationSerializer,
    'snapchat':     SnapchatIntegrationSerializer,
    'facebook':     FacebookPixelIntegrationSerializer,
    'google_ads':   GoogleAdsIntegrationSerializer,
    'twitter':      TwitterAdsIntegrationSerializer,
    'ga4':          GA4IntegrationSerializer,
    'push_network': PushNetworkIntegrationSerializer,
}


class IntegrationViewSet(viewsets.ViewSet):
    """
    Manage ad-network integrations for a SmartLink.
    Config is stored as JSON inside SmartLink.integrations (JSONField).

    GET  /api/smartlink/smartlinks/{sl_pk}/integrations/
         → Return all configured integrations for this SmartLink.

    PUT  /api/smartlink/smartlinks/{sl_pk}/integrations/{network}/
         → Save config for a specific integration (tiktok|snapchat|facebook|google_ads|push_network).

    DELETE /api/smartlink/smartlinks/{sl_pk}/integrations/{network}/
         → Remove a specific integration config.

    POST /api/smartlink/smartlinks/{sl_pk}/integrations/{network}/test/
         → Fire a test event to verify the integration is working.

    GET  /api/smartlink/smartlinks/{sl_pk}/integrations/{network}/status/
         → Return whether the integration is active and last-fired stats.
    """
    permission_classes = [IsAuthenticated, IsSmartLinkOwnerOrAdmin]

    def _get_smartlink(self, smartlink_pk, user):
        from django.shortcuts import get_object_or_404
        qs = SmartLink.objects.all() if user.is_staff else SmartLink.objects.filter(publisher=user)
        return get_object_or_404(qs, pk=smartlink_pk)

    def list(self, request, smartlink_pk=None):
        """GET /api/smartlink/smartlinks/{sl_pk}/integrations/ — all integrations."""
        sl = self._get_smartlink(smartlink_pk, request.user)
        integrations = getattr(sl, 'integrations', {}) or {}
        # Mask access tokens before returning
        safe = self._mask_secrets(integrations)
        return Response({
            'smartlink': sl.slug,
            'integrations': safe,
            'active_count': sum(
                1 for v in integrations.values()
                if isinstance(v, dict) and v.get('is_active', False)
            ),
        })

    def retrieve(self, request, smartlink_pk=None, pk=None):
        """GET /api/smartlink/smartlinks/{sl_pk}/integrations/{network}/"""
        if pk not in _INTEGRATION_KEYS:
            return Response(
                {'detail': f"Unknown integration '{pk}'. Valid: {', '.join(_INTEGRATION_KEYS)}"},
                status=status.HTTP_404_NOT_FOUND,
            )
        sl = self._get_smartlink(smartlink_pk, request.user)
        integrations = getattr(sl, 'integrations', {}) or {}
        config = integrations.get(pk)
        if not config:
            return Response(
                {'detail': f"No {pk} integration configured for this SmartLink."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({pk: self._mask_secrets({pk: config})[pk]})

    def update(self, request, smartlink_pk=None, pk=None):
        """PUT /api/smartlink/smartlinks/{sl_pk}/integrations/{network}/"""
        if pk not in _INTEGRATION_KEYS:
            return Response(
                {'detail': f"Unknown integration '{pk}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer_class = _SERIALIZER_MAP[pk]
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        sl = self._get_smartlink(smartlink_pk, request.user)
        integrations = getattr(sl, 'integrations', {}) or {}
        integrations[pk] = serializer.validated_data
        SmartLink.objects.filter(pk=sl.pk).update(integrations=integrations)

        logger.info(
            f"Integration '{pk}' saved for [{sl.slug}] by {request.user.username}"
        )
        return Response({
            'message': f"{pk} integration saved.",
            pk: self._mask_secrets({pk: serializer.validated_data})[pk],
        })

    def destroy(self, request, smartlink_pk=None, pk=None):
        """DELETE /api/smartlink/smartlinks/{sl_pk}/integrations/{network}/"""
        if pk not in _INTEGRATION_KEYS:
            return Response(
                {'detail': f"Unknown integration '{pk}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        sl = self._get_smartlink(smartlink_pk, request.user)
        integrations = getattr(sl, 'integrations', {}) or {}
        if pk not in integrations:
            return Response(
                {'detail': f"No {pk} integration to delete."},
                status=status.HTTP_404_NOT_FOUND,
            )
        del integrations[pk]
        SmartLink.objects.filter(pk=sl.pk).update(integrations=integrations)
        logger.info(f"Integration '{pk}' removed from [{sl.slug}] by {request.user.username}")
        return Response({'message': f"{pk} integration removed."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='test')
    def test_integration(self, request, smartlink_pk=None, pk=None):
        """
        POST /api/smartlink/smartlinks/{sl_pk}/integrations/{network}/test/
        Fire a test event to verify connectivity.
        """
        if pk not in _INTEGRATION_KEYS:
            return Response({'detail': f"Unknown integration '{pk}'."}, status=400)

        sl = self._get_smartlink(smartlink_pk, request.user)
        integrations = getattr(sl, 'integrations', {}) or {}
        config = integrations.get(pk)
        if not config:
            return Response(
                {'detail': f"No {pk} integration configured. Save config first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        start = time.monotonic()
        result = self._fire_test_event(pk, config)
        latency_ms = round((time.monotonic() - start) * 1000, 2)

        payload = {
            'integration': pk,
            'success': result['success'],
            'http_status': result.get('http_status'),
            'message': result['message'],
            'latency_ms': latency_ms,
        }
        return Response(IntegrationTestResultSerializer(payload).data)

    @action(detail=True, methods=['get'], url_path='status')
    def integration_status(self, request, smartlink_pk=None, pk=None):
        """
        GET /api/smartlink/smartlinks/{sl_pk}/integrations/{network}/status/
        Return active state and cached last-fired stats.
        """
        if pk not in _INTEGRATION_KEYS:
            return Response({'detail': f"Unknown integration '{pk}'."}, status=404)

        sl = self._get_smartlink(smartlink_pk, request.user)
        integrations = getattr(sl, 'integrations', {}) or {}
        config = integrations.get(pk)

        from django.core.cache import cache
        stats_key = f'integration_stats:{sl.pk}:{pk}'
        stats = cache.get(stats_key, {})

        return Response({
            'integration': pk,
            'configured': bool(config),
            'is_active': config.get('is_active', False) if config else False,
            'events_fired_today': stats.get('events_fired_today', 0),
            'last_fired_at': stats.get('last_fired_at'),
            'last_success': stats.get('last_success'),
        })

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _mask_secrets(self, integrations: dict) -> dict:
        """Replace access tokens and secrets with masked placeholders."""
        SECRET_FIELDS = ('access_token', 'api_secret')
        masked = {}
        for key, config in integrations.items():
            if isinstance(config, dict):
                entry = {}
                for field, value in config.items():
                    if field in SECRET_FIELDS and value:
                        entry[field] = '***' + str(value)[-4:] if len(str(value)) > 4 else '****'
                    else:
                        entry[field] = value
                masked[key] = entry
            else:
                masked[key] = config
        return masked

    def _fire_test_event(self, network: str, config: dict) -> dict:
        """Attempt to fire a minimal test event to the network."""
        test_context = {
            'ip': '127.0.0.1',
            'user_agent': 'SmartLink-TestBot/1.0',
            'url': 'https://test.smartlink.internal/',
        }
        try:
            if network == 'tiktok':
                from ..integrations.tiktok.TikTokEventsAPI import TikTokEventsAPI
                TikTokEventsAPI().fire_click_event(
                    pixel_id=config['pixel_id'],
                    access_token=config['access_token'],
                    context=test_context,
                )
                return {'success': True, 'message': 'TikTok test event queued (async).', 'http_status': None}

            elif network == 'snapchat':
                from ..integrations.snapchat.SnapchatConversionsAPI import SnapchatConversionsAPI
                SnapchatConversionsAPI().fire_page_view(
                    pixel_id=config['pixel_id'],
                    token=config['access_token'],
                    context=test_context,
                )
                return {'success': True, 'message': 'Snapchat test event queued (async).', 'http_status': None}

            elif network == 'facebook':
                from ..integrations.traffic_sources.FacebookPixelService import FacebookPixelService
                FacebookPixelService().fire_page_view(
                    pixel_id=config['pixel_id'],
                    access_token=config['access_token'],
                    event_data=test_context,
                )
                return {'success': True, 'message': 'Facebook test event queued (async).', 'http_status': None}

            elif network == 'google_ads':
                from ..integrations.traffic_sources.GoogleAdsService import GoogleAdsConversionService
                GoogleAdsConversionService().fire_conversion({
                    'gclid': 'test_gclid',
                    'conversion_label': config.get('conversion_label', 'test'),
                    'conversion_value': 0,
                    'currency': config.get('currency', 'USD'),
                    'order_id': 'test_order',
                })
                return {'success': True, 'message': 'Google Ads test event queued (async).', 'http_status': None}

            elif network == 'twitter':
                from ..integrations.twitter.TwitterAdsConversionAPI import TwitterAdsConversionAPI
                TwitterAdsConversionAPI().fire_page_view(
                    pixel_id=config['pixel_id'],
                    access_token=config['access_token'],
                    context=test_context,
                )
                return {'success': True, 'message': 'Twitter/X test event queued (async).', 'http_status': None}

            elif network == 'ga4':
                from ..integrations.google_analytics.GA4MeasurementProtocol import GA4MeasurementProtocol
                result = GA4MeasurementProtocol().validate_event(
                    measurement_id=config['measurement_id'],
                    api_secret=config['api_secret'],
                    event_name='page_view',
                    context=test_context,
                )
                success = 'validationMessages' in result and len(result.get('validationMessages', [])) == 0
                return {'success': success, 'message': 'GA4 debug validation complete.', 'http_status': 200}

            elif network == 'push_network':
                return {'success': True, 'message': 'Push network config is valid (no live test needed).', 'http_status': None}

        except Exception as e:
            return {'success': False, 'message': str(e), 'http_status': None}

        return {'success': False, 'message': 'Unknown network.', 'http_status': None}
