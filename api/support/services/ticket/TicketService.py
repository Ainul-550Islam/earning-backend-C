# api/support/services/ticket/TicketService.py
"""Re-export ticket_service from main services.py"""
from api.support.services import ticket_service, TicketService
__all__ = ["ticket_service", "TicketService"]