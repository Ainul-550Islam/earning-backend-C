# api/referral/INTEGRATION_SYSTEM/integ_registry.py
# Central registry — maps events to handlers, tracks adapters
# ============================================================

import logging
from typing import Callable, Dict, List, Optional, Any
from .integ_constants import (
    EVENT_TASK_COMPLETED, EVENT_OFFER_COMPLETED,
    EVENT_WITHDRAWAL_APPROVED, EVENT_DEPOSIT_COMPLETED,
    EVENT_USER_REGISTERED, EVENT_FRAUD_CONFIRMED,
    EVENT_USER_TIER_UPGRADED,
)

logger = logging.getLogger(__name__)


class IntegrationRegistry:
    """
    Single registry for all referral integration handlers.
    Other modules register themselves here.
    Thread-safe singleton pattern.
    """
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._handlers: Dict[str, List[Callable]] = {}
        self._adapters: Dict[str, Any] = {}
        self._module_status: Dict[str, bool] = {}
        self._initialized = True
        logger.info('[ReferralRegistry] Initialized')

    # ── Handler Registration ──────────────────────────────────────────────────

    def register_handler(self, event: str, handler: Callable, module: str = '') -> None:
        """Register a handler for a specific event."""
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)
        logger.debug(f'[Registry] Handler registered: {event} → {handler.__name__} ({module})')

    def unregister_handler(self, event: str, handler: Callable) -> bool:
        """Remove a handler."""
        if event in self._handlers:
            try:
                self._handlers[event].remove(handler)
                return True
            except ValueError:
                pass
        return False

    def get_handlers(self, event: str) -> List[Callable]:
        """Get all handlers for an event."""
        return self._handlers.get(event, [])

    # ── Adapter Registration ──────────────────────────────────────────────────

    def register_adapter(self, name: str, adapter: Any) -> None:
        """Register an integration adapter (wallet, notification, etc.)."""
        self._adapters[name] = adapter
        logger.info(f'[Registry] Adapter registered: {name}')

    def get_adapter(self, name: str) -> Optional[Any]:
        """Get registered adapter by name."""
        return self._adapters.get(name)

    def has_adapter(self, name: str) -> bool:
        return name in self._adapters

    # ── Module Status ─────────────────────────────────────────────────────────

    def set_module_available(self, module: str, available: bool) -> None:
        self._module_status[module] = available

    def is_module_available(self, module: str) -> bool:
        return self._module_status.get(module, False)

    def get_available_modules(self) -> List[str]:
        return [m for m, a in self._module_status.items() if a]

    # ── Auto-Discovery ────────────────────────────────────────────────────────

    def auto_discover_modules(self) -> Dict[str, bool]:
        """
        Try to import each module and register its availability.
        Called during app.ready().
        """
        modules_to_check = {
            'wallet': 'api.wallet.services',
            'notifications': 'api.notifications.services',
            'fraud_detection': 'api.fraud_detection.services.FraudScoreCalculator',
            'tasks': 'api.tasks.services',
            'offer_inventory': 'api.offer_inventory.models',
            'promotions': 'api.promotions.models',
            'analytics': 'api.analytics.models',
            'audit_logs': 'api.audit_logs.models',
            'djoyalty': 'api.djoyalty.models.core',
            'postback_engine': 'api.postback_engine.services',
            'rate_limit': 'api.rate_limit.services.RateLimitService',
            'admin_panel': 'api.admin_panel.models',
        }

        results = {}
        for module_name, import_path in modules_to_check.items():
            try:
                __import__(import_path)
                self.set_module_available(module_name, True)
                results[module_name] = True
            except ImportError:
                self.set_module_available(module_name, False)
                results[module_name] = False
                logger.debug(f'[Registry] Module unavailable: {module_name}')

        available = [k for k, v in results.items() if v]
        logger.info(f'[Registry] Modules available: {available}')
        return results

    def get_status(self) -> dict:
        """Registry status summary."""
        return {
            'handlers': {k: len(v) for k, v in self._handlers.items()},
            'adapters': list(self._adapters.keys()),
            'modules': self._module_status,
            'total_events': len(self._handlers),
            'total_handlers': sum(len(v) for v in self._handlers.values()),
        }


# ── Default Registrations ─────────────────────────────────────────────────────

def setup_default_handlers(registry: IntegrationRegistry) -> None:
    """
    Register all default event handlers.
    Called from integ_handler.py on app startup.
    """
    from .integ_handler import (
        handle_task_completed,
        handle_offer_completed,
        handle_withdrawal_approved,
        handle_user_registered,
        handle_fraud_confirmed,
        handle_user_tier_upgraded,
    )

    mappings = [
        (EVENT_TASK_COMPLETED,      handle_task_completed,      'tasks'),
        (EVENT_OFFER_COMPLETED,     handle_offer_completed,     'offer_inventory'),
        (EVENT_WITHDRAWAL_APPROVED, handle_withdrawal_approved, 'wallet'),
        (EVENT_USER_REGISTERED,     handle_user_registered,     'users'),
        (EVENT_FRAUD_CONFIRMED,     handle_fraud_confirmed,     'fraud_detection'),
        (EVENT_USER_TIER_UPGRADED,  handle_user_tier_upgraded,  'users'),
    ]

    for event, handler, module in mappings:
        registry.register_handler(event, handler, module)

    logger.info(f'[Registry] Default handlers registered: {len(mappings)}')


# ── Global Singleton ──────────────────────────────────────────────────────────

_registry: Optional[IntegrationRegistry] = None


def get_registry() -> IntegrationRegistry:
    """Get the global registry singleton."""
    global _registry
    if _registry is None:
        _registry = IntegrationRegistry()
    return _registry


def reset_registry() -> None:
    """Reset registry (for testing)."""
    global _registry
    _registry = None
    IntegrationRegistry._instance = None
    IntegrationRegistry._initialized = False