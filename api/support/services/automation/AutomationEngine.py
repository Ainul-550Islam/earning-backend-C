# api/support/services/automation/AutomationEngine.py  — WORLD #1 COMPLETE
import logging
logger = logging.getLogger(__name__)

class AutomationEngine:
    def evaluate_and_run(self, trigger: str, ticket, extra: dict = None) -> list:
        from api.support.models import AutomationRule
        rules   = AutomationRule.objects.filter(is_active=True, trigger=trigger).prefetch_related("conditions","actions").order_by("priority")
        results = []
        for rule in rules:
            try:
                if self._conditions_met(ticket, rule.conditions.all(), rule.conditions_logic):
                    executed = self._execute_actions(ticket, rule.actions.all())
                    AutomationRule.objects.filter(pk=rule.pk).update(run_count=rule.run_count+1)
                    results.append({"rule":rule.name,"executed":len(executed),"actions":executed})
                    if rule.stop_on_match: break
            except Exception as e:
                logger.error(f"Rule [{rule.name}] failed: {e}")
        return results

    def _conditions_met(self, ticket, conditions, logic: str = "AND") -> bool:
        if not conditions: return True
        from api.support.automation.condition_evaluator import condition_evaluator
        results = [condition_evaluator._eval_single(ticket, {"field":c.field,"operator":c.operator,"value":c.value}) for c in conditions]
        return all(results) if logic == "AND" else any(results)

    def _execute_actions(self, ticket, actions) -> list:
        from api.support.automation.action_executor import action_executor
        executed = []
        for action in actions:
            try:
                if action_executor.execute(ticket, action.action_type, action.value):
                    executed.append(action.action_type)
            except Exception as e:
                logger.error(f"Action [{action.action_type}] failed: {e}")
        return executed

automation_engine = AutomationEngine()