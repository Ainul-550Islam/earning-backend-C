# api/support/exceptions.py
from rest_framework.exceptions import APIException

class TicketNotFound(APIException):
    status_code = 404
    default_detail = 'Ticket not found.'
    default_code = 'ticket_not_found'

class TicketClosed(APIException):
    status_code = 400
    default_detail = 'Ticket is closed. Please create a new ticket.'
    default_code = 'ticket_closed'

class TicketPermissionDenied(APIException):
    status_code = 403
    default_detail = 'Permission denied.'
    default_code = 'ticket_permission_denied'

class SLANotFound(APIException):
    status_code = 404
    default_detail = 'No SLA record found.'
    default_code = 'sla_not_found'

class DisputeLimitExceeded(APIException):
    status_code = 429
    default_detail = 'Dispute limit exceeded.'
    default_code = 'dispute_limit_exceeded'

class InvalidRating(APIException):
    status_code = 400
    default_detail = 'Rating must be 1-5.'
    default_code = 'invalid_rating'

class ChatSessionNotFound(APIException):
    status_code = 404
    default_detail = 'Chat session not found.'
    default_code = 'chat_not_found'

class ChatSessionEnded(APIException):
    status_code = 400
    default_detail = 'Chat session ended.'
    default_code = 'chat_ended'

class AgentNotAvailable(APIException):
    status_code = 503
    default_detail = 'No agents available.'
    default_code = 'agent_unavailable'

class AttachmentTooLarge(APIException):
    status_code = 400
    default_detail = 'File too large.'
    default_code = 'attachment_too_large'

class SupportMaintenanceMode(APIException):
    status_code = 503
    default_detail = 'Support in maintenance mode.'
    default_code = 'maintenance_mode'