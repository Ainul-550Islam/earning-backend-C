# api/support/throttling.py
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle, BaseThrottle

class TicketCreateThrottle(UserRateThrottle):
    scope = 'ticket_create'
    rate  = '10/hour'

class DisputeSubmitThrottle(UserRateThrottle):
    scope = 'dispute_submit'
    rate  = '5/day'

class ChatStartThrottle(UserRateThrottle):
    scope = 'chat_start'
    rate  = '10/hour'

class RatingSubmitThrottle(UserRateThrottle):
    scope = 'rating_submit'
    rate  = '20/hour'

class SupportPublicThrottle(AnonRateThrottle):
    scope = 'support_public'
    rate  = '60/minute'

class AgentActionThrottle(UserRateThrottle):
    scope = 'agent_action'
    rate  = '100/minute'

class WebhookThrottle(BaseThrottle):
    def allow_request(self, request, view):
        return True
    def wait(self):
        return None