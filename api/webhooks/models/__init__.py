# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Webhooks Models Package

Single authoritative source. All views, serializers, tasks and services
must import from here — not from individual sub-modules directly.
"""

# ── Core models (canonical) ───────────────────────────────────────────────────
from .core import WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog

# ── Advanced models ───────────────────────────────────────────────────────────
from .advanced import (
    WebhookFilter,
    WebhookBatch,
    WebhookBatchItem,
    WebhookTemplate,
    WebhookSecret,
)

# ── Inbound models ────────────────────────────────────────────────────────────
from .inbound import (
    InboundWebhook,
    InboundWebhookLog,
    InboundWebhookRoute,
    InboundWebhookError,
)

# ── Analytics models ──────────────────────────────────────────────────────────
from .analytics import (
    WebhookAnalytics,
    WebhookHealthLog,
    WebhookEventStat,
    WebhookRateLimit,
    WebhookRetryAnalysis,
)

# ── Replay models ─────────────────────────────────────────────────────────────
from .replay import WebhookReplay, WebhookReplayBatch, WebhookReplayItem

# ── Helpers re-exported so services/tasks can import from .models ─────────────
from .core import _generate_secret_key, _empty_dict

__all__ = [
    # Core
    "WebhookEndpoint",
    "WebhookSubscription",
    "WebhookDeliveryLog",
    # Advanced
    "WebhookFilter",
    "WebhookBatch",
    "WebhookBatchItem",
    "WebhookTemplate",
    "WebhookSecret",
    # Inbound
    "InboundWebhook",
    "InboundWebhookLog",
    "InboundWebhookRoute",
    "InboundWebhookError",
    # Analytics
    "WebhookAnalytics",
    "WebhookHealthLog",
    "WebhookEventStat",
    "WebhookRateLimit",
    "WebhookRetryAnalysis",
    # Replay
    "WebhookReplay",
    "WebhookReplayBatch",
    "WebhookReplayItem",
    # Aging
    'AgeTier',
    'AgingEventType',
    'WebhookAgingPolicy',
    'WebhookEndpointAging',
    'WebhookDeliveryAging',
    'WebhookAgingEvent',
    # Helpers
    "_generate_secret_key",
    "_empty_dict",
]

# ── Aging models ──────────────────────────────────────────────────────────────
from .aging import (
    AgeTier,
    AgingEventType,
    WebhookAgingPolicy,
    WebhookEndpointAging,
    WebhookDeliveryAging,
    WebhookAgingEvent,
)

