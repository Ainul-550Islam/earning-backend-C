# api/support/services/automation/AutomationActionService.py  — WORLD #1
import logging
logger = logging.getLogger(__name__)

class AutomationActionService:
    def execute(self, ticket, action_type: str, value: str) -> bool:
        from api.support.automation.action_executor import action_executor
        return action_executor.execute(ticket, action_type, value)

    def execute_batch(self, ticket, actions: list) -> list:
        results = []
        for action in actions:
            ok = self.execute(ticket, action.get('type',''), action.get('value',''))
            results.append({'type': action.get('type'), 'ok': ok})
        return results

automation_action_service = AutomationActionService()