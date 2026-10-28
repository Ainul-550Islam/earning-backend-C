# api/support/notification_service.py  — WORLD #1 COMPLETE
"""
Simple notification helpers — re-export from main services.py.
Referenced as: from .notification_service import notify_ticket_created
"""
from api.support.services import (
    notify_ticket_created,
    notify_new_reply,
    notify_ticket_resolved,
    notify_sla_breach,
    notify_sla_warning,
)

__all__ = [
    'notify_ticket_created',
    'notify_new_reply',
    'notify_ticket_resolved',
    'notify_sla_breach',
    'notify_sla_warning',
]