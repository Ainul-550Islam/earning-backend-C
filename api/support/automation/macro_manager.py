"""
api/support/automation/macro_manager.py
FILE 47/70 — One-Click Macro Manager

Agent dashboard-এ one-click macros।
Multiple actions একসাথে execute করো।
"""
import logging
logger = logging.getLogger(__name__)

# Default macros
DEFAULT_MACROS = {
    'close_and_resolve': {
        'name':    'Resolve & Close',
        'icon':    '✅',
        'actions': [
            {'type': 'set_status',  'value': 'resolved'},
            {'type': 'send_canned', 'value': '/resolved'},
        ],
    },
    'mark_spam': {
        'name':    'Mark Spam & Close',
        'icon':    '🚫',
        'actions': [
            {'type': 'set_status',  'value': 'spam'},
            {'type': 'add_tag',     'value': 'spam'},
        ],
    },
    'escalate_urgent': {
        'name':    'Escalate to Urgent',
        'icon':    '🚨',
        'actions': [
            {'type': 'set_priority', 'value': 'urgent'},
            {'type': 'escalate',     'value': ''},
            {'type': 'notify_slack', 'value': 'Ticket escalated to URGENT!'},
        ],
    },
    'payment_investigating': {
        'name':    'Payment Investigating',
        'icon':    '🔍',
        'actions': [
            {'type': 'set_priority', 'value': 'high'},
            {'type': 'add_tag',      'value': 'payment-investigation'},
            {'type': 'send_canned',  'value': '/payment'},
        ],
    },
    'kyc_required': {
        'name':    'Request KYC',
        'icon':    '📋',
        'actions': [
            {'type': 'add_tag',     'value': 'kyc-required'},
            {'type': 'send_canned', 'value': '/kyc'},
        ],
    },
    'waiting_for_user': {
        'name':    'Set Waiting for User',
        'icon':    '⏳',
        'actions': [
            {'type': 'set_status', 'value': 'waiting_user'},
            {'type': 'send_canned','value': '/waiting'},
        ],
    },
}

class MacroManager:
    def get_all_macros(self, agent_user=None) -> list:
        macros = [{'id': k, **v} for k, v in DEFAULT_MACROS.items()]
        try:
            from api.support.models import TicketWorkflow
            custom = TicketWorkflow.objects.filter(is_active=True, trigger='manual')
            for wf in custom:
                macros.append({'id': str(wf.id), 'name': wf.name, 'icon': '⚡', 'actions': wf.actions})
        except Exception:
            pass
        return macros

    def execute_macro(self, macro_id: str, ticket, agent_user) -> dict:
        macro   = DEFAULT_MACROS.get(macro_id)
        if not macro:
            try:
                from api.support.models import TicketWorkflow
                wf    = TicketWorkflow.objects.get(id=macro_id)
                macro = {'actions': wf.actions}
            except Exception:
                return {'error': f'Macro {macro_id} not found.'}

        from api.support.automation.action_executor import action_executor
        executed = []
        for action in macro.get('actions', []):
            ok = action_executor.execute(ticket, action['type'], action.get('value',''))
            if ok:
                executed.append(action['type'])

        logger.info(f'Macro [{macro_id}] executed on {ticket.ticket_id}: {executed}')
        return {'macro_id': macro_id, 'executed': executed, 'count': len(executed)}

    def create_macro(self, name: str, icon: str, actions: list, agent_user) -> dict:
        try:
            from api.support.models import TicketWorkflow
            wf = TicketWorkflow.objects.create(
                name       = name,
                trigger    = 'manual',
                actions    = actions,
                is_active  = True,
                created_by = agent_user,
            )
            return {'id': str(wf.id), 'name': name}
        except Exception as e:
            logger.error(f'Macro create failed: {e}')
            return {'error': str(e)}

macro_manager = MacroManager()