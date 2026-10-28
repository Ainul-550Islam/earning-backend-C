# api/support/services/agent/ShiftService.py  — WORLD #1
import logging
from django.utils import timezone
logger = logging.getLogger(__name__)

class ShiftService:
    def who_is_on_shift_now(self) -> list:
        from api.support.models import SupportAgent, AgentShift
        now     = timezone.localtime()
        weekday = now.weekday()
        time_now= now.time()
        shifts  = AgentShift.objects.filter(
            weekday=weekday, shift_start__lte=time_now, shift_end__gte=time_now, is_active=True
        ).select_related('agent__user')
        return [{'username': s.agent.user.username, 'role': s.agent.role} for s in shifts]

    def is_agent_on_shift(self, agent) -> bool:
        agents = self.who_is_on_shift_now()
        return any(a['username'] == agent.user.username for a in agents)

shift_service = ShiftService()