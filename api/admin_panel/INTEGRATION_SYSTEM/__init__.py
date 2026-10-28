# api/admin_panel/INTEGRATION_SYSTEM/__init__.py
"""
INTEGRATION_SYSTEM — Admin Panel Cross-Module Integration Layer.

This package connects all 50 apps in the system through:
  - Core Connectors (registry, adapter, handler, signals)
  - Bridge & Bus (event bus, webhooks, message queue, data bridge)
  - Security & Validation (auth bridge, validator, fallback)
  - Monitoring & Logs (health check, audit, performance, sync manager)

Usage:
    from api.admin_panel.INTEGRATION_SYSTEM import IntegrationRegistry
    from api.admin_panel.INTEGRATION_SYSTEM.bridge import AdminBridge
    from api.admin_panel.INTEGRATION_SYSTEM.event_bus import EventBus
"""

from .integ_registry import IntegrationRegistry
from .integ_constants import (
    INTEGRATION_APPS,
    INTEGRATION_EVENTS,
    SUPPORTED_BRIDGES,
)

__all__ = [
    'IntegrationRegistry',
    'INTEGRATION_APPS',
    'INTEGRATION_EVENTS',
    'SUPPORTED_BRIDGES',
]

__version__ = '1.0.0'