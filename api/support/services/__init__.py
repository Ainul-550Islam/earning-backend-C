# api/support/services/__init__.py
import sys
import os

# Import directly from parent services.py to avoid circular imports
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "api.support._services",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "services.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

ticket_service        = _mod.ticket_service
sla_service           = _mod.sla_service
livechat_service      = _mod.livechat_service
kb_service            = _mod.kb_service
offer_dispute_service = _mod.offer_dispute_service
notification_service  = _mod.notification_service
TicketService         = _mod.TicketService
SLAService            = _mod.SLAService
NotificationService   = _mod.NotificationService
SupportService        = _mod.SupportService