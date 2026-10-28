# api/support/integrations/project_specific/ticket_collision.py
"""
Ticket Collision Detection — prevent two agents from working on same ticket.

When agent opens a ticket:
  1. Check if another agent already has it open
  2. Show warning to second agent
  3. Track who is currently "viewing" each ticket
  
Uses Redis/cache for real-time presence tracking.
"""
import logging
from django.core.cache import cache
from django.utils import timezone
logger = logging.getLogger(__name__)

VIEWING_TTL = 120  # seconds — agent "presence" expires after 2 min


class TicketCollisionDetector:
    """Detect and prevent agent collision on tickets."""

    def _key(self, ticket_id) -> str:
        return f"support:ticket:viewing:{ticket_id}"

    def agent_opened_ticket(self, agent, ticket) -> dict:
        """
        Called when agent opens a ticket for editing.
        Returns: {collision: bool, other_agent: str, warning: str}
        """
        key      = self._key(ticket.ticket_id)
        viewing  = cache.get(key, {})
        agent_id = str(agent.id)
        now_iso  = timezone.now().isoformat()

        # Check for collision
        collision_agents = [
            info for aid, info in viewing.items()
            if aid != agent_id
        ]

        # Register this agent as viewing
        viewing[agent_id] = {
            "username":   agent.username,
            "opened_at":  now_iso,
            "expires_at": (timezone.now() + timezone.timedelta(seconds=VIEWING_TTL)).isoformat(),
        }
        cache.set(key, viewing, timeout=VIEWING_TTL)

        if collision_agents:
            other = collision_agents[0]
            return {
                "collision":   True,
                "other_agent": other["username"],
                "opened_at":   other["opened_at"],
                "warning":     f"⚠️ {other['username']} is also viewing this ticket. Coordinate to avoid duplicate responses.",
            }

        return {"collision": False, "other_agent": None, "warning": ""}

    def agent_closed_ticket(self, agent, ticket) -> None:
        """Called when agent closes/leaves a ticket view."""
        key     = self._key(ticket.ticket_id)
        viewing = cache.get(key, {})
        viewing.pop(str(agent.id), None)
        if viewing:
            cache.set(key, viewing, timeout=VIEWING_TTL)
        else:
            cache.delete(key)

    def heartbeat(self, agent, ticket) -> None:
        """Refresh agent presence (call every 60s from frontend)."""
        self.agent_opened_ticket(agent, ticket)

    def get_viewing_agents(self, ticket) -> list:
        """Get list of agents currently viewing a ticket."""
        key     = self._key(ticket.ticket_id)
        viewing = cache.get(key, {})
        return [info["username"] for info in viewing.values()]

    def get_all_active_viewers(self) -> dict:
        """Admin view — see who is viewing what (uses Redis SCAN if available)."""
        return {}  # Complex in Redis — simplified version


collision_detector = TicketCollisionDetector()