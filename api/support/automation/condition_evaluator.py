"""
api/support/automation/condition_evaluator.py
FILE 44/70 — Advanced Condition Evaluator

Complex conditions: AND/OR groups, nested conditions।
"""
import logging, re
logger = logging.getLogger(__name__)

class ConditionEvaluator:
    def evaluate_all(self, ticket, conditions: list, logic: str = 'AND') -> bool:
        if not conditions:
            return True
        results = [self._eval_single(ticket, c) for c in conditions]
        return all(results) if logic == 'AND' else any(results)

    def _eval_single(self, ticket, cond: dict) -> bool:
        field    = cond.get('field', '')
        operator = cond.get('operator', 'equals')
        value    = str(cond.get('value', ''))
        try:
            ticket_val = self._get_field(ticket, field)
            return self._compare(str(ticket_val), operator, value)
        except Exception as e:
            logger.warning(f'Condition eval failed [{field}]: {e}')
            return False

    def _get_field(self, ticket, field: str):
        parts = field.split('.')
        if parts[0] == 'ticket':
            return getattr(ticket, parts[1], '')
        if parts[0] == 'user':
            user = ticket.user
            if parts[1] == 'total_tickets':
                from api.support.models import SupportTicket
                return SupportTicket.objects.filter(user=user).count()
            return getattr(user, parts[1], '')
        if parts[0] == 'sla':
            try:
                sla = ticket.sla
                if parts[1] == 'is_breached':
                    return sla.is_breached
                if parts[1] == 'minutes_remaining':
                    from django.utils import timezone
                    if sla.first_response_due:
                        return (sla.first_response_due - timezone.now()).total_seconds() / 60
            except Exception:
                pass
        if parts[0] == 'ai':
            if parts[1] == 'sentiment':
                return ticket.ai_sentiment
            if parts[1] == 'category':
                return ticket.ai_category
        return ''

    def _compare(self, val: str, op: str, target: str) -> bool:
        if op == 'equals':        return val == target
        if op == 'not_equals':    return val != target
        if op == 'contains':      return target.lower() in val.lower()
        if op == 'not_contains':  return target.lower() not in val.lower()
        if op == 'starts_with':   return val.lower().startswith(target.lower())
        if op == 'in':            return val in [v.strip() for v in target.split(',')]
        if op == 'not_in':        return val not in [v.strip() for v in target.split(',')]
        if op == 'is_true':       return val.lower() in ('true','1','yes')
        if op == 'is_false':      return val.lower() in ('false','0','no')
        if op == 'is_empty':      return not val.strip()
        if op == 'is_not_empty':  return bool(val.strip())
        try:
            if op == 'greater_than':  return float(val) > float(target)
            if op == 'less_than':     return float(val) < float(target)
        except ValueError:
            pass
        return False

condition_evaluator = ConditionEvaluator()