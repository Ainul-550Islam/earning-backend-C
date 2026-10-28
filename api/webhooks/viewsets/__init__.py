# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Webhooks ViewSets Package

Imports all ViewSets so they can be referenced from urls.py via:
    from .viewsets import WebhookFilterViewSet, ...

FIX: Added actual class imports (previously only __all__ strings existed).
"""

# ── Core viewsets are NOT re-exported here. urls.py routes the views.py
# versions of WebhookEndpointViewSet / WebhookSubscriptionViewSet /
# WebhookDeliveryLogViewSet / WebhookEmitAPIView / EventTypeListAPIView.
# The duplicate copies that used to live in this package were unused by
# any import in the codebase and were moved to _deprecated_unused/.

# ── Advanced Feature ViewSets ─────────────────────────────────────────────────
from .WebhookFilterViewSet    import WebhookFilterViewSet
from .WebhookTemplateViewSet  import WebhookTemplateViewSet
from .WebhookBatchViewSet     import WebhookBatchViewSet
from .WebhookSecretViewSet    import WebhookSecretViewSet
from .WebhookReplayViewSet    import WebhookReplayViewSet

# ── Inbound (receive webhooks from external sources) ─────────────────────────
from .InboundWebhookViewSet    import InboundWebhookViewSet
from .InboundWebhookLogViewSet import InboundWebhookLogViewSet

# ── Observability ─────────────────────────────────────────────────────────────
from .WebhookAnalyticsViewSet import WebhookAnalyticsViewSet
from .WebhookHealthViewSet    import WebhookHealthViewSet

# ── Admin (staff/ops only) ───────────────────────────────────────────────────
from .AdminWebhookViewSet import AdminWebhookViewSet

# ── Aging (lifecycle management) ─────────────────────────────────────────────
from .WebhookAgingViewSet import (
    WebhookEndpointAgingViewSet,
    WebhookDeliveryAgingViewSet,
    WebhookAgingEventViewSet,
    WebhookAgingSummaryAPIView,
    WebhookAgingPolicyAPIView,
    WebhookAgingArchiveAPIView,
    WebhookAgingPurgeAPIView,
)

__all__ = [
    # Advanced
    "WebhookFilterViewSet",
    "WebhookTemplateViewSet",
    "WebhookBatchViewSet",
    "WebhookSecretViewSet",
    "WebhookReplayViewSet",
    # Inbound
    "InboundWebhookViewSet",
    "InboundWebhookLogViewSet",
    # Observability
    "WebhookAnalyticsViewSet",
    "WebhookHealthViewSet",
    # Admin
    "AdminWebhookViewSet",
    # Aging
    "WebhookEndpointAgingViewSet",
    "WebhookDeliveryAgingViewSet",
    "WebhookAgingEventViewSet",
    "WebhookAgingSummaryAPIView",
    "WebhookAgingPolicyAPIView",
    "WebhookAgingArchiveAPIView",
    "WebhookAgingPurgeAPIView",
    # Rate limits & retry analysis
    "WebhookRateLimitViewSet",
    "WebhookRetryAnalysisViewSet",
]

# ── Rate limits & retry analysis ─────────────────────────────────────────────
from .WebhookRateLimitViewSet import WebhookRateLimitViewSet, WebhookRetryAnalysisViewSet
