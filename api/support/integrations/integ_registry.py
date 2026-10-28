# api/support/integrations/integ_registry.py  — WORLD #1
"""
Central Integration Registry.
সব integration এক জায়গায় register করা হয়।
যেকোনো module এখান থেকে integration access করতে পারে।
"""
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class IntegrationRegistry:
    """
    Central registry for all support system integrations.
    Singleton pattern — একটাই instance থাকবে।
    
    Usage:
        registry = get_registry()
        result = registry.call('wallet', 'get_balance', user=user)
    """

    _instance: Optional['IntegrationRegistry'] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._adapters: Dict[str, Any]          = {}   # app_name → adapter instance
            self._handlers: Dict[str, Callable]      = {}   # event_type → handler list
            self._middleware: List[Callable]          = []   # middleware chain
            self._health_status: Dict[str, dict]     = {}   # app_name → {healthy, last_check}
            self._disabled: set                      = set() # disabled integration names
            self._initialized = True

    # ── Registration ─────────────────────────────────────
    def register_adapter(self, name: str, adapter) -> None:
        """Register an integration adapter for an app."""
        self._adapters[name] = adapter
        logger.debug(f'Adapter registered: {name}')

    def register_handler(self, event_type: str, handler: Callable) -> None:
        """Register an event handler."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f'Handler registered: {event_type}')

    def register_middleware(self, middleware: Callable) -> None:
        """Register middleware for all integration calls."""
        self._middleware.append(middleware)

    # ── Retrieval ─────────────────────────────────────────
    def get_adapter(self, name: str) -> Optional[Any]:
        """Get adapter by name."""
        if name in self._disabled:
            logger.warning(f'Adapter {name} is disabled.')
            return None
        return self._adapters.get(name)

    def has_adapter(self, name: str) -> bool:
        """Check if adapter is registered and enabled."""
        return name in self._adapters and name not in self._disabled

    def get_all_adapters(self) -> Dict[str, Any]:
        """Get all registered adapters."""
        return {k: v for k, v in self._adapters.items() if k not in self._disabled}

    # ── Calling ───────────────────────────────────────────
    def call(self, adapter_name: str, method: str, **kwargs) -> Any:
        """
        Call a method on an adapter with error handling.
        
        Usage:
            registry.call('wallet', 'get_balance', user=user)
            registry.call('fraud', 'get_risk_score', user=user)
        """
        adapter = self.get_adapter(adapter_name)
        if adapter is None:
            logger.warning(f'Adapter not found: {adapter_name}')
            return None

        if not hasattr(adapter, method):
            logger.warning(f'Method {method} not found on {adapter_name}')
            return None

        try:
            return getattr(adapter, method)(**kwargs)
        except Exception as e:
            logger.error(f'Integration call failed [{adapter_name}.{method}]: {e}')
            return None

    # ── Event Dispatching ─────────────────────────────────
    def dispatch(self, event_type: str, **data) -> List[Any]:
        """
        Dispatch an event to all registered handlers.
        
        Usage:
            registry.dispatch('support.ticket.created', ticket=ticket, user=user)
        """
        handlers = self._handlers.get(event_type, [])
        results  = []

        for handler in handlers:
            try:
                result = handler(event_type=event_type, **data)
                results.append(result)
            except Exception as e:
                logger.error(f'Handler failed [{event_type}]: {e}')

        if not handlers:
            logger.debug(f'No handlers for event: {event_type}')

        return results

    # ── Health Management ─────────────────────────────────
    def set_health(self, name: str, healthy: bool, details: dict = None) -> None:
        """Update health status of an integration."""
        from django.utils import timezone
        self._health_status[name] = {
            'healthy':    healthy,
            'details':    details or {},
            'last_check': timezone.now().isoformat(),
        }

    def get_health(self, name: str) -> dict:
        """Get health status of an integration."""
        return self._health_status.get(name, {'healthy': None, 'last_check': None})

    def get_all_health(self) -> Dict[str, dict]:
        """Get all health statuses."""
        return dict(self._health_status)

    # ── Enable / Disable ──────────────────────────────────
    def disable(self, name: str, reason: str = '') -> None:
        """Disable an integration."""
        self._disabled.add(name)
        logger.warning(f'Integration disabled: {name} — {reason}')

    def enable(self, name: str) -> None:
        """Re-enable a disabled integration."""
        self._disabled.discard(name)
        logger.info(f'Integration enabled: {name}')

    def is_enabled(self, name: str) -> bool:
        return name not in self._disabled and name in self._adapters

    # ── Summary ───────────────────────────────────────────
    def summary(self) -> dict:
        """Get registry summary — useful for admin/health endpoints."""
        return {
            'total_adapters': len(self._adapters),
            'enabled':        [k for k in self._adapters if k not in self._disabled],
            'disabled':       list(self._disabled),
            'event_types':    list(self._handlers.keys()),
            'middleware':     len(self._middleware),
        }

    def __repr__(self):
        return f'<IntegrationRegistry adapters={len(self._adapters)} events={len(self._handlers)}>'


# ── Singleton accessor ────────────────────────────────
_registry: Optional[IntegrationRegistry] = None


def get_registry() -> IntegrationRegistry:
    """Get the global integration registry instance."""
    global _registry
    if _registry is None:
        _registry = IntegrationRegistry()
    return _registry


def reset_registry() -> None:
    """Reset registry — for testing only."""
    global _registry
    _registry = None
    IntegrationRegistry._instance = None
    IntegrationRegistry._initialized = False