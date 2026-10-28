# api/support/decorators.py
import logging
from functools import wraps
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def require_agent(func):
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'detail': 'Authentication required.'}, status=401)
        if not (request.user.is_staff or request.user.is_superuser or
                hasattr(request.user, 'support_agent')):
            return Response({'detail': 'Agent access required.'}, status=403)
        return func(request, *args, **kwargs)
    return wrapper


def support_available(func):
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        try:
            from api.support.models import SupportSettings
            obj, _ = SupportSettings.objects.get_or_create(id=1)
            if obj.maintenance_mode and not request.user.is_staff:
                return Response({
                    'error': 'maintenance',
                    'message': obj.maintenance_message or 'Support in maintenance.'
                }, status=503)
        except Exception:
            pass
        return func(request, *args, **kwargs)
    return wrapper


def ticket_owner_or_agent(func):
    @wraps(func)
    def wrapper(request, ticket_id, *args, **kwargs):
        from api.support.models import SupportTicket
        try:
            ticket = (SupportTicket.objects.get(ticket_id=ticket_id)
                      if str(ticket_id).startswith('TKT')
                      else SupportTicket.objects.get(id=ticket_id))
        except SupportTicket.DoesNotExist:
            return Response({'error': 'Ticket not found.'}, status=404)
        if not request.user.is_staff and ticket.user != request.user:
            return Response({'detail': 'Access denied.'}, status=403)
        request.ticket = ticket
        return func(request, ticket_id, *args, **kwargs)
    return wrapper