"""
INTEGRATION_SYSTEM Wiring
=========================
This module is the single entry point that wires INTEGRATION_SYSTEM components
into the gamification app. Import from here, never directly from sub-modules.

Usage in services:
    from api.gamification.INTEGRATION_SYSTEM.wiring import (
        gamification_circuit_breaker, gamification_health_manager,
        gamification_event_bus, call_with_circuit_breaker,
    )
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CircuitBreaker — protects all external adapter calls
# ---------------------------------------------------------------------------
try:
    from api.gamification.INTEGRATION_SYSTEM.circuit_breaker import (
        StandardCircuitBreaker, CircuitBreakerConfig, CircuitBreakerRegistry,
    )

    _cb_config = CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=30,
        half_open_max_calls=3,
    )
    _cb_registry = CircuitBreakerRegistry()
    gamification_circuit_breaker: Optional[StandardCircuitBreaker] = StandardCircuitBreaker(
        name="gamification_external", config=_cb_config
    )
    _cb_registry.register("gamification_external", gamification_circuit_breaker)
    logger.info("CircuitBreaker wired: gamification_external")
except Exception as exc:
    gamification_circuit_breaker = None
    logger.warning("CircuitBreaker unavailable: %s", exc)


def call_with_circuit_breaker(fn: Callable, *args: Any, fallback: Any = None, **kwargs: Any) -> Any:
    """
    Execute fn(*args, **kwargs) protected by the gamification circuit breaker.
    If the circuit is open or fn raises, return fallback instead of propagating.
    """
    if gamification_circuit_breaker is None:
        return fn(*args, **kwargs)
    try:
        return gamification_circuit_breaker.call(fn, *args, **kwargs)
    except Exception as exc:
        logger.warning("circuit_breaker blocked call to %s: %s", getattr(fn, "__name__", fn), exc)
        return fallback


# ---------------------------------------------------------------------------
# HealthManager — used by GamificationHealthView
# ---------------------------------------------------------------------------
try:
    from api.gamification.INTEGRATION_SYSTEM.health_check import (
        HealthManager, HealthCheck, CheckType, Severity,
    )

    gamification_health_manager: Optional[HealthManager] = HealthManager()

    # Register database connectivity check
    _db_check = HealthCheck(
        name="gamification_db",
        check_type=CheckType.CONNECTIVITY,
        severity=Severity.CRITICAL,
        metadata={"description": "Gamification database connectivity"},
    )
    gamification_health_manager.register_check(_db_check)
    logger.info("HealthManager wired with db check")
except Exception as exc:
    gamification_health_manager = None
    logger.warning("HealthManager unavailable: %s", exc)


def run_health_checks() -> dict:
    """
    Run all registered health checks and return a status dict.
    Used by GamificationHealthView to enrich its response.
    """
    if gamification_health_manager is None:
        return {"integration_system": "unavailable"}
    try:
        results = gamification_health_manager.run_all_checks()
        return {
            "integration_system": "ok",
            "checks": {r.name: r.status.value for r in results} if hasattr(results, "__iter__") else {},
        }
    except Exception as exc:
        logger.warning("health check run failed: %s", exc)
        return {"integration_system": "error", "detail": str(exc)}


# ---------------------------------------------------------------------------
# EventBus — used by receivers to publish domain events
# ---------------------------------------------------------------------------
try:
    from api.gamification.INTEGRATION_SYSTEM.event_bus import (
        InMemoryEventBus, Event, EventType, EventPriority,
    )

    gamification_event_bus: Optional[InMemoryEventBus] = InMemoryEventBus()
    logger.info("EventBus wired: InMemoryEventBus")
except Exception as exc:
    gamification_event_bus = None
    logger.warning("EventBus unavailable: %s", exc)


def publish_domain_event(event_type: str, payload: dict, priority: str = "normal") -> bool:
    """
    Publish a domain event to the gamification event bus.
    Returns True on success, False on failure (non-raising).
    """
    if gamification_event_bus is None:
        return False
    try:
        event = Event(event_type=event_type, payload=payload)
        return gamification_event_bus.publish(event)
    except Exception as exc:
        logger.warning("publish_domain_event failed for %s: %s", event_type, exc)
        return False


# ---------------------------------------------------------------------------
# PerformanceMonitor — tracks service layer timing
# ---------------------------------------------------------------------------
try:
    from api.gamification.INTEGRATION_SYSTEM.performance_monitor import PerformanceMonitor

    gamification_perf_monitor: Optional[PerformanceMonitor] = PerformanceMonitor(
        name="gamification_services"
    )
    logger.info("PerformanceMonitor wired")
except Exception as exc:
    gamification_perf_monitor = None
    logger.warning("PerformanceMonitor unavailable: %s", exc)


def record_service_metric(metric_name: str, value: float, tags: Optional[dict] = None) -> None:
    """Record a service performance metric. Non-raising."""
    if gamification_perf_monitor is None:
        return
    try:
        gamification_perf_monitor.record(metric_name, value, tags=tags or {})
    except Exception as exc:
        logger.debug("record_service_metric failed: %s", exc)
