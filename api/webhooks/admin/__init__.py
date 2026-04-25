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
