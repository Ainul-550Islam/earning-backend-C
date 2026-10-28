"""Webhooks Admin Configuration

This module contains the admin configuration for all webhook models.
"""

from .endpoint_admin import WebhookEndpointAdmin
from .subscription_admin import WebhookSubscriptionAdmin
from .delivery_log_admin import WebhookDeliveryLogAdmin
from .inbound_admin import InboundWebhookAdmin, InboundWebhookLogAdmin, InboundWebhookRouteAdmin, InboundWebhookErrorAdmin
from .analytics_admin import WebhookAnalyticsAdmin, WebhookHealthLogAdmin, WebhookEventStatAdmin, WebhookRateLimitAdmin, WebhookRetryAnalysisAdmin
from .replay_admin import WebhookReplayAdmin, WebhookReplayBatchAdmin, WebhookReplayItemAdmin
from .template_admin import WebhookTemplateAdmin, WebhookBatchAdmin, WebhookBatchItemAdmin, WebhookSecretAdmin

__all__ = [
    'WebhookEndpointAdmin',
    'WebhookSubscriptionAdmin',
    'WebhookDeliveryLogAdmin',
    'InboundWebhookAdmin',
    'InboundWebhookLogAdmin',
    'InboundWebhookRouteAdmin',
    'InboundWebhookErrorAdmin',
    'WebhookAnalyticsAdmin',
    'WebhookHealthLogAdmin',
    'WebhookEventStatAdmin',
    'WebhookRateLimitAdmin',
    'WebhookRetryAnalysisAdmin',
    'WebhookReplayAdmin',
    'WebhookReplayBatchAdmin',
    'WebhookReplayItemAdmin',
    'WebhookTemplateAdmin',
    'WebhookBatchAdmin',
    'WebhookBatchItemAdmin',
    'WebhookSecretAdmin',
]

# ─────────────────────────────────────────────────────────────────────────────
#  Force-register all admin classes (called from apps.py ready())
# ─────────────────────────────────────────────────────────────────────────────

def _force_register_webhooks():
    """
    Idempotently register all webhook models with Django admin.
    Called by WebhooksConfig.ready() so admin works even when
    INSTALLED_APPS ordering causes early model registration races.
    """
    from django.contrib import admin
    from api.webhooks.models import (
        WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog,
        WebhookBatch, WebhookTemplate, WebhookSecret, WebhookFilter,
    )
    from api.webhooks.models.analytics import WebhookAnalytics, WebhookHealthLog
    from api.webhooks.models.replay    import WebhookReplay, WebhookReplayBatch

    registrations = [
        (WebhookEndpoint,      WebhookEndpointAdmin),
        (WebhookSubscription,  WebhookSubscriptionAdmin),
        (WebhookDeliveryLog,   WebhookDeliveryLogAdmin),
        (WebhookAnalytics,     WebhookAnalyticsAdmin),
        (WebhookHealthLog,     WebhookHealthLogAdmin),
        (WebhookReplay,        WebhookReplayAdmin),
        (WebhookReplayBatch,   WebhookReplayBatchAdmin),
    ]

    for model, model_admin in registrations:
        try:
            admin.site.register(model, model_admin)
        except admin.sites.AlreadyRegistered:
            pass  # already registered — idempotent
