"""Webhooks Services Module

This module contains all services for the webhooks system,
including core services, filtering, inbound processing, analytics, and replay functionality.
"""

# Export all services for easy access
__all__ = [
    # Core Services
    'SignatureEngine',
    'DispatchService',
    'SecretRotationService',
    'EndpointHealthService',
    
    # Filtering Services
    'FilterService',
    'PayloadTransformer',
    'EventRouter',
    
    # Inbound Services
    'InboundWebhookService',
    'SignatureVerifier',
    'PayloadParser',
    'InboundEventRouter',
    
    # Batch Services
    'BatchDispatchService',
    'BatchStatusService',
    
    # Analytics Services
    'WebhookAnalyticsService',
    'RateLimiterService',
    'HealthMonitorService',
    
    # Replay Services
    'ReplayService',
    'ReplayValidatorService',
]

# Actual imports so `from .services import X` works
try:
    from .core.DispatchService import DispatchService
except Exception:
    DispatchService = None

try:
    from .core.SignatureEngine import SignatureEngine
except Exception:
    SignatureEngine = None

try:
    from .core.SecretRotationService import SecretRotationService
except Exception:
    SecretRotationService = None

try:
    from .core.EndpointHealthService import EndpointHealthService
except Exception:
    EndpointHealthService = None

try:
    from .filtering.EventRouter import EventRouter
except Exception:
    EventRouter = None

try:
    from .analytics.HealthMonitorService import HealthMonitorService
except Exception:
    HealthMonitorService = None

try:
    from .analytics.RateLimiterService import RateLimiterService
except Exception:
    RateLimiterService = None
