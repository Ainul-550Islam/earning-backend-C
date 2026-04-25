# integration_system/__init__.py
"""
Integration System — Cross-module integration layer for earning site.

Quick access:
    from integration_system import handler, event_bus, registry
    from integration_system import bridge, message_queue, webhook_manager
    from integration_system import health_checker, audit_logger, sync_manager
    from integration_system import performance_monitor, data_validator
    from integration_system import auth_bridge, fallback_service, data_bridge
"""
from .integ_handler import handler
from .integ_registry import registry
from .event_bus import event_bus
from .bridge import bridge
from .message_queue import message_queue
from .webhooks_integration import webhook_manager
from .data_bridge import data_bridge
from .data_validator import data_validator
from .fallback_logic import fallback_service
from .auth_bridge import auth_bridge
from .performance_monitor import performance_monitor
from .integ_audit_logs import audit_logger
from .health_check import health_checker
from .sync_manager import sync_manager

__all__ = [
    'handler', 'registry', 'event_bus', 'bridge', 'message_queue',
    'webhook_manager', 'data_bridge', 'data_validator', 'fallback_service',
    'auth_bridge', 'performance_monitor', 'audit_logger', 'health_checker',
    'sync_manager',
]

VERSION = '1.0.0'

from .auto_discovery import auto_discovery  # noqa: F401
from .module_protocol import ModuleConfig, SignalMap, EventMap, WebhookMap, HealthCheck  # noqa: F401
