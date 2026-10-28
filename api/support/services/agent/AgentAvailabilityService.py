# api/support/services/agent/AgentAvailabilityService.py  — WORLD #1
import logging
from django.utils import timezone
logger = logging.getLogger(__name__)

STATUS_CHOICES = ('online','busy','away','offline')

class AgentAvailabilityService:
    def set_status(self, agent, status: str) -> dict:
        if status not in STATUS_CHOICES:
            return {'error': f'Invalid status. Choose: {STATUS_CHOICES}'}
        from api.support.models import AgentStatus
        obj, _ = AgentStatus.objects.get_or_create(agent=agent)
        obj.status = status
        obj.save(update_fields=['status'])
        # Update SupportAgent.is_available
        agent.is_available = status in ('online',)
        agent.save(update_fields=['is_available'])
        return {'status': status, 'agent': agent.user.username}

    def get_status(self, agent) -> dict:
        from api.support.models import AgentStatus
        try:
            s = agent.status
            return {'status': s.status, 'last_seen': s.last_seen, 'message': s.status_message}
        except Exception:
            return {'status': 'offline'}

    def who_is_online(self) -> list:
        from api.support.models import AgentStatus
        online = AgentStatus.objects.filter(status__in=['online','busy']).select_related('agent__user')
        return [{'username': s.agent.user.username, 'status': s.status} for s in online]

agent_availability_service = AgentAvailabilityService()