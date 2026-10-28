# api/rate_limit/adapters/ad_networks.py
"""
Ad Networks ↔ Rate Limit Adapter
====================================
Covers: ad impression, ad click, ad conversion.

Usage in api/ad_networks/:
    from api.rate_limit.adapters.ad_networks import AdNetworksRateLimitAdapter

    class AdNetworkViewSet(viewsets.ModelViewSet):
        def click(self, request, *args, **kwargs):
            ip = request.META.get('REMOTE_ADDR')
            AdNetworksRateLimitAdapter.check_ad_click(
                ip_address=ip,
                network='adsense',
                request=request,
            ).raise_if_blocked()
            ...
"""

import logging
from api.rate_limit.integration_service import RateLimitIntegrationService, RateLimitResult

logger = logging.getLogger('rate_limit.adapters.ad_networks')


class AdNetworksRateLimitAdapter:
    """Adapter for api/ad_networks system."""

    @staticmethod
    def check_ad_impression(ip_address: str, user=None, request=None, network: str = '') -> RateLimitResult:
        """
        Check before recording an ad impression.
        Where to call:
            api/ad_networks/views.py → impression endpoint
            api/ad_networks/viewset.py
        """
        return RateLimitIntegrationService.check(
            'ad_impression',
            user=user,
            ip_address=ip_address,
            request=request,
            extra_context={'network': network},
        )

    @staticmethod
    def check_ad_click(ip_address: str, user=None, request=None, network: str = '') -> RateLimitResult:
        """
        Check before recording an ad click.
        Where to call:
            api/ad_networks/views.py → click endpoint
            api/ad_networks/viewset.py
            api/ad_networks/viewset_cap.py
        """
        return RateLimitIntegrationService.check(
            'ad_click',
            user=user,
            ip_address=ip_address,
            request=request,
            extra_context={'network': network},
        )

    @staticmethod
    def check_ad_conversion(ip_address: str, user=None, request=None, network: str = '') -> RateLimitResult:
        """
        Check before recording an ad conversion.
        Where to call:
            api/ad_networks/webhooks/views.py → conversion webhook
        """
        return RateLimitIntegrationService.check(
            'ad_conversion',
            user=user,
            ip_address=ip_address,
            request=request,
            extra_context={'network': network},
        )

    @staticmethod
    def check_from_endpoint(request, action: str = 'ad_click', network: str = '') -> RateLimitResult:
        """
        Generic check for api/ad_networks/endpoint.py.
        Replaces existing rate_limit logic in endpoint.py.
        """
        ip = RateLimitIntegrationService._extract_ip(request)
        user = getattr(request, 'user', None)
        return RateLimitIntegrationService.check(
            action,
            request=request,
            user=user if user and getattr(user, 'is_authenticated', False) else None,
            ip_address=ip,
            extra_context={'network': network},
        )
