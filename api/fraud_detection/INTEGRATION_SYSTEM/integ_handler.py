# =============================================================================
# fraud_detection/INTEGRATION_SYSTEM/integ_handler.py
# =============================================================================
from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger('fraud_detection.integ_handler')


class IntegrationHandler:
    """
    Dispatches named integration calls through registered adapters,
    wrapping each in the circuit breaker if one is registered.
    """

    def __init__(self):
        self._lock     = threading.Lock()
        self._adapters : Dict[str, Callable] = {}

    def register_adapter(self, name: str, adapter: Callable) -> None:
        with self._lock:
            self._adapters[name] = adapter
        logger.debug('IntegrationHandler: registered adapter %r', name)

    def execute(
        self,
        integration_name : str,
        operation        : str,
        payload          : Dict[str, Any] | None = None,
        use_circuit_breaker: bool = True,
    ) -> Any:
        adapter = self._adapters.get(integration_name)
        if adapter is None:
            logger.warning('No adapter for integration %r', integration_name)
            return {'status': 'no_adapter', 'integration': integration_name}

        call = lambda: adapter(operation=operation, payload=payload or {})

        if use_circuit_breaker:
            try:
                from api.fraud_detection.INTEGRATION_SYSTEM.circuit_breaker import (
                    get_circuit_breaker_registry,
                )
                cb = get_circuit_breaker_registry().get_or_create(integration_name)
                return cb.call(call)
            except Exception as exc:
                logger.error('IntegrationHandler.execute failed [%s.%s]: %s',
                             integration_name, operation, exc)
                return {'status': 'error', 'error': str(exc)}
        else:
            return call()


_handler : IntegrationHandler | None = None
_h_lock = threading.Lock()


def get_integration_handler() -> IntegrationHandler:
    global _handler
    if _handler is None:
        with _h_lock:
            if _handler is None:
                _handler = IntegrationHandler()
    return _handler


def execute_integration(name: str, operation: str, payload: dict | None = None) -> Any:
    return get_integration_handler().execute(name, operation, payload)
