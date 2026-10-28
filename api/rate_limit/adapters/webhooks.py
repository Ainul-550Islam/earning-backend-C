# api/rate_limit/adapters/webhooks.py
"""
Webhooks System ↔ Rate Limit Adapter
=======================================
Covers: inbound webhook, outbound delivery, retry.

Usage in api/webhooks/:
    from api.rate_limit.adapters.webhooks import WebhooksRateLimitAdapter

    # In api/webhooks/utils.py:
    result = WebhooksRateLimitAdapter.check_inbound(
        ip_address=request.META.get('REMOTE_ADDR'),
        request=request,
    )
    if not result.allowed:
        return HttpResponse('Too Many Requests', status=429)
"""

import logging
from api.rate_limit.integration_service import RateLimitIntegrationService, RateLimitResult

logger = logging.getLogger('rate_limit.adapters.webhooks')


class WebhooksRateLimitAdapter:
    """Adapter for api/webhooks system."""

    @staticmethod
    def check_inbound(ip_address: str, request=None, source: str = '') -> RateLimitResult:
        """
        Check inbound webhook request.
        Where to call:
            api/webhooks/utils.py
            api/webhooks/viewsets/ → inbound handler
            api/webhooks/services/inbound/
        """
        return RateLimitIntegrationService.check(
            'webhook_inbound',
            request=request,
            ip_address=ip_address,
            extra_context={'source': source},
        )

    @staticmethod
    def check_outbound(request=None, destination: str = '') -> RateLimitResult:
        """
        Check before sending outbound webhook.
        Prevents flooding external endpoints.
        Where to call:
            api/webhooks/services/core/
            api/webhooks/tasks/
        """
        return RateLimitIntegrationService.check(
            'webhook_outbound',
            request=request,
            extra_context={'destination': destination},
        )

    @staticmethod
    def check_retry(request=None, webhook_id: str = '') -> RateLimitResult:
        """
        Check before retrying a failed webhook.
        Where to call:
            api/webhooks/tasks/__init__.py
            api/webhooks/services/batch/
        """
        return RateLimitIntegrationService.check(
            'webhook_retry',
            request=request,
            extra_context={'webhook_id': webhook_id},
        )

    @staticmethod
    def check_from_tasks(action: str = 'webhook_outbound', context: dict = None) -> RateLimitResult:
        """
        Called from Celery tasks (no request object).
        Where to call:
            api/webhooks/tasks/__init__.py
        """
        return RateLimitIntegrationService.check(
            action,
            extra_context=context or {},
        )
