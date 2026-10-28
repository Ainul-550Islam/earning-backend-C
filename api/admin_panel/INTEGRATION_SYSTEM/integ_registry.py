# api/admin_panel/INTEGRATION_SYSTEM/integ_registry.py
"""
IntegrationRegistry — Central registry for all app integrations.

Every app that the admin_panel can control MUST register itself here.
Registry stores: app name, status, capabilities, health, adapter reference.

Usage:
    from api.admin_panel.INTEGRATION_SYSTEM.integ_registry import IntegrationRegistry

    # Register an app
    IntegrationRegistry.register('wallet', WalletAdapter, capabilities=['read', 'write', 'adjust'])

    # Get adapter
    adapter = IntegrationRegistry.get_adapter('wallet')

    # Check app health
    health = IntegrationRegistry.health_check('wallet')
"""
import logging
from typing import Any, Dict, List, Optional, Type
from django.core.cache import cache
from django.utils import timezone
from .integ_constants import INTEGRATION_APPS, HEALTH_STATUSES, TIMEOUTS

logger = logging.getLogger(__name__)


class AppRegistration:
    """Represents a single registered app in the integration system."""

    def __init__(
        self,
        app_name: str,
        adapter_class: Optional[Type] = None,
        capabilities: Optional[List[str]] = None,
        version: str = '1.0.0',
        description: str = '',
    ):
        self.app_name = app_name
        self.adapter_class = adapter_class
        self._adapter_instance = None
        self.capabilities = capabilities or ['read']
        self.version = version
        self.description = description
        self.registered_at = timezone.now()
        self.health_status = HEALTH_STATUSES['UNKNOWN']
        self.last_health_check = None
        self.error_count = 0
        self.is_active = True

    @property
    def adapter(self):
        """Lazy-load adapter instance."""
        if self._adapter_instance is None and self.adapter_class:
            try:
                self._adapter_instance = self.adapter_class()
            except Exception as e:
                logger.error(f"[IntegrationRegistry] Failed to init adapter for {self.app_name}: {e}")
        return self._adapter_instance

    def can(self, capability: str) -> bool:
        return capability in self.capabilities

    def to_dict(self) -> Dict:
        return {
            'app_name': self.app_name,
            'capabilities': self.capabilities,
            'version': self.version,
            'description': self.description,
            'health_status': self.health_status,
            'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None,
            'error_count': self.error_count,
            'is_active': self.is_active,
            'registered_at': self.registered_at.isoformat(),
        }


class IntegrationRegistryMeta(type):
    """Metaclass to make IntegrationRegistry a true singleton."""
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class IntegrationRegistry(metaclass=IntegrationRegistryMeta):
    """
    Central registry for all 50 app integrations.
    Singleton — one global registry per process.
    """

    def __init__(self):
        self._registry: Dict[str, AppRegistration] = {}
        self._hooks: Dict[str, List] = {}  # event_type -> [callback, ...]
        self._initialized = False

    def register(
        self,
        app_name: str,
        adapter_class: Optional[Type] = None,
        capabilities: Optional[List[str]] = None,
        version: str = '1.0.0',
        description: str = '',
        overwrite: bool = False,
    ) -> AppRegistration:
        """Register an app with the integration system."""
        if app_name in self._registry and not overwrite:
            logger.debug(f"[IntegrationRegistry] {app_name} already registered.")
            return self._registry[app_name]

        registration = AppRegistration(
            app_name=app_name,
            adapter_class=adapter_class,
            capabilities=capabilities,
            version=version,
            description=description,
        )
        self._registry[app_name] = registration
        logger.info(f"[IntegrationRegistry] Registered: {app_name} caps={capabilities}")
        return registration

    def unregister(self, app_name: str) -> bool:
        """Remove an app from the registry."""
        if app_name in self._registry:
            del self._registry[app_name]
            logger.warning(f"[IntegrationRegistry] Unregistered: {app_name}")
            return True
        return False

    def get_adapter(self, app_name: str) -> Optional[Any]:
        """Get the adapter instance for an app."""
        reg = self._registry.get(app_name)
        if not reg:
            logger.warning(f"[IntegrationRegistry] App not registered: {app_name}")
            return None
        if not reg.is_active:
            logger.warning(f"[IntegrationRegistry] App is disabled: {app_name}")
            return None
        return reg.adapter

    def get_registration(self, app_name: str) -> Optional[AppRegistration]:
        return self._registry.get(app_name)

    def is_registered(self, app_name: str) -> bool:
        return app_name in self._registry

    def can_do(self, app_name: str, capability: str) -> bool:
        """Check if an app supports a given capability."""
        reg = self._registry.get(app_name)
        return reg.can(capability) if reg else False

    def list_apps(self, active_only: bool = False) -> List[str]:
        """List all registered app names."""
        if active_only:
            return [name for name, reg in self._registry.items() if reg.is_active]
        return list(self._registry.keys())

    def list_registrations(self) -> List[Dict]:
        """Full list of all registrations with status."""
        return [reg.to_dict() for reg in self._registry.values()]

    def enable_app(self, app_name: str) -> bool:
        reg = self._registry.get(app_name)
        if reg:
            reg.is_active = True
            return True
        return False

    def disable_app(self, app_name: str) -> bool:
        reg = self._registry.get(app_name)
        if reg:
            reg.is_active = False
            return True
        return False

    # ==================== HOOKS ====================

    def register_hook(self, event_type: str, callback) -> None:
        """Register a callback for an event type."""
        if event_type not in self._hooks:
            self._hooks[event_type] = []
        self._hooks[event_type].append(callback)
        logger.debug(f"[IntegrationRegistry] Hook registered: {event_type}")

    def fire_hooks(self, event_type: str, payload: Dict) -> int:
        """Fire all registered hooks for an event. Returns count fired."""
        hooks = self._hooks.get(event_type, [])
        fired = 0
        for callback in hooks:
            try:
                callback(event_type=event_type, payload=payload)
                fired += 1
            except Exception as e:
                logger.error(f"[IntegrationRegistry] Hook error for {event_type}: {e}")
        return fired

    # ==================== HEALTH ====================

    def health_check_all(self) -> Dict[str, str]:
        """Run health check on all registered apps. Returns dict of app->status."""
        results = {}
        for app_name, reg in self._registry.items():
            if not reg.is_active:
                results[app_name] = HEALTH_STATUSES['UNKNOWN']
                continue
            try:
                adapter = reg.adapter
                if adapter and hasattr(adapter, 'health_check'):
                    status = adapter.health_check()
                else:
                    # Check if the app module is importable
                    import importlib
                    try:
                        importlib.import_module(f'api.{app_name}')
                        status = HEALTH_STATUSES['HEALTHY']
                    except ImportError:
                        status = HEALTH_STATUSES['UNKNOWN']
                reg.health_status = status
                reg.last_health_check = timezone.now()
                reg.error_count = 0
            except Exception as e:
                reg.health_status = HEALTH_STATUSES['DOWN']
                reg.error_count += 1
                logger.error(f"[IntegrationRegistry] Health check failed for {app_name}: {e}")
                status = HEALTH_STATUSES['DOWN']
            results[app_name] = status

        # Cache results
        cache.set('admin_panel:integration_health', results, TIMEOUTS['CACHE_TTL_MEDIUM'])
        return results

    def get_health_summary(self) -> Dict:
        """Get cached or fresh health summary."""
        cached = cache.get('admin_panel:integration_health')
        if cached:
            return cached
        return self.health_check_all()

    def get_system_status(self) -> str:
        """Overall system status — healthy/degraded/down."""
        health = self.get_health_summary()
        if not health:
            return HEALTH_STATUSES['UNKNOWN']
        values = list(health.values())
        if all(v == HEALTH_STATUSES['HEALTHY'] for v in values):
            return HEALTH_STATUSES['HEALTHY']
        if any(v == HEALTH_STATUSES['DOWN'] for v in values):
            return HEALTH_STATUSES['DEGRADED']
        return HEALTH_STATUSES['DEGRADED']

    # ==================== AUTO-DISCOVER ====================

    def auto_discover(self) -> int:
        """
        Auto-discover and register all apps that have an IntegrationAdapter.
        Looks for api/<app>/integration_adapter.py.
        """
        import importlib
        discovered = 0
        for app_name in INTEGRATION_APPS:
            if self.is_registered(app_name):
                continue
            try:
                module = importlib.import_module(f'api.{app_name}.integration_adapter')
                adapter_class = getattr(module, 'IntegrationAdapter', None)
                caps = getattr(module, 'CAPABILITIES', ['read'])
                desc = getattr(module, 'DESCRIPTION', '')
                self.register(app_name, adapter_class=adapter_class, capabilities=caps, description=desc)
                discovered += 1
            except ImportError:
                # App doesn't have an integration adapter — register with no adapter
                self.register(app_name, capabilities=['read'], description=f'Auto-registered: {app_name}')
        logger.info(f"[IntegrationRegistry] Auto-discovered {discovered} new apps.")
        return discovered

    def __repr__(self) -> str:
        return f"<IntegrationRegistry apps={len(self._registry)} active={len(self.list_apps(active_only=True))}>"


# Global singleton instance
registry = IntegrationRegistry()