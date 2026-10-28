# =============================================================================
# fraud_detection/INTEGRATION_SYSTEM/integ_registry.py
# =============================================================================
from __future__ import annotations

import threading
from typing import Any, Dict, Optional


class IntegrationRegistry:
    """Simple key-value registry for named integrations."""

    def __init__(self):
        self._lock       = threading.Lock()
        self._integrations: Dict[str, Any] = {}

    def register(self, name: str, integration: Any) -> None:
        with self._lock:
            self._integrations[name] = integration

    def get(self, name: str) -> Optional[Any]:
        return self._integrations.get(name)

    def all_names(self) -> list:
        return list(self._integrations.keys())

    def unregister(self, name: str) -> bool:
        with self._lock:
            return self._integrations.pop(name, None) is not None


_registry_inst : IntegrationRegistry | None = None
_ri_lock = threading.Lock()


def get_integration_registry() -> IntegrationRegistry:
    global _registry_inst
    if _registry_inst is None:
        with _ri_lock:
            if _registry_inst is None:
                _registry_inst = IntegrationRegistry()
    return _registry_inst
