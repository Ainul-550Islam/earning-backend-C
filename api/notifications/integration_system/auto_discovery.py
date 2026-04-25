# api/notifications/integration_system/auto_discovery.py
"""
Auto-Discovery Engine — Zero-config module integration.

When a new Django app is added to INSTALLED_APPS, this engine:
  1. Scans for `integ_config.py` in each app
  2. Reads the ModuleConfig class
  3. Auto-wires Django signals → EventBus
  4. Auto-subscribes EventBus events → Notification triggers
  5. Auto-registers adapters in the registry
  6. Auto-grants cross-module permissions
  7. Auto-registers health checks
  8. Auto-maps webhook handlers

The developer's ONLY job:
  - Create `your_app/integ_config.py`
  - Define ModuleConfig with signal_maps and event_maps
  - Done. Everything else is automatic.

Usage (called once from notifications/apps.py ready()):
    from api.notifications.integration_system.auto_discovery import auto_discovery
    auto_discovery.discover_all()
"""

import importlib
import logging
import threading
from typing import Any, Dict, List, Optional, Set, Type

from django.apps import apps
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .integ_constants import HealthStatus, IntegPriority
from .module_protocol import ModuleConfig, SignalMap, EventMap, WebhookMap, HealthCheck

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Default Adapter for auto-discovered modules
# ---------------------------------------------------------------------------

class DefaultModuleAdapter:
    """
    A generic adapter that is auto-created for any module that doesn't
    provide a custom adapter_class in its ModuleConfig.

    It wraps the module's standard service pattern:
      - Looks for `{app}.services.{Module}Service`
      - Falls back to a passthrough that logs the call
    """

    def __init__(self, module_name: str, config: Dict = None):
        self.module_name = module_name
        self.config = config or {}
        self._service = None

    def send(self, payload: Dict, **kwargs) -> Dict:
        """Generic send — delegates to module's service if available."""
        service = self._get_service()
        if service and hasattr(service, 'handle_integration_event'):
            try:
                result = service.handle_integration_event(payload)
                return {'success': True, 'data': result or {}, 'error': ''}
            except Exception as exc:
                return {'success': False, 'data': {}, 'error': str(exc)}
        # Passthrough — log the call
        logger.debug(f'DefaultModuleAdapter[{self.module_name}]: {payload.get("action", "event")}')
        return {'success': True, 'data': payload, 'error': ''}

    def health_check(self) -> HealthStatus:
        service = self._get_service()
        if service and hasattr(service, 'health_check'):
            try:
                return service.health_check()
            except Exception:
                return HealthStatus.UNKNOWN
        return HealthStatus.UNKNOWN

    def _get_service(self):
        if self._service is not None:
            return self._service
        try:
            module_name = self.module_name
            # Try importing the module's service
            svc_module = importlib.import_module(f'{module_name}.services')
            # Look for a singleton named e.g. 'offers_service', 'payment_service'
            for attr in dir(svc_module):
                if attr.endswith('_service') or attr.endswith('Service'):
                    self._service = getattr(svc_module, attr)
                    break
        except ImportError:
            pass
        return self._service


# ---------------------------------------------------------------------------
# Auto-Discovery Engine
# ---------------------------------------------------------------------------

class AutoDiscovery:
    """
    Scans all INSTALLED_APPS for integ_config.py and auto-wires integrations.
    Thread-safe. Idempotent (safe to call multiple times).
    """

    INTEG_CONFIG_MODULE = 'integ_config'
    _lock = threading.Lock()
    _discovered: Set[str] = set()

    def __init__(self):
        self._configs: Dict[str, Type[ModuleConfig]] = {}

    def discover_all(self) -> Dict[str, bool]:
        """
        Scan all INSTALLED_APPS for integ_config.py and wire them.

        Returns:
            Dict mapping app_name → success (True/False)
        """
        results = {}
        for app_config in apps.get_app_configs():
            app_name = app_config.name
            if app_name in self._discovered:
                results[app_name] = True
                continue
            try:
                success = self._discover_app(app_config)
                results[app_name] = success
            except Exception as exc:
                logger.warning(f'AutoDiscovery: error scanning "{app_name}": {exc}')
                results[app_name] = False
        return results

    def discover_app(self, app_name: str) -> bool:
        """
        Discover and wire a single app by name.
        Useful when an app is enabled dynamically.
        """
        try:
            app_config = apps.get_app_config(app_name.split('.')[-1])
            return self._discover_app(app_config)
        except Exception as exc:
            logger.warning(f'AutoDiscovery.discover_app "{app_name}": {exc}')
            return False

    def _discover_app(self, app_config) -> bool:
        """Try to load integ_config.py from an app and wire it."""
        app_name = app_config.name

        # Try to import integ_config from the app
        try:
            config_module = importlib.import_module(f'{app_name}.{self.INTEG_CONFIG_MODULE}')
        except ImportError:
            return False  # No integ_config.py — skip silently
        except Exception as exc:
            logger.warning(f'AutoDiscovery: failed to import {app_name}.integ_config: {exc}')
            return False

        # Find the ModuleConfig subclass in the module
        module_config_class = None
        for attr_name in dir(config_module):
            attr = getattr(config_module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, ModuleConfig)
                and attr is not ModuleConfig
                and getattr(attr, 'module_name', '')
            ):
                module_config_class = attr
                break

        if not module_config_class:
            logger.debug(f'AutoDiscovery: {app_name}.integ_config has no ModuleConfig subclass')
            return False

        # Validate config
        errors = module_config_class.validate()
        if errors:
            logger.error(
                f'AutoDiscovery: {app_name} config validation failed: {errors}'
            )
            return False

        # Wire everything
        with self._lock:
            if app_name in self._discovered:
                return True
            self._wire_module(module_config_class)
            self._configs[module_config_class.module_name] = module_config_class
            self._discovered.add(app_name)

        logger.info(f'AutoDiscovery: ✅ "{module_config_class.module_name}" auto-registered')
        return True

    def _wire_module(self, config: Type[ModuleConfig]):
        """Wire all aspects of a discovered module."""
        module_name = config.module_name

        # 1. Register adapter
        self._register_adapter(config)

        # 2. Wire Django model signals → EventBus
        for signal_map in config.signal_maps:
            self._wire_signal(signal_map, module_name)

        # 3. Subscribe EventBus events → Notifications
        for event_map in config.event_maps:
            self._wire_event_subscription(event_map, module_name)

        # 4. Register webhook handlers
        for webhook_map in config.webhook_maps:
            self._wire_webhook(webhook_map, module_name)

        # 5. Grant cross-module permissions
        self._grant_permissions(config)

        # 6. Register health checks
        for health_check in config.health_checks:
            self._register_health_check(health_check, module_name)

        # 7. Call on_registered hook
        try:
            config.on_registered()
        except Exception as exc:
            logger.warning(f'AutoDiscovery: on_registered "{module_name}": {exc}')

    # ------------------------------------------------------------------
    # 1. Adapter Registration
    # ------------------------------------------------------------------

    def _register_adapter(self, config: Type[ModuleConfig]):
        """Auto-register the module's adapter in the registry."""
        from .integ_registry import registry

        adapter_class = config.get_adapter_class()

        # Wrap DefaultModuleAdapter with module_name if needed
        if adapter_class is DefaultModuleAdapter:
            module_name = config.module_name
            class _SpecificAdapter(DefaultModuleAdapter):
                def __init__(self, cfg=None):
                    super().__init__(module_name, cfg or config.adapter_config)
                def health_check(self):
                    return self._run_health_check(config)
                def _run_health_check(self, cfg):
                    for hc in cfg.health_checks:
                        if hc.model_path:
                            try:
                                app_label, model_name = hc.model_path.split('.')
                                Model = apps.get_model(app_label, model_name)
                                Model.objects.first()
                                return HealthStatus.HEALTHY
                            except Exception:
                                return HealthStatus.UNHEALTHY
                    return HealthStatus.UNKNOWN
            _SpecificAdapter.__name__ = f'{config.module_name.title()}Adapter'
            adapter_class = _SpecificAdapter

        registry.register(
            name=config.module_name,
            adapter_class=adapter_class,
            description=config.description,
            version=config.version,
            enabled=config.enabled,
            config=config.adapter_config,
            overwrite=True,
        )

    # ------------------------------------------------------------------
    # 2. Signal Wiring
    # ------------------------------------------------------------------

    def _wire_signal(self, signal_map: SignalMap, module_name: str):
        """Wire a Django post_save signal to an EventBus publish."""
        try:
            app_label, model_name = signal_map.model_path.split('.', 1)
            Model = apps.get_model(app_label, model_name)
        except (LookupError, ValueError):
            logger.debug(
                f'AutoDiscovery: model "{signal_map.model_path}" not found '
                f'(module "{module_name}") — signal not wired'
            )
            return

        from .event_bus import event_bus

        # Capture loop variable
        _sm = signal_map
        _mod = module_name

        def _signal_handler(sender, instance, created, **kwargs):
            # Check if we should trigger
            if _sm.on_created and not created:
                return
            if not _sm.on_update and not created:
                return

            current_val = getattr(instance, _sm.field, None)
            if current_val != _sm.value:
                return

            # Check update_fields optimization
            update_fields = kwargs.get('update_fields')
            if update_fields and _sm.field not in update_fields and not created:
                return

            # Apply optional condition function
            if _sm.condition_fn:
                try:
                    if not _sm.condition_fn(instance):
                        return
                except Exception:
                    return

            # Extract event data
            data = {'_source_model': _sm.model_path, '_triggered_by': _sm.field}
            for field_name in _sm.data_fields:
                val = getattr(instance, field_name, None)
                if val is not None:
                    data[field_name] = str(val) if hasattr(val, 'pk') else val

            # Resolve user_id
            user_id = None
            if _sm.user_field:
                user_id = getattr(instance, _sm.user_field, None)
                if user_id is None and _sm.user_field == 'user_id':
                    user = getattr(instance, 'user', None)
                    user_id = getattr(user, 'pk', None)

            # Publish event
            event_bus.publish(
                event_type=_sm.event_type,
                data=data,
                user_id=user_id,
                source_module=_mod,
                async_dispatch=True,
            )

            # If notify_admin — also publish admin notification event
            if _sm.notify_admin:
                event_bus.publish(
                    event_type=f'{_sm.event_type}.admin',
                    data={**data, 'notify_admin': True},
                    source_module=_mod,
                    priority=IntegPriority.HIGH,
                    async_dispatch=True,
                )

        # Register with Django
        post_save.connect(
            _signal_handler,
            sender=Model,
            weak=False,
            dispatch_uid=f'autodiscovery_{module_name}_{signal_map.model_path}_{signal_map.event_type}',
        )
        logger.debug(
            f'AutoDiscovery: wired {signal_map.model_path}.{signal_map.field}'
            f'={signal_map.value} → {signal_map.event_type}'
        )

    # ------------------------------------------------------------------
    # 3. Event Subscription Wiring
    # ------------------------------------------------------------------

    def _wire_event_subscription(self, event_map: EventMap, module_name: str):
        """Subscribe an EventBus event to auto-trigger notifications."""
        from .event_bus import event_bus

        _em = event_map
        _mod = module_name

        def _event_handler(event):
            if _em.condition_fn:
                try:
                    if not _em.condition_fn(event):
                        return
                except Exception:
                    return

            if not event.user_id and not _em.notification_type.endswith('_admin'):
                return

            # Render templates using event.data
            try:
                title = _em.title_template.format(**event.data)
            except (KeyError, ValueError):
                title = _em.title_template

            try:
                message = _em.message_template.format(**event.data)
            except (KeyError, ValueError):
                message = _em.message_template

            # Determine channels to send to
            channels = [_em.channel]
            if _em.send_push and 'push' not in channels:
                channels.append('push')
            if _em.send_email and 'email' not in channels:
                channels.append('email')
            if _em.send_sms and 'sms' not in channels:
                channels.append('sms')

            # Trigger notification for each channel
            for channel in channels:
                try:
                    from .integ_adapter import NotificationIntegrationAdapter
                    adapter = NotificationIntegrationAdapter()
                    adapter.send({
                        'user_id': event.user_id,
                        'notification_type': _em.notification_type,
                        'title': title,
                        'message': message,
                        'channel': channel,
                        'priority': _em.priority,
                        'metadata': event.data,
                    })
                except Exception as exc:
                    logger.warning(f'AutoDiscovery event handler {_em.event_type}: {exc}')

        event_bus.subscribe(
            event_type=_em.event_type,
            handler=_event_handler,
            subscriber_name=f'autodiscovery_{module_name}_{_em.event_type}',
            is_async=True,
        )
        logger.debug(f'AutoDiscovery: subscribed "{_em.event_type}" → notification "{_em.notification_type}"')

    # ------------------------------------------------------------------
    # 4. Webhook Registration
    # ------------------------------------------------------------------

    def _wire_webhook(self, webhook_map: WebhookMap, module_name: str):
        """Register webhook handler for a provider/event."""
        from .webhooks_integration import webhook_manager
        from .event_bus import event_bus

        _wm = webhook_map
        _mod = module_name

        def _webhook_handler(provider, event_type, payload):
            # Parse payload if parser_fn provided
            data = payload
            if _wm.parser_fn:
                try:
                    data = _wm.parser_fn(payload)
                except Exception as exc:
                    logger.warning(f'AutoDiscovery webhook parser {_wm.provider}: {exc}')

            event_bus.publish(
                event_type=_wm.event_output,
                data=data,
                source_module=_mod,
                async_dispatch=True,
            )

        for event_type in _wm.event_types:
            webhook_manager.on_event(f'{webhook_map.provider}.{event_type}')(_webhook_handler)

        logger.debug(
            f'AutoDiscovery: wired webhook {_wm.provider} '
            f'{_wm.event_types} → {_wm.event_output}'
        )

    # ------------------------------------------------------------------
    # 5. Permission Granting
    # ------------------------------------------------------------------

    def _grant_permissions(self, config: Type[ModuleConfig]):
        """Grant cross-module permissions declared in ModuleConfig."""
        from .auth_bridge import auth_bridge
        for target in config.allowed_targets:
            auth_bridge.grant_permission(config.module_name, target)
        logger.debug(
            f'AutoDiscovery: granted {config.module_name} → {config.allowed_targets}'
        )

    # ------------------------------------------------------------------
    # 6. Health Check Registration
    # ------------------------------------------------------------------

    def _register_health_check(self, health_check: HealthCheck, module_name: str):
        """Register a health check for a module."""
        from .health_check import health_checker

        _hc = health_check
        _mod = module_name

        def _check_fn() -> HealthStatus:
            if _hc.check_fn:
                return _hc.check_fn()
            if _hc.model_path:
                try:
                    app_label, model_name = _hc.model_path.split('.')
                    Model = apps.get_model(app_label, model_name)
                    Model.objects.first()
                    return HealthStatus.HEALTHY
                except Exception:
                    return HealthStatus.UNHEALTHY
            if _hc.url:
                try:
                    import requests
                    resp = requests.get(_hc.url, timeout=5)
                    return HealthStatus.HEALTHY if resp.status_code < 400 else HealthStatus.DEGRADED
                except Exception:
                    return HealthStatus.UNHEALTHY
            return HealthStatus.UNKNOWN

        # Register with health checker
        from .integ_constants import HealthStatus as HS
        service_name = f'{module_name}.{health_check.name}'
        health_checker._health[service_name] = type(
            'ServiceHealth',
            (),
            {
                'name': service_name,
                'status': HS.UNKNOWN,
                'last_checked': None,
                'last_success': None,
                'consecutive_failures': 0,
                'response_time_ms': 0,
                'details': {},
                'to_dict': lambda self: {
                    'service': self.name,
                    'status': self.status.value if hasattr(self.status, 'value') else str(self.status),
                },
            }
        )()

        # Override check function
        original_run_check = health_checker._run_check

        def _new_run_check(service: str) -> HealthStatus:
            if service == service_name:
                return _check_fn()
            return original_run_check(service)

        health_checker._run_check = _new_run_check
        logger.debug(f'AutoDiscovery: health check registered for "{service_name}"')

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_registered_modules(self) -> List[str]:
        """Return list of auto-discovered module names."""
        return list(self._configs.keys())

    def get_module_config(self, module_name: str) -> Optional[Type[ModuleConfig]]:
        """Return the ModuleConfig class for a module."""
        return self._configs.get(module_name)

    def get_discovery_report(self) -> Dict:
        """Return a full discovery report."""
        report = {
            'discovered_modules': self.get_registered_modules(),
            'total': len(self._configs),
            'modules': {},
        }
        for name, config in self._configs.items():
            report['modules'][name] = {
                'version': config.version,
                'description': config.description,
                'signal_maps': len(config.signal_maps),
                'event_maps': len(config.event_maps),
                'webhook_maps': len(config.webhook_maps),
                'health_checks': len(config.health_checks),
                'allowed_targets': config.allowed_targets,
                'enabled': config.enabled,
            }
        return report

    def reload_module(self, module_name: str) -> bool:
        """
        Re-discover a specific module (useful after config changes in dev).
        """
        # Remove from discovered set to allow re-discovery
        for app_name in list(self._discovered):
            if module_name in app_name:
                self._discovered.discard(app_name)
                if module_name in self._configs:
                    del self._configs[module_name]
                break
        return self.discover_app(module_name)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
auto_discovery = AutoDiscovery()
