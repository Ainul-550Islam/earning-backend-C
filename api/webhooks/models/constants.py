"""
Model-layer constants — thin re-export shim.

CONSOLIDATION (this audit): this file used to independently define
WebhookStatus, DeliveryStatus, BatchStatus, FilterOperator, InboundSource,
ReplayStatus, and ErrorType, each also defined separately in ../choices.py
(and DeliveryStatus a third time in ../constants.py). Several of these had
genuinely diverged in value, not just duplicated:
  - FilterOperator.GREATER_THAN/LESS_THAN were 'gt'/'lt' in choices.py vs
    'greater_than'/'less_than' here (and in the real migrated DB schema) -
    services/filtering/FilterService.py imported choices.py's version,
    so gt/lt filter evaluation was silently always False.
  - ReplayStatus here had CANCELLED; choices.py's didn't. WebhookReplayViewSet
    imports choices.py's version (via ../constants.py's re-export) and sets
    status=ReplayStatus.CANCELLED on cancel — confirmed AttributeError on
    every real call.
  - WebhookStatus here had INACTIVE instead of choices.py's DISABLED, which
    actually governs the real WebhookEndpoint.status field (models/core.py
    imports from ../choices.py directly) — admin/subscription_admin.py's
    color-map used this file's INACTIVE and silently never matched.
  - ErrorType here (SIGNATURE_ERROR/SYSTEM_ERROR, for InboundWebhookError)
    and choices.py's (AUTHENTICATION_ERROR/AUTHORIZATION_ERROR/
    RATE_LIMIT_ERROR/SERVER_ERROR, dispatch-oriented) were disjoint sets.

../choices.py is now the single owner, merged to the union of values found
in real use across both. This file re-exports so every existing `from
.constants import X` within models/ keeps working unchanged.
"""

from ..choices import (
    WebhookStatus,
    DeliveryStatus,
    BatchStatus,
    FilterOperator,
    InboundSource,
    ReplayStatus,
    ErrorType,
)

__all__ = [
    "WebhookStatus",
    "DeliveryStatus",
    "BatchStatus",
    "FilterOperator",
    "InboundSource",
    "ReplayStatus",
    "ErrorType",
    "HTTP_METHOD_CHOICES",
    "DEFAULT_TIMEOUT_SECONDS",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_RATE_LIMIT_PER_MIN",
    "DEFAULT_BATCH_SIZE",
]

HTTP_METHOD_CHOICES = [
    ('POST', 'POST'),
    ('PUT', 'PUT'),
    ('PATCH', 'PATCH'),
]

# Default values
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_RATE_LIMIT_PER_MIN = 60
DEFAULT_BATCH_SIZE = 100
