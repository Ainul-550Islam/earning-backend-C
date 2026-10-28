# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Webhooks Services Package

FIX: Removed bare except-swallowing try/except blocks that silently set
services to None on import failure. All imports now raise on error so
misconfiguration is immediately visible rather than producing mysterious
AttributeError: 'NoneType' has no attribute '...' at call time.
"""

# ── Core services ─────────────────────────────────────────────────────────────
from .core.DispatchService import DispatchService
from .core.SignatureEngine import SignatureEngine
from .core.SecretRotationService import SecretRotationService
from .core.EndpointHealthService import EndpointHealthService

# ── Filtering services ────────────────────────────────────────────────────────
from .filtering.EventRouter import EventRouter
from .filtering.FilterService import FilterService
from .filtering.PayloadTransformer import PayloadTransformer

# ── Inbound services ──────────────────────────────────────────────────────────
from .inbound.InboundWebhookService import InboundWebhookService
from .inbound.SignatureVerifier import SignatureVerifier
from .inbound.PayloadParser import PayloadParser
from .inbound.InboundEventRouter import InboundEventRouter

# ── Batch services ────────────────────────────────────────────────────────────
from .batch.BatchDispatchService import BatchDispatchService
from .batch.BatchStatusService import BatchStatusService

# ── Analytics services ────────────────────────────────────────────────────────
from .analytics.WebhookAnalyticsService import WebhookAnalyticsService
from .analytics.AgingService import AgingService
from .analytics.RateLimiterService import RateLimiterService
from .analytics.HealthMonitorService import HealthMonitorService

__all__ = [
    # Core
    "DispatchService",
    "SignatureEngine",
    "SecretRotationService",
    "EndpointHealthService",
    # Filtering
    "FilterService",
    "PayloadTransformer",
    "EventRouter",
    # Inbound
    "InboundWebhookService",
    "SignatureVerifier",
    "PayloadParser",
    "InboundEventRouter",
    # Batch
    "BatchDispatchService",
    "BatchStatusService",
    # Analytics
    "AgingService",
    "WebhookAnalyticsService",
    "RateLimiterService",
    "HealthMonitorService",
]
