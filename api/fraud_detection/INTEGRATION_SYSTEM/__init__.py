# =============================================================================
# fraud_detection/INTEGRATION_SYSTEM/__init__.py
# =============================================================================
"""
Fraud Detection Integration System Package.

Exports all public classes and factory functions so any module can do:

    from api.fraud_detection.INTEGRATION_SYSTEM import get_integration_handler
    from api.fraud_detection.INTEGRATION_SYSTEM import get_event_bus
    from api.fraud_detection.INTEGRATION_SYSTEM import run_health_checks
"""
from __future__ import annotations

# ── Health checks ─────────────────────────────────────────────────────────────
try:
    from api.fraud_detection.INTEGRATION_SYSTEM.health_check import (
        run_health_checks,
        get_system_health_status,
        get_health_statistics,
        check_integration_health,
    )
except ImportError:
    pass

# ── Performance monitor ───────────────────────────────────────────────────────
try:
    from api.fraud_detection.INTEGRATION_SYSTEM.performance_monitor import (
        get_performance_metrics,
        get_performance_alerts,
        get_performance_statistics,
        record_request,
    )
except ImportError:
    pass

# ── Integration handler ───────────────────────────────────────────────────────
try:
    from api.fraud_detection.INTEGRATION_SYSTEM.integ_handler import (
        get_integration_handler,
        execute_integration,
    )
except ImportError:
    pass

# ── Integration registry ──────────────────────────────────────────────────────
try:
    from api.fraud_detection.INTEGRATION_SYSTEM.integ_registry import (
        get_integration_registry,
    )
except ImportError:
    pass

# ── Circuit breaker ───────────────────────────────────────────────────────────
try:
    from api.fraud_detection.INTEGRATION_SYSTEM.circuit_breaker import (
        get_circuit_breaker_registry,
        get_circuit_breaker_status,
        reset_circuit_breaker,
    )
except ImportError:
    pass

# ── Event bus ─────────────────────────────────────────────────────────────────
try:
    from api.fraud_detection.INTEGRATION_SYSTEM.event_bus import (
        get_event_bus,
        Event,
        EventType,
    )
except ImportError:
    pass

# ── Message queue ─────────────────────────────────────────────────────────────
try:
    from api.fraud_detection.INTEGRATION_SYSTEM.message_queue import (
        get_message_queue_manager,
        publish_message,
        get_queue_statistics,
    )
except ImportError:
    pass

# ── Audit logs ────────────────────────────────────────────────────────────────
try:
    from api.fraud_detection.INTEGRATION_SYSTEM.integ_audit_logs import (
        get_audit_logger,
        get_audit_statistics,
    )
except ImportError:
    pass

# ── Sync manager ──────────────────────────────────────────────────────────────
try:
    from api.fraud_detection.INTEGRATION_SYSTEM.sync_manager import (
        get_sync_manager,
        create_sync_operation,
        execute_sync,
        get_sync_statistics,
    )
except ImportError:
    pass

# ── Fraud adapter ─────────────────────────────────────────────────────────────
try:
    from api.fraud_detection.INTEGRATION_SYSTEM.fraud_adapter import (
        FraudDetectionAdapter,
    )
except ImportError:
    pass

__all__ = [
    # health
    'run_health_checks', 'get_system_health_status',
    'get_health_statistics', 'check_integration_health',
    # performance
    'get_performance_metrics', 'get_performance_alerts',
    'get_performance_statistics', 'record_request',
    # handler
    'get_integration_handler', 'execute_integration',
    # registry
    'get_integration_registry',
    # circuit breaker
    'get_circuit_breaker_registry', 'get_circuit_breaker_status', 'reset_circuit_breaker',
    # event bus
    'get_event_bus', 'Event', 'EventType',
    # queue
    'get_message_queue_manager', 'publish_message', 'get_queue_statistics',
    # audit
    'get_audit_logger', 'get_audit_statistics',
    # sync
    'get_sync_manager', 'create_sync_operation', 'execute_sync', 'get_sync_statistics',
    # adapter
    'FraudDetectionAdapter',
]
