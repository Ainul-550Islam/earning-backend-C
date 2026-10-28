# api/admin_panel/plugins.py
"""
Admin Panel Extension System — FUTURE-PROOF ARCHITECTURE.

নতুন feature/app যোগ করতে শুধু 3 step:
  1. নতুন app-এ AppExtension subclass বানাও
  2. apps.py ready()-এ register করো
  3. শেষ — admin_panel-এর কোনো কোড বদলাতে হবে না

Example:
    class CryptoPayoutExtension(AppExtension):
        name = 'crypto_payout'
        label = 'Crypto Payout'
        icon = '₿'
        menu_group = 'Finance'

        def get_viewsets(self):
            from .viewsets import CryptoPayoutAdminViewSet
            return [('crypto-payouts', CryptoPayoutAdminViewSet)]

        def get_search_handlers(self):
            from .search import search_crypto
            return [('CryptoTx', 'crypto_payout', search_crypto, '₿')]

        def get_feature_flags(self):
            return [('enabled', True, 'Enable crypto payout feature')]

    # in crypto_payout/apps.py ready():
    from api.admin_panel.plugins import extension_registry
    extension_registry.register(CryptoPayoutExtension())
"""
from __future__ import annotations
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AppExtension:
    """Base class — subclass for every new app/feature."""

    name:          str  = ''
    label:         str  = ''
    version:       str  = '1.0.0'
    description:   str  = ''
    author:        str  = ''
    icon:          str  = 'box'
    menu_group:    str  = 'Other'
    menu_order:    int  = 100
    menu_url:      str  = ''
    requires_flag: str  = ''
    depends_on:    List[str] = []

    # Override these:
    def get_viewsets(self) -> List[Tuple[str, Any]]:          return []
    def get_urls(self) -> List:                                return []
    def get_search_handlers(self) -> List[Tuple]:              return []
    def get_dashboard_widgets(self) -> List[Dict]:             return []
    def get_celery_beat_schedule(self) -> Dict[str, Dict]:     return []
    def get_signals(self) -> List[Tuple[str, Callable]]:       return []
    def get_event_handlers(self) -> Dict[str, Callable]:       return {}
    def get_admin_menu_items(self) -> List[Dict]:              return []
    def get_permissions(self) -> Dict[str, List[str]]:         return {}
    def get_health_checks(self) -> List[Callable]:             return []
    def get_feature_flags(self) -> List[Tuple[str, bool, str]]: return []
    def get_system_config_defaults(self) -> List[Tuple]:       return []
    def get_notification_templates(self) -> Dict[str, Dict]:   return {}
    def get_audit_event_types(self) -> List[str]:              return []

    def on_install(self) -> None: pass
    def on_ready(self) -> None:   pass
    def on_uninstall(self) -> None: pass

    def __repr__(self) -> str:
        return f"<AppExtension: {self.name} v{self.version}>"


class AdminPlugin:
    """Lighter plugin for small add-ons."""
    name:    str = ''
    version: str = '1.0.0'
    icon:    str = 'plug'

    def on_install(self) -> None: pass
    def on_uninstall(self) -> None: pass
    def get_viewsets(self) -> List: return []
    def get_urls(self) -> List: return []
    def get_menu_items(self) -> List[Dict]: return []


class ExtensionRegistry:
    """Singleton registry for all extensions and plugins."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._extensions: Dict[str, AppExtension] = {}
            cls._instance._plugins:    Dict[str, AdminPlugin]   = {}
            cls._instance._initialized = False
        return cls._instance

    # ── Registration ─────────────────────────────────────────────────────

    def register(self, extension: AppExtension) -> bool:
        if not extension.name:
            logger.error("[ExtensionRegistry] Extension has no name")
            return False

        # Feature flag gate
        if extension.requires_flag:
            try:
                from api.admin_panel.feature_flags import is_enabled
                if not is_enabled(extension.requires_flag, default=True):
                    logger.info(f"[ExtensionRegistry] {extension.name} gated by flag {extension.requires_flag}")
                    return False
            except Exception:
                pass

        self._extensions[extension.name] = extension

        # Auto-wire all contributions
        self._wire_search(extension)
        self._wire_events(extension)
        self._wire_signals(extension)
        self._wire_flags(extension)
        self._wire_config(extension)
        self._wire_templates(extension)
        self._wire_health(extension)

        try:
            extension.on_install()
        except Exception as e:
            logger.warning(f"[ExtensionRegistry] on_install failed for {extension.name}: {e}")

        logger.info(f"[ExtensionRegistry] Registered: {extension.name} v{extension.version}")
        return True

    def register_plugin(self, plugin: AdminPlugin) -> bool:
        if not plugin.name:
            return False
        self._plugins[plugin.name] = plugin
        try:
            plugin.on_install()
        except Exception:
            pass
        logger.info(f"[ExtensionRegistry] Plugin: {plugin.name}")
        return True

    def unregister(self, name: str) -> bool:
        ext = self._extensions.pop(name, None)
        if ext:
            try:
                ext.on_uninstall()
            except Exception:
                pass
            return True
        return False

    # ── Auto-wiring ───────────────────────────────────────────────────────

    def _wire_search(self, ext: AppExtension) -> None:
        handlers = ext.get_search_handlers()
        if not handlers:
            return
        try:
            from api.admin_panel.search import search_registry
            for item in handlers:
                model_name, app_name, fn, icon = (item + ('box',))[:4]
                search_registry.register(model_name, app_name, fn, icon=icon, priority=50)
        except Exception as e:
            logger.debug(f"[ExtReg._wire_search] {ext.name}: {e}")

    def _wire_events(self, ext: AppExtension) -> None:
        handlers = ext.get_event_handlers()
        if not handlers:
            return
        try:
            from api.admin_panel.INTEGRATION_SYSTEM.event_bus import event_bus
            for event_name, fn in handlers.items():
                event_bus.subscribe(event_name, fn)
        except Exception as e:
            logger.debug(f"[ExtReg._wire_events] {ext.name}: {e}")

    def _wire_signals(self, ext: AppExtension) -> None:
        signals = ext.get_signals()
        if not signals:
            return
        try:
            from api.admin_panel.signals_kb import signal_router
            for signal_name, fn in signals:
                signal_router.route(signal_name, fn, priority=20)
        except Exception as e:
            logger.debug(f"[ExtReg._wire_signals] {ext.name}: {e}")

    def _wire_flags(self, ext: AppExtension) -> None:
        flags = ext.get_feature_flags()
        if not flags:
            return
        try:
            from api.admin_panel.models.config import FeatureFlag
            for flag_key, default_enabled, description in flags:
                full_key = f"{ext.name}.{flag_key}"
                FeatureFlag.objects.get_or_create(
                    flag_key=full_key,
                    defaults={
                        'label':       f"{ext.label or ext.name}: {flag_key.replace('_', ' ').title()}",
                        'description': description,
                        'is_enabled':  default_enabled,
                        'rollout_pct': 100,
                    }
                )
        except Exception as e:
            logger.debug(f"[ExtReg._wire_flags] {ext.name}: {e}")

    def _wire_config(self, ext: AppExtension) -> None:
        configs = ext.get_system_config_defaults()
        if not configs:
            return
        try:
            from api.admin_panel.models.config import SystemConfig
            for key, value, value_type, group in configs:
                SystemConfig.objects.get_or_create(
                    key=f"{ext.name}.{key}",
                    defaults={'value': value, 'value_type': value_type, 'group': group}
                )
        except Exception as e:
            logger.debug(f"[ExtReg._wire_config] {ext.name}: {e}")

    def _wire_templates(self, ext: AppExtension) -> None:
        templates = ext.get_notification_templates()
        if not templates:
            return
        try:
            from api.admin_panel.models.config import EmailTemplate
            for key, tmpl in templates.items():
                EmailTemplate.objects.get_or_create(
                    template_key=f"{ext.name}.{key}",
                    defaults={
                        'subject':   tmpl.get('email_subject', key),
                        'body_text': tmpl.get('email_body', ''),
                        'body_html': tmpl.get('email_html', ''),
                    }
                )
        except Exception as e:
            logger.debug(f"[ExtReg._wire_templates] {ext.name}: {e}")

    def _wire_health(self, ext: AppExtension) -> None:
        checks = ext.get_health_checks()
        if not checks:
            return
        try:
            from api.admin_panel.INTEGRATION_SYSTEM.health_check import HealthCheck
            if hasattr(HealthCheck, 'register_custom'):
                for fn in checks:
                    HealthCheck.register_custom(ext.name, fn)
        except Exception as e:
            logger.debug(f"[ExtReg._wire_health] {ext.name}: {e}")

    # ── Query ────────────────────────────────────────────────────────────

    def get_all_viewsets(self) -> List[Tuple[str, Any]]:
        result = []
        for ext in self._extensions.values():
            try:
                result.extend(ext.get_viewsets())
            except Exception as e:
                logger.error(f"[ExtReg] viewsets({ext.name}): {e}")
        for p in self._plugins.values():
            try:
                result.extend(p.get_viewsets())
            except Exception:
                pass
        return result

    def get_all_urls(self) -> List:
        result = []
        for ext in self._extensions.values():
            try:
                result.extend(ext.get_urls())
            except Exception:
                pass
        return result

    def get_all_menu_items(self) -> List[Dict]:
        items = []
        for ext in self._extensions.values():
            try:
                auto = {
                    'label':  ext.label or ext.name.replace('_', ' ').title(),
                    'icon':   ext.icon,
                    'group':  ext.menu_group,
                    'order':  ext.menu_order,
                    'url':    ext.menu_url or f'/api/admin-panel/{ext.name.replace("_", "-")}/',
                    'source': ext.name,
                }
                items.append(auto)
                items.extend(ext.get_admin_menu_items())
            except Exception as e:
                logger.error(f"[ExtReg] menu({ext.name}): {e}")
        items.sort(key=lambda x: (x.get('group', 'ZZ'), x.get('order', 100)))
        return items

    def get_all_widgets(self) -> List[Dict]:
        widgets = []
        for ext in self._extensions.values():
            try:
                widgets.extend(ext.get_dashboard_widgets())
            except Exception:
                pass
        return widgets

    def get_all_beat_schedule(self) -> Dict[str, Dict]:
        schedule = {}
        for ext in self._extensions.values():
            try:
                for name, config in ext.get_celery_beat_schedule().items():
                    schedule[f"{ext.name}.{name}"] = config
            except Exception:
                pass
        return schedule

    def get_extension(self, name: str) -> Optional[AppExtension]:
        return self._extensions.get(name)

    def list_extensions(self) -> List[Dict]:
        return [
            {
                'name':    e.name,   'label':   e.label,
                'version': e.version, 'icon':   e.icon,
                'group':   e.menu_group, 'description': e.description,
                'viewsets': len(e.get_viewsets()),
                'widgets':  len(e.get_dashboard_widgets()),
                'flags':    len(e.get_feature_flags()),
            }
            for e in self._extensions.values()
        ]

    def list_plugins(self) -> List[Dict]:
        return [{'name': p.name, 'version': p.version} for p in self._plugins.values()]

    def run_all_ready(self) -> None:
        """Call on_ready() on all extensions after full Django startup."""
        for ext in self._extensions.values():
            try:
                ext.on_ready()
            except Exception as e:
                logger.error(f"[ExtReg] on_ready({ext.name}): {e}")
        self._initialized = True
        logger.info(f"[ExtensionRegistry] All extensions ready: {list(self._extensions.keys())}")

    def get_health_summary(self) -> Dict:
        return {
            'total':        len(self._extensions),
            'plugins':      len(self._plugins),
            'initialized':  self._initialized,
            'extensions':   [e.name for e in self._extensions.values()],
        }


# Singletons
extension_registry = ExtensionRegistry()
plugin_registry    = extension_registry   # backward-compatible alias