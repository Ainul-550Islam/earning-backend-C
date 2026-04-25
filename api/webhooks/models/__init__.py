
# Functions needed by migrations (originally in flat models.py)
try:
    from api.webhooks.models_flat import _generate_secret_key, _empty_dict
except ImportError:
    import secrets
    def _generate_secret_key() -> str:
        return secrets.token_hex(32)
    def _empty_dict():
        return {}
"""
Webhooks Models Module

This module contains all models for the webhooks system,
including core models, advanced features, analytics, and replay functionality.
Models are organized into separate files for better maintainability.
"""

# Import all models to ensure Django discovers them
from .core import WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog
from .advanced import WebhookFilter, WebhookBatch, WebhookBatchItem, WebhookTemplate, WebhookSecret
from .inbound import InboundWebhook, InboundWebhookLog, InboundWebhookRoute, InboundWebhookError
from .analytics import WebhookAnalytics, WebhookHealthLog, WebhookEventStat, WebhookRateLimit, WebhookRetryAnalysis
from .replay import WebhookReplay, WebhookReplayBatch, WebhookReplayItem

# Explicitly list all model names for Django's model discovery
# This ensures Django recognizes all models for makemigrations and migrate commands
__all__ = [
    # Core Models
    'WebhookEndpoint',
    'WebhookSubscription',
    'WebhookDeliveryLog',
    
    # Advanced Models
    'WebhookFilter',
    'WebhookBatch',
    'WebhookBatchItem',
    'WebhookTemplate',
    'WebhookSecret',
    
    # Inbound Models
    'InboundWebhook',
    'InboundWebhookLog',
    'InboundWebhookRoute',
    'InboundWebhookError',
    
    # Analytics Models
    'WebhookAnalytics',
    'WebhookHealthLog',
    'WebhookEventStat',
    'WebhookRateLimit',
    'WebhookRetryAnalysis',
    
    # Replay Models
    'WebhookReplay',
    'WebhookReplayBatch',
    'WebhookReplayItem',
]

# Django will discover models through the app registry
# The models will be available for makemigrations and migrate commands
# when Django apps are loaded properly.
