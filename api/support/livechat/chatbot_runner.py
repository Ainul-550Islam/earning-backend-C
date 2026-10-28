"""
api/support/livechat/chatbot_runner.py
FILE 24/70 — Chatbot Flow Runner

Builder-এ তৈরি flow execute করো।
User message → correct node → response।

State machine:
- Current node track করো
- Variable store করো
- Condition evaluate করো
- Action execute করো
"""
import logging
import re
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

STATE_TTL = 1800  # 30 minutes


class ChatbotFlowRunner:
    """
    Chatbot flow execution engine।
    Session-based state management।
    """

    # ──────────────────────────────────────────
    # MAIN: PROCESS USER MESSAGE
    # ──────────────────────────────────────────
    def process_message(self, session_id: str, user_message: str, user=None) -> dict:
        """
        User message process করো।
        Returns: {
            messages: [str],        # Bot response messages
            options: [dict],        # Quick reply options
            is_handoff: bool,       # Transfer to agent
            is_end: bool,           # Flow ended
            ticket_created: dict,   # If ticket was created
            variables: dict,        # Current variable state
        }
        """
        # Get or initialize session state
        state = self._get_state(session_id)

        if not state:
            # Start new flow
            state = self._init_state(session_id, user)
            return self._execute_node(state, 'start', user)

        # Process user input
        current_node_id = state.get('current_node', 'start')
        node            = self._get_node(state, current_node_id)

        if not node:
            return self._error_response('Flow error. Please try again.')

        # Handle option selection
        if node.get('options'):
            selected = self._match_option(user_message, node['options'])
            if selected:
                # Save to variables
                var_name = node.get('variable')
                if var_name:
                    state['variables'][var_name] = selected['value']

                next_node = selected.get('goto') or node.get('next')
                self._save_state(session_id, state)
                return self._execute_node(state, next_node, user)
            else:
                # Invalid option
                return {
                    'messages': ['Please select one of the options above.'],
                    'options':  node.get('options', []),
                    'is_handoff':False,
                    'is_end':    False,
                }

        # Handle free text input
        if node.get('expects_input'):
            var_name = node.get('variable')
            if var_name and user_message.strip():
                state['variables'][var_name] = user_message.strip()

            next_node = node.get('next')
            self._save_state(session_id, state)
            return self._execute_node(state, next_node, user)

        # Default: move to next
        next_node = node.get('next')
        if next_node:
            return self._execute_node(state, next_node, user)

        return self._error_response('I\'m not sure how to help with that. Let me connect you to an agent.')

    def start_flow(self, session_id: str, flow_id: str = 'support_flow', user=None) -> dict:
        """Flow শুরু করো"""
        flow  = self._load_flow(flow_id)
        state = {
            'session_id':    session_id,
            'flow_id':       flow_id,
            'flow':          flow,
            'current_node':  'start',
            'variables':     {},
            'started_at':    timezone.now().isoformat(),
            'message_count': 0,
            'user_id':       str(user.id) if user else None,
        }
        self._save_state(session_id, state)
        return self._execute_node(state, 'start', user)

    # ──────────────────────────────────────────
    # NODE EXECUTOR
    # ──────────────────────────────────────────
    def _execute_node(self, state: dict, node_id: str, user=None) -> dict:
        """Node execute করো এবং response তৈরি করো"""
        node = self._get_node(state, node_id)

        if not node:
            return self._handoff_response(state, 'No matching node found.')

        state['current_node']  = node_id
        state['message_count'] = state.get('message_count', 0) + 1
        self._save_state(state['session_id'], state)

        node_type = node.get('type', 'message')

        if node_type == 'message':
            return self._execute_message_node(node, state)

        elif node_type == 'question':
            return self._execute_question_node(node, state)

        elif node_type == 'condition':
            return self._execute_condition_node(node, state, user)

        elif node_type == 'action':
            return self._execute_action_node(node, state, user)

        elif node_type == 'kb_search':
            return self._execute_kb_search_node(node, state)

        elif node_type == 'ticket':
            return self._execute_ticket_node(node, state, user)

        elif node_type == 'handoff':
            return self._execute_handoff_node(node, state)

        elif node_type == 'end':
            return self._execute_end_node(node, state)

        return self._handoff_response(state, 'Unknown node type.')

    def _execute_message_node(self, node: dict, state: dict) -> dict:
        content = self._render_template(node.get('content', ''), state['variables'])
        result  = {
            'messages':      [content],
            'options':       node.get('options', []),
            'is_handoff':    False,
            'is_end':        False,
            'ticket_created':None,
            'variables':     state['variables'],
        }
        if node.get('options'):
            node['expects_input'] = False  # Wait for option selection
        elif node.get('next'):
            # Auto-advance if no options
            pass
        return result

    def _execute_question_node(self, node: dict, state: dict) -> dict:
        content = self._render_template(node.get('content', ''), state['variables'])
        node['expects_input'] = True
        return {
            'messages':      [content],
            'options':       node.get('options', []),
            'expects_input': not bool(node.get('options')),
            'is_handoff':    False,
            'is_end':        False,
            'ticket_created':None,
            'variables':     state['variables'],
        }

    def _execute_condition_node(self, node: dict, state: dict, user=None) -> dict:
        """Condition evaluate করো এবং correct branch-এ যাও"""
        conditions = node.get('conditions', [])
        variables  = state['variables']

        next_node = None
        for cond in conditions:
            if cond.get('else'):
                next_node = cond.get('goto')
                continue  # Check other conditions first

            condition_str = list(cond.keys())[0] if cond else ''
            if condition_str == 'else':
                continue

            # Parse condition: "variable == value"
            if self._evaluate_condition(condition_str, variables):
                next_node = cond.get('goto')
                break

        if not next_node:
            # Else branch
            for cond in conditions:
                if cond.get('else'):
                    next_node = cond.get('goto')
                    break

        if next_node:
            return self._execute_node(state, next_node, user)

        return self._handoff_response(state, 'I\'m not sure how to help. Let me connect you to an agent.')

    def _execute_action_node(self, node: dict, state: dict, user=None) -> dict:
        action_type = node.get('action', '')
        content     = self._render_template(node.get('content', ''), state['variables'])

        if action_type == 'escalate_to_security':
            # Escalate ticket/alert
            self._send_security_alert(state, user)

        elif action_type == 'set_priority_urgent':
            state['ticket_priority'] = 'urgent'

        result = {
            'messages':      [content] if content else [],
            'options':       node.get('options', []),
            'is_handoff':    False,
            'is_end':        False,
            'ticket_created':None,
            'variables':     state['variables'],
        }

        next_node = node.get('next')
        if next_node:
            next_result = self._execute_node(state, next_node, user)
            result['messages'].extend(next_result.get('messages', []))
            result.update({k: v for k, v in next_result.items() if k != 'messages'})

        return result

    def _execute_kb_search_node(self, node: dict, state: dict) -> dict:
        """KB search করো এবং results দেখাও"""
        query   = state['variables'].get('query') or state['variables'].get('issue', '')
        content = self._render_template(node.get('content', 'Searching...'), state['variables'])
        messages= [content]

        if query:
            try:
                from api.support.services.knowledge_base.KBSearchService import kb_search_service
                results = kb_search_service.search(query, limit=3)
                if results:
                    messages.append('Here are some helpful articles:')
                    for r in results:
                        messages.append(f"📚 {r['title']}")
                    messages.append('\nDid any of these help? Or would you like to create a support ticket?')
                    return {
                        'messages':      messages,
                        'options':       [
                            {'label': '✅ Yes, that helped!', 'value': 'resolved', 'goto': 'end_flow'},
                            {'label': '🎫 Create Ticket',     'value': 'ticket',   'goto': 'create_ticket'},
                            {'label': '👤 Talk to Agent',      'value': 'handoff',  'goto': 'handoff_to_agent'},
                        ],
                        'is_handoff':    False,
                        'is_end':        False,
                        'ticket_created':None,
                        'variables':     state['variables'],
                    }
            except Exception as e:
                logger.warning(f'KB search in bot failed: {e}')

        return self._execute_node(state, node.get('next', 'create_ticket'), None)

    def _execute_ticket_node(self, node: dict, state: dict, user=None) -> dict:
        """Ticket create করো"""
        ticket_created = None
        messages       = []

        if user:
            try:
                from api.support.models import SupportTicket
                from api.support.choices import CATEGORY_PRIORITY_MAP
                vars_      = state['variables']
                category   = vars_.get('category', 'other')
                priority   = state.get('ticket_priority') or CATEGORY_PRIORITY_MAP.get(category, 'medium')
                description= vars_.get('description') or vars_.get('issue') or 'Support request from chat bot'

                ticket = SupportTicket.objects.create(
                    user        = user,
                    category    = category,
                    subject     = vars_.get('subject', description[:100]),
                    description = description[:2000],
                    priority    = priority,
                    status      = 'open',
                    channel     = 'chat',
                    tenant      = getattr(user, 'tenant', None),
                )
                state['variables']['ticket_id'] = ticket.ticket_id
                ticket_created = {
                    'ticket_id': ticket.ticket_id,
                    'priority':  ticket.priority,
                    'category':  ticket.category,
                }
                content = self._render_template(node.get('content', ''), state['variables'])
                messages.append(content or f'✅ Ticket #{ticket.ticket_id} created successfully!')
            except Exception as e:
                logger.error(f'Bot ticket creation failed: {e}')
                messages.append('I had trouble creating your ticket. Let me connect you to an agent.')
                return self._handoff_response(state, None, additional_messages=messages)
        else:
            messages.append('Please log in to create a support ticket.')

        self._save_state(state['session_id'], state)
        next_result = self._execute_node(state, node.get('next', 'end_flow'), user) if node.get('next') else {}

        return {
            'messages':      messages + next_result.get('messages', []),
            'options':       next_result.get('options', []),
            'is_handoff':    next_result.get('is_handoff', False),
            'is_end':        next_result.get('is_end', False),
            'ticket_created':ticket_created,
            'variables':     state['variables'],
        }

    def _execute_handoff_node(self, node: dict, state: dict) -> dict:
        content = self._render_template(node.get('content', 'Connecting to agent...'), state['variables'])
        return {
            'messages':      [content],
            'options':       [],
            'is_handoff':    True,
            'handoff_reason':self._render_template(node.get('reason', ''), state['variables']),
            'is_end':        False,
            'ticket_created':None,
            'variables':     state['variables'],
        }

    def _execute_end_node(self, node: dict, state: dict) -> dict:
        content = self._render_template(
            node.get('content', 'Thank you! Have a great day! 😊'),
            state['variables']
        )
        self._clear_state(state['session_id'])
        return {
            'messages':      [content],
            'options':       [],
            'is_handoff':    False,
            'is_end':        True,
            'ticket_created':None,
            'variables':     state['variables'],
        }

    # ──────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────
    def _evaluate_condition(self, condition_str: str, variables: dict) -> bool:
        """Simple condition evaluation"""
        # Format: "variable == value" or "variable != value"
        match = re.match(r'(\w+)\s*(==|!=|>|<|>=|<=)\s*(\w+)', condition_str.strip())
        if not match:
            return False

        var_name, operator, value = match.groups()
        var_value = str(variables.get(var_name, ''))

        if operator == '==':  return var_value == value
        if operator == '!=':  return var_value != value
        if operator == '>':   return float(var_value or 0) > float(value)
        if operator == '<':   return float(var_value or 0) < float(value)
        if operator == '>=':  return float(var_value or 0) >= float(value)
        if operator == '<=':  return float(var_value or 0) <= float(value)
        return False

    def _match_option(self, user_input: str, options: list) -> dict | None:
        """User input-এর সাথে option match করো"""
        text = user_input.lower().strip()
        for opt in options:
            if (text == opt.get('value', '').lower() or
                text == opt.get('label', '').lower() or
                text in opt.get('label', '').lower()):
                return opt
        return None

    def _render_template(self, template: str, variables: dict) -> str:
        """{{variable}} replace করো"""
        for key, value in variables.items():
            template = template.replace(f'{{{{{key}}}}}', str(value))
        return template

    def _handoff_response(self, state: dict, message: str = None, additional_messages: list = None) -> dict:
        messages = additional_messages or []
        if message:
            messages.insert(0, message)
        messages.append('Connecting you to a support agent. Please wait...')
        return {
            'messages':      messages,
            'options':       [],
            'is_handoff':    True,
            'is_end':        False,
            'ticket_created':None,
            'variables':     state.get('variables', {}),
        }

    def _error_response(self, message: str) -> dict:
        return {
            'messages':      [message, 'Connecting you to a support agent...'],
            'options':       [],
            'is_handoff':    True,
            'is_end':        False,
            'ticket_created':None,
            'variables':     {},
        }

    def _get_node(self, state: dict, node_id: str) -> dict | None:
        flow  = state.get('flow', {})
        nodes = {n['id']: n for n in flow.get('nodes', [])}
        return nodes.get(node_id)

    def _load_flow(self, flow_id: str) -> dict:
        from api.support.livechat.chatbot_builder import chatbot_builder
        return chatbot_builder.get_flow(flow_id) or {}

    def _get_state(self, session_id: str) -> dict | None:
        return cache.get(f'bot_state:{session_id}')

    def _save_state(self, session_id: str, state: dict) -> None:
        cache.set(f'bot_state:{session_id}', state, timeout=STATE_TTL)

    def _clear_state(self, session_id: str) -> None:
        cache.delete(f'bot_state:{session_id}')

    def _init_state(self, session_id: str, user=None) -> dict:
        flow = self._load_flow('support_flow')
        return {
            'session_id':    session_id,
            'flow_id':       'support_flow',
            'flow':          flow,
            'current_node':  'start',
            'variables':     {},
            'started_at':    timezone.now().isoformat(),
            'message_count': 0,
            'user_id':       str(user.id) if user else None,
        }

    def _send_security_alert(self, state: dict, user=None) -> None:
        try:
            from api.support.integrations.slack_integration import slack_integration
            logger.warning(f'Security alert from bot — user: {state.get("user_id")}')
        except Exception:
            pass


# Singleton
chatbot_runner = ChatbotFlowRunner()