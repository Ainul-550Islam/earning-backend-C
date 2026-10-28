# api/support/services/livechat/ChatRoutingService.py  — WORLD #1
import logging
logger = logging.getLogger(__name__)

class ChatRoutingService:
    def find_available_agent(self, department=None, skills: list = None):
        from api.support.services.agent.AgentService import workload_balancer
        return workload_balancer.get_best_agent(skills=skills)

    def route_session(self, session) -> bool:
        agent = self.find_available_agent()
        if agent:
            session.agent  = agent.user
            session.status = 'active'
            session.save(update_fields=['agent','status'])
            return True
        return False

chat_routing_service = ChatRoutingService()