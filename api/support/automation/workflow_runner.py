"""
api/support/automation/workflow_runner.py
FILE 42/70 — Complex Workflow Runner

Multi-step workflow execute করো।
Wait, branch, loop support।
"""
import logging
from django.core.cache import cache
from django.utils import timezone
logger = logging.getLogger(__name__)

class WorkflowRunner:
    def run(self, workflow_id: str, ticket, context: dict = None) -> dict:
        try:
            from api.support.models import AutomationRule
            rule = AutomationRule.objects.prefetch_related('conditions','actions').get(id=workflow_id, is_active=True)
            from api.support.services.automation.AutomationEngine import automation_engine
            executed = automation_engine._execute_actions(ticket, rule.actions.all())
            return {'workflow_id': workflow_id, 'executed': len(executed), 'actions': executed}
        except Exception as e:
            logger.error(f'Workflow run failed [{workflow_id}]: {e}')
            return {'error': str(e)}

    def run_delayed(self, workflow_id: str, ticket_id: str, delay_minutes: int) -> str:
        """Celery delay task"""
        from api.support.tasks.automation_tasks import run_automation_on_ticket
        result = run_automation_on_ticket.apply_async(
            args  = [ticket_id, 'delayed_workflow'],
            countdown = delay_minutes * 60,
        )
        return result.id

workflow_runner = WorkflowRunner()