# api/djoyalty/integration_system/__init__.py
"""
Djoyalty Integration System -- 18-file Production-grade Layer।

⚡ CORE CONNECTORS
   integ_handler.py      -- Central integration handler/dispatcher
   integ_signals.py      -- Django signals -> integration events
   integ_adapter.py      -- Adapter pattern for external systems
   integ_registry.py     -- Integration registry (plug & play)
   integ_constants.py    -- All integration constants & enums

🌉 BRIDGE & BUS
   bridge.py             -- Service bridge (loyalty ↔ external)
   event_bus.py          -- Internal event bus (pub/sub)
   webhooks_integration.py -- Outbound webhook manager
   data_bridge.py        -- Data transformation & mapping
   message_queue.py      -- High traffic queue (New - High Traffic Manager)

🛡️ SECURITY & VALIDATION
   data_validator.py     -- Input/output validation
   integ_exceptions.py   -- Integration-specific exceptions
   fallback_logic.py     -- Circuit breaker & fallback
   auth_bridge.py        -- Cross-module permission (New)

📊 MONITORING & LOGS
   performance_monitor.py -- Response time & metrics
   integ_audit_logs.py   -- Integration audit trail
   health_check.py       -- Health check endpoints
   sync_manager.py       -- Data conflict resolver (New)
"""
from .integ_registry import IntegrationRegistry, registry
from .integ_handler import IntegrationHandler
from .event_bus import EventBus
from .health_check import HealthCheckService
from .bridge import LoyaltyBridge, loyalty_bridge
from .message_queue import MessageQueueManager, mq
from .sync_manager import SyncManager
from .fallback_logic import CircuitBreaker, RetryPolicy, FallbackChain
from .integ_exceptions import (
    DjoyaltyIntegrationError,
    IntegrationNotConfiguredError,
    CircuitBreakerOpenError,
    RateLimitExceededError,
)

__all__ = [
    'IntegrationRegistry', 'registry',
    'IntegrationHandler',
    'EventBus',
    'HealthCheckService',
    'LoyaltyBridge', 'loyalty_bridge',
    'MessageQueueManager', 'mq',
    'SyncManager',
    'CircuitBreaker', 'RetryPolicy', 'FallbackChain',
    'DjoyaltyIntegrationError',
    'IntegrationNotConfiguredError',
    'CircuitBreakerOpenError',
    'RateLimitExceededError',
]
