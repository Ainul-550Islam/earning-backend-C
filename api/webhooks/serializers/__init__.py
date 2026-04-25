"""
Webhooks Serializers Package

Re-exports all serializers so views.py can use `from .serializers import X`.
"""
# Core serializers from the flat serializers.py file
from api.webhooks.serializers_flat import (
    WebhookEndpointSerializer,
    WebhookEndpointDetailSerializer,
    WebhookSubscriptionSerializer,
    WebhookDeliveryLogSerializer,
    WebhookEmitSerializer,
    WebhookTestSerializer,
    SecretRotateSerializer,
)

# Package-level serializers (best-effort, ignore if model not yet migrated)
try:
    from .WebhookAnalyticsSerializer import WebhookAnalyticsSerializer, WebhookHealthLogSerializer
except Exception:
    WebhookAnalyticsSerializer = None
    WebhookHealthLogSerializer = None

try:
    from .AdminWebhookSerializer import AdminWebhookSerializer
except Exception:
    AdminWebhookSerializer = None

try:
    from .WebhookFilterSerializer import WebhookFilterSerializer
except Exception:
    WebhookFilterSerializer = None

try:
    from .WebhookTemplateSerializer import WebhookTemplateSerializer
except Exception:
    WebhookTemplateSerializer = None

__all__ = [
    'WebhookEndpointSerializer',
    'WebhookEndpointDetailSerializer',
    'WebhookSubscriptionSerializer',
    'WebhookDeliveryLogSerializer',
    'WebhookEmitSerializer',
    'WebhookTestSerializer',
    'SecretRotateSerializer',
    'WebhookAnalyticsSerializer',
    'WebhookHealthLogSerializer',
    'AdminWebhookSerializer',
    'WebhookFilterSerializer',
    'WebhookTemplateSerializer',
]
