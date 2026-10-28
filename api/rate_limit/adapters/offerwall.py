# api/rate_limit/adapters/offerwall.py
"""
Offerwall System ↔ Rate Limit Adapter
========================================
Covers: offer view, offer click, offer complete, task submit,
        task complete, survey submit.

Usage in api/offerwall/views.py:
    from api.rate_limit.adapters.offerwall import OfferwallRateLimitAdapter

    class OfferViewSet(viewsets.ModelViewSet):
        def retrieve(self, request, *args, **kwargs):
            OfferwallRateLimitAdapter.check_offer_view(request).raise_if_blocked()
            ...

        @action(detail=True, methods=['post'])
        def complete(self, request, pk=None):
            offer = self.get_object()
            OfferwallRateLimitAdapter.check_offer_complete(
                request,
                offer_id=pk,
                offer_wall=offer.provider.name,
            ).raise_if_blocked()
            ...
"""

import logging
from typing import Optional

from api.rate_limit.integration_service import RateLimitIntegrationService, RateLimitResult

logger = logging.getLogger('rate_limit.adapters.offerwall')


class OfferwallRateLimitAdapter:
    """Adapter for api/offerwall system."""

    # ── Offer View ─────────────────────────────────────────────

    @staticmethod
    def check_offer_view(request) -> RateLimitResult:
        """
        Check before listing/retrieving offers.

        Where to call:
            api/offerwall/views.py → OfferViewSet.list() / retrieve()
        """
        user = getattr(request, 'user', None)
        return RateLimitIntegrationService.check(
            'offer_view',
            request=request,
            user=user,
        )

    # ── Offer Click ────────────────────────────────────────────

    @staticmethod
    def check_offer_click(request, offer_id=None, offer_wall: str = '') -> RateLimitResult:
        """
        Check before recording an offer click.

        Where to call:
            api/offerwall/views.py → OfferViewSet click action
            api/offerwall/webhooks/ → click tracking
        """
        user = getattr(request, 'user', None)
        ip = RateLimitIntegrationService._extract_ip(request)
        return RateLimitIntegrationService.check(
            'offer_click',
            request=request,
            user=user,
            ip_address=ip,
            extra_context={
                'offer_id': str(offer_id) if offer_id else '',
                'offer_wall': offer_wall,
            },
        )

    # ── Offer Complete ─────────────────────────────────────────

    @staticmethod
    def check_offer_complete(
        request,
        offer_id=None,
        offer_wall: str = '',
        user=None,
    ) -> RateLimitResult:
        """
        Check before marking an offer as complete.
        Most critical check — prevents reward farming.

        Where to call:
            api/offerwall/views.py → complete action
            api/offerwall/webhooks/OfferwallWebhook.py → postback handler
            api/offerwall/webhooks/TapjoyWebhook.py
            api/offerwall/webhooks/AdGemWebhook.py
        """
        user = user or getattr(request, 'user', None)
        ip = RateLimitIntegrationService._extract_ip(request)
        return RateLimitIntegrationService.check(
            'offer_complete',
            request=request,
            user=user,
            ip_address=ip,
            extra_context={
                'offer_id': str(offer_id) if offer_id else '',
                'offer_wall': offer_wall,
            },
        )

    # ── Task Submit ────────────────────────────────────────────

    @staticmethod
    def check_task_submit(request, task_type: str = '', task_id=None) -> RateLimitResult:
        """
        Check before task submission.

        Where to call:
            api/offerwall/views.py → task submit action
        """
        user = getattr(request, 'user', None)
        return RateLimitIntegrationService.check(
            'task_submit',
            request=request,
            user=user,
            extra_context={
                'task_type': task_type,
                'task_id': str(task_id) if task_id else '',
            },
        )

    # ── Task Complete ──────────────────────────────────────────

    @staticmethod
    def check_task_complete(request, task_type: str = '', task_id=None) -> RateLimitResult:
        """
        Check before marking a task as complete.

        Where to call:
            api/offerwall/views.py → task complete action
        """
        user = getattr(request, 'user', None)
        return RateLimitIntegrationService.check(
            'task_complete',
            request=request,
            user=user,
            extra_context={
                'task_type': task_type,
                'task_id': str(task_id) if task_id else '',
            },
        )

    # ── Survey Submit ──────────────────────────────────────────

    @staticmethod
    def check_survey_submit(request) -> RateLimitResult:
        """
        Check before survey submission.

        Where to call:
            api/offerwall/views.py → survey submit action
        """
        user = getattr(request, 'user', None)
        return RateLimitIntegrationService.check(
            'survey_submit',
            request=request,
            user=user,
        )

    # ── Webhook postback (no request object) ───────────────────

    @staticmethod
    def check_webhook_complete(
        user=None,
        ip_address: str = '',
        offer_id=None,
        offer_wall: str = '',
    ) -> RateLimitResult:
        """
        Check offer/task completion arriving via webhook (no Django request).
        Used when postback comes in from external offerwall provider.

        Where to call:
            api/offerwall/webhooks/TapjoyWebhook.py
            api/offerwall/webhooks/AdGemWebhook.py
            api/offerwall/webhooks/OfferwallWebhook.py
        """
        return RateLimitIntegrationService.check(
            'offer_complete',
            user=user,
            ip_address=ip_address,
            extra_context={
                'offer_id': str(offer_id) if offer_id else '',
                'offer_wall': offer_wall,
                'source': 'webhook',
            },
        )
