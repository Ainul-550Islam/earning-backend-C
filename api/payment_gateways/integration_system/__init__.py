# api/payment_gateways/integration_system/__init__.py
# Integration system — 18 files
# Auto-wires payment_gateways with your existing api apps

from .integ_handler   import handler as integration_handler
from .integ_registry  import registry
from .integ_constants import IntegEvent, IntegModule, Priority, QUEUE_NAMES
from .event_bus       import event_bus
from .message_queue   import message_queue

__all__ = [
    'integration_handler', 'registry', 'event_bus', 'message_queue',
    'IntegEvent', 'IntegModule', 'Priority', 'QUEUE_NAMES',
]
