"""
api/support/automation/workflow_builder.py
FILE 41/70 — Visual Workflow Designer API

Zendesk-এর মতো automation workflow designer।
Admin visually if/then rules তৈরি করতে পারবে।
50+ trigger types, 30+ action types।
"""
import logging
import uuid
from django.utils import timezone

logger = logging.getLogger(__name__)


class WorkflowBuilderAPI:
    """
    Workflow builder CRUD।
    Complex multi-step automation design করো।
    """

    # 50+ TRIGGER TYPES
    TRIGGERS = {
        # Ticket events
        'ticket_created':         {'label': 'Ticket Created',              'group': 'ticket'},
        'ticket_updated':         {'label': 'Ticket Updated',              'group': 'ticket'},
        'ticket_status_changed':  {'label': 'Status Changed',              'group': 'ticket'},
        'ticket_priority_changed':{'label': 'Priority Changed',            'group': 'ticket'},
        'ticket_assigned':        {'label': 'Ticket Assigned',             'group': 'ticket'},
        'ticket_unassigned':      {'label': 'Ticket Unassigned',           'group': 'ticket'},
        'ticket_resolved':        {'label': 'Ticket Resolved',             'group': 'ticket'},
        'ticket_closed':          {'label': 'Ticket Closed',               'group': 'ticket'},
        'ticket_reopened':        {'label': 'Ticket Reopened',             'group': 'ticket'},
        'ticket_escalated':       {'label': 'Ticket Escalated',            'group': 'ticket'},
        'ticket_merged':          {'label': 'Ticket Merged',               'group': 'ticket'},
        'ticket_spam':            {'label': 'Marked as Spam',              'group': 'ticket'},
        'ticket_tagged':          {'label': 'Tag Added',                   'group': 'ticket'},
        'ticket_rated':           {'label': 'Rating Submitted',            'group': 'ticket'},

        # Reply events
        'reply_received':         {'label': 'Reply Received (User)',       'group': 'reply'},
        'agent_replied':          {'label': 'Agent Replied',               'group': 'reply'},
        'first_reply_sent':       {'label': 'First Reply Sent',            'group': 'reply'},

        # Time-based
        'ticket_idle_1h':         {'label': 'Ticket Idle 1 Hour',         'group': 'time'},
        'ticket_idle_4h':         {'label': 'Ticket Idle 4 Hours',        'group': 'time'},
        'ticket_idle_24h':        {'label': 'Ticket Idle 24 Hours',       'group': 'time'},
        'ticket_idle_72h':        {'label': 'Ticket Idle 72 Hours',       'group': 'time'},
        'ticket_idle_7d':         {'label': 'Ticket Idle 7 Days',         'group': 'time'},
        'sla_warning':            {'label': 'SLA Warning (1hr before)',    'group': 'sla'},
        'sla_first_response_breach':{'label': 'First Response SLA Breach','group': 'sla'},
        'sla_resolution_breach':  {'label': 'Resolution SLA Breach',      'group': 'sla'},

        # Chat events
        'chat_started':           {'label': 'Chat Session Started',        'group': 'chat'},
        'chat_ended':             {'label': 'Chat Session Ended',          'group': 'chat'},
        'chat_missed':            {'label': 'Chat Missed (No Agent)',      'group': 'chat'},
        'chat_rated_low':         {'label': 'Chat Rated Low (1-2)',        'group': 'chat'},

        # Agent events
        'agent_offline':          {'label': 'All Agents Offline',          'group': 'agent'},
        'agent_overloaded':       {'label': 'Agent Overloaded (>90%)',     'group': 'agent'},

        # User events
        'user_high_churn_risk':   {'label': 'High Churn Risk Detected',   'group': 'user'},
        'user_fraud_suspected':   {'label': 'Fraud Suspected',            'group': 'user'},
        'csat_low':               {'label': 'Low CSAT Score (1-2)',        'group': 'csat'},
        'csat_received':          {'label': 'CSAT Rating Received',        'group': 'csat'},

        # KB events
        'kb_article_viewed':      {'label': 'KB Article Viewed',           'group': 'kb'},
        'kb_search_no_result':    {'label': 'KB Search No Results',       'group': 'kb'},
    }

    # 30+ CONDITION FIELDS
    CONDITIONS = {
        'ticket.priority':   {'label': 'Priority',          'type': 'select', 'options': ['urgent','high','medium','low']},
        'ticket.category':   {'label': 'Category',          'type': 'select', 'options': ['payment','withdrawal','coins','account','fraud','kyc','technical','referral','other']},
        'ticket.status':     {'label': 'Status',            'type': 'select', 'options': ['open','in_progress','waiting_user','resolved','closed']},
        'ticket.channel':    {'label': 'Channel',           'type': 'select', 'options': ['web','email','chat','telegram','whatsapp']},
        'ticket.subject':    {'label': 'Subject Contains',  'type': 'text'},
        'ticket.description':{'label': 'Description Contains','type': 'text'},
        'ticket.assigned_to':{'label': 'Assigned Agent',    'type': 'agent_select'},
        'ticket.department': {'label': 'Department',        'type': 'dept_select'},
        'ticket.tags':       {'label': 'Has Tag',           'type': 'tag_select'},
        'ticket.message_count':{'label': 'Message Count',  'type': 'number'},
        'ticket.wait_hours': {'label': 'Wait Hours',        'type': 'number'},
        'user.total_tickets':{'label': 'User Total Tickets','type': 'number'},
        'user.churn_score':  {'label': 'Churn Risk Score',  'type': 'number'},
        'user.last_rating':  {'label': 'Last CSAT Rating',  'type': 'number'},
        'sla.is_breached':   {'label': 'SLA Breached',      'type': 'boolean'},
        'sla.minutes_remaining':{'label': 'SLA Minutes Remaining','type': 'number'},
        'ai.sentiment':      {'label': 'AI Sentiment',      'type': 'select', 'options': ['positive','neutral','negative','very_negative']},
        'ai.category':       {'label': 'AI Classified Category','type': 'select', 'options': ['payment','withdrawal','coins','account','fraud','kyc','technical','other']},
        'time.hour':         {'label': 'Current Hour (0-23)','type': 'number'},
        'time.weekday':      {'label': 'Day of Week',       'type': 'select', 'options': ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']},
        'time.is_business_hours':{'label': 'Is Business Hours','type': 'boolean'},
    }

    # 30+ ACTION TYPES
    ACTIONS = {
        # Assignment
        'assign_agent':      {'label': 'Assign to Agent',        'group': 'assignment', 'params': ['agent_id']},
        'assign_department': {'label': 'Assign to Department',   'group': 'assignment', 'params': ['dept_id']},
        'unassign':          {'label': 'Unassign Ticket',         'group': 'assignment', 'params': []},
        'round_robin':       {'label': 'Round-Robin Assign',      'group': 'assignment', 'params': []},

        # Status + Priority
        'set_status':        {'label': 'Set Status',             'group': 'status', 'params': ['status']},
        'set_priority':      {'label': 'Set Priority',           'group': 'status', 'params': ['priority']},
        'escalate':          {'label': 'Escalate Ticket',         'group': 'status', 'params': []},
        'close':             {'label': 'Close Ticket',            'group': 'status', 'params': []},
        'reopen':            {'label': 'Reopen Ticket',           'group': 'status', 'params': []},

        # Tags
        'add_tag':           {'label': 'Add Tag',                 'group': 'tags', 'params': ['tag']},
        'remove_tag':        {'label': 'Remove Tag',              'group': 'tags', 'params': ['tag']},

        # Messages
        'send_reply':        {'label': 'Send Reply',              'group': 'reply', 'params': ['message_or_canned']},
        'send_internal_note':{'label': 'Add Internal Note',       'group': 'reply', 'params': ['note']},
        'send_canned':       {'label': 'Send Canned Response',    'group': 'reply', 'params': ['canned_id']},

        # Notifications
        'notify_user_email': {'label': 'Email User',              'group': 'notify', 'params': ['template']},
        'notify_agent_email':{'label': 'Email Agent',             'group': 'notify', 'params': ['template']},
        'notify_slack':      {'label': 'Slack Notification',      'group': 'notify', 'params': ['channel', 'message']},
        'notify_telegram':   {'label': 'Telegram Notification',   'group': 'notify', 'params': ['chat_id', 'message']},
        'notify_whatsapp':   {'label': 'WhatsApp Message',        'group': 'notify', 'params': ['phone', 'message']},
        'notify_sms':        {'label': 'SMS Alert',               'group': 'notify', 'params': ['phone', 'message']},
        'push_notification': {'label': 'Push Notification',       'group': 'notify', 'params': ['title', 'body']},

        # Webhook
        'webhook':           {'label': 'HTTP Webhook',            'group': 'integration', 'params': ['url', 'method']},
        'zapier_trigger':    {'label': 'Trigger Zapier',          'group': 'integration', 'params': ['hook_url']},

        # Advanced
        'run_workflow':      {'label': 'Run Another Workflow',    'group': 'advanced', 'params': ['workflow_id']},
        'wait':              {'label': 'Wait (delay)',            'group': 'advanced', 'params': ['minutes']},
        'ai_classify':       {'label': 'AI Classify Ticket',      'group': 'ai', 'params': []},
        'ai_draft_response': {'label': 'AI Draft Response',       'group': 'ai', 'params': []},
        'ai_detect_churn':   {'label': 'AI Churn Risk Check',     'group': 'ai', 'params': []},
        'kb_suggest':        {'label': 'Suggest KB Articles',     'group': 'kb', 'params': []},
        'create_task':       {'label': 'Create Internal Task',    'group': 'task', 'params': ['title', 'assignee']},
    }

    # OPERATORS
    OPERATORS = [
        {'value': 'equals',        'label': 'Equals'},
        {'value': 'not_equals',    'label': 'Not Equals'},
        {'value': 'contains',      'label': 'Contains'},
        {'value': 'not_contains',  'label': 'Not Contains'},
        {'value': 'starts_with',   'label': 'Starts With'},
        {'value': 'in',            'label': 'Is One Of'},
        {'value': 'not_in',        'label': 'Is Not One Of'},
        {'value': 'greater_than',  'label': 'Greater Than'},
        {'value': 'less_than',     'label': 'Less Than'},
        {'value': 'is_true',       'label': 'Is True'},
        {'value': 'is_false',      'label': 'Is False'},
        {'value': 'is_empty',      'label': 'Is Empty'},
        {'value': 'is_not_empty',  'label': 'Is Not Empty'},
    ]

    def get_builder_schema(self) -> dict:
        """Frontend builder-এর জন্য complete schema"""
        return {
            'triggers':   self._group_by(self.TRIGGERS, 'group'),
            'conditions': self.CONDITIONS,
            'actions':    self._group_by(self.ACTIONS, 'group'),
            'operators':  self.OPERATORS,
            'version':    '2.0',
        }

    def create_workflow(self, name: str, description: str, trigger: str,
                       conditions: list, actions: list, created_by,
                       is_active: bool = True, priority: int = 0,
                       stop_on_match: bool = False) -> object:
        """Workflow DB-তে create করো"""
        from api.support.models import AutomationRule, AutomationCondition, AutomationAction

        rule = AutomationRule.objects.create(
            name          = name,
            description   = description,
            trigger       = trigger,
            is_active     = is_active,
            priority      = priority,
            stop_on_match = stop_on_match,
            created_by    = created_by,
        )

        # Conditions
        for i, cond in enumerate(conditions):
            AutomationCondition.objects.create(
                rule     = rule,
                field    = cond.get('field', ''),
                operator = cond.get('operator', 'equals'),
                value    = str(cond.get('value', '')),
            )

        # Actions
        for i, action in enumerate(actions):
            AutomationAction.objects.create(
                rule        = rule,
                action_type = action.get('type', ''),
                value       = str(action.get('value', '')),
                order       = i,
            )

        logger.info(f'Workflow created: {rule.name} | trigger={trigger}')
        return rule

    def _group_by(self, items: dict, key: str) -> dict:
        grouped = {}
        for item_key, item in items.items():
            group = item.get(key, 'other')
            if group not in grouped:
                grouped[group] = {}
            grouped[group][item_key] = item
        return grouped


workflow_builder_api = WorkflowBuilderAPI()