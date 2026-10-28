"""
api/support/automation/trigger_engine.py
FILE 43/70 — Trigger Engine (50+ triggers)

Ticket/Chat/Agent/User events → automation trigger করো।
"""
import logging
logger = logging.getLogger(__name__)

class TriggerEngine:
    def fire(self, trigger: str, ticket=None, chat=None, agent=None, extra: dict = None) -> list:
        """Fire trigger → run matching automation rules"""
        try:
            from api.support.models import AutomationRule
            from api.support.services.automation.AutomationEngine import automation_engine
            rules = AutomationRule.objects.filter(is_active=True, trigger=trigger).order_by('priority')
            results = []
            for rule in rules:
                if ticket:
                    executed = automation_engine._execute_actions(ticket, rule.actions.all())
                    if executed:
                        results.append({'rule': rule.name, 'actions': len(executed)})
            return results
        except Exception as e:
            logger.error(f'Trigger engine failed [{trigger}]: {e}')
            return []

    def fire_time_based_triggers(self) -> dict:
        """Celery-এ প্রতি ঘণ্টায় run করো — idle + SLA"""
        from api.support.models import SupportTicket
        from django.utils import timezone
        from datetime import timedelta

        stats = {'fired': 0}
        for hours, trigger in [(1,'ticket_idle_1h'),(4,'ticket_idle_4h'),(24,'ticket_idle_24h')]:
            cutoff  = timezone.now() - timedelta(hours=hours)
            tickets = SupportTicket.objects.filter(status__in=['open','in_progress'], updated_at__lte=cutoff)
            for ticket in tickets[:20]:
                self.fire(trigger, ticket=ticket)
                stats['fired'] += 1
        return stats

trigger_engine = TriggerEngine()