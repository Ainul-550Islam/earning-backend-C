"""
api/support/livechat/chatbot_builder.py
FILE 23/70 — No-Code Chatbot Flow Builder

Admin visually chatbot flows design করতে পারবে।
Drag-and-drop interface → JSON flow definition।

Flow Structure:
- Nodes: message, question, condition, action
- Edges: connections between nodes
- Variables: user input storage

Example Flow:
Start → Greet → Ask Category → [Branch] → Handle Payment/KYC/Other
"""
import logging
import uuid
from django.utils import timezone

logger = logging.getLogger(__name__)


class ChatbotFlowBuilder:
    """
    Chatbot flow builder — CRUD operations for bot flows।
    Frontend drag-and-drop interface-এর backend।
    """

    # ──────────────────────────────────────────
    # NODE TYPES
    # ──────────────────────────────────────────
    NODE_TYPES = {
        'message':    {'label': 'Send Message',      'icon': '💬', 'can_connect_to': ['message','question','condition','action','end']},
        'question':   {'label': 'Ask Question',       'icon': '❓', 'can_connect_to': ['message','condition','action']},
        'condition':  {'label': 'Condition Branch',   'icon': '🔀', 'can_connect_to': ['message','question','action','end']},
        'action':     {'label': 'Perform Action',     'icon': '⚡', 'can_connect_to': ['message','question','end']},
        'kb_search':  {'label': 'Search Knowledge Base','icon':'📚','can_connect_to': ['message','question','end']},
        'ticket':     {'label': 'Create Ticket',      'icon': '🎫', 'can_connect_to': ['message','end']},
        'handoff':    {'label': 'Transfer to Agent',  'icon': '👤', 'can_connect_to': ['end']},
        'end':        {'label': 'End Flow',           'icon': '🔚', 'can_connect_to': []},
    }

    # ──────────────────────────────────────────
    # DEFAULT FLOWS (built-in)
    # ──────────────────────────────────────────
    DEFAULT_FLOWS = {
        'support_flow': {
            'name':        'Main Support Flow',
            'description': 'Default support bot flow',
            'is_default':  True,
            'nodes': [
                {
                    'id':      'start',
                    'type':    'message',
                    'order':   0,
                    'content': 'Hello! Welcome to Support. How can I help you today?',
                    'delay_ms':500,
                },
                {
                    'id':      'ask_category',
                    'type':    'question',
                    'order':   1,
                    'content': 'Please select your issue:',
                    'options': [
                        {'label': '💰 Payment Issue',   'value': 'payment'},
                        {'label': '💸 Withdrawal',       'value': 'withdrawal'},
                        {'label': '🪙 Missing Coins',    'value': 'coins'},
                        {'label': '👤 Account Problem',  'value': 'account'},
                        {'label': '🔒 Fraud Report',     'value': 'fraud'},
                        {'label': '❓ Other',            'value': 'other'},
                    ],
                    'variable': 'category',
                },
                {
                    'id':      'branch_category',
                    'type':    'condition',
                    'order':   2,
                    'conditions': [
                        {'if': 'category == payment',    'goto': 'handle_payment'},
                        {'if': 'category == withdrawal', 'goto': 'handle_withdrawal'},
                        {'if': 'category == fraud',      'goto': 'handle_fraud'},
                        {'else': True,                   'goto': 'handle_general'},
                    ],
                },
                {
                    'id':      'handle_payment',
                    'type':    'message',
                    'order':   3,
                    'content': 'For payment issues, please share your transaction ID. Our payment team will investigate within 24 hours.',
                    'next':    'create_ticket',
                },
                {
                    'id':      'handle_withdrawal',
                    'type':    'message',
                    'order':   3,
                    'content': 'Withdrawals typically process within 1-3 business days. Would you like to check your withdrawal status or create a support ticket?',
                    'options': [
                        {'label': 'Check Status', 'value': 'check_status'},
                        {'label': 'Create Ticket','value': 'create_ticket'},
                    ],
                    'variable':'withdrawal_action',
                    'next':    'handle_withdrawal_action',
                },
                {
                    'id':      'handle_fraud',
                    'type':    'action',
                    'order':   3,
                    'action':  'escalate_to_security',
                    'content': '🚨 Your fraud report has been escalated to our security team immediately. An agent will contact you within 2 hours.',
                    'next':    'handoff_to_agent',
                },
                {
                    'id':      'handle_general',
                    'type':    'kb_search',
                    'order':   3,
                    'content': 'Let me search our knowledge base for you...',
                    'next':    'show_kb_results',
                },
                {
                    'id':      'create_ticket',
                    'type':    'ticket',
                    'order':   4,
                    'content': 'Creating a support ticket for you...',
                    'ticket_data': {
                        'category': '{{category}}',
                        'priority': 'medium',
                    },
                    'next':    'ticket_created',
                },
                {
                    'id':      'ticket_created',
                    'type':    'message',
                    'order':   5,
                    'content': '✅ Your ticket {{ticket_id}} has been created! Our team will respond within 24 hours. Is there anything else I can help with?',
                    'options': [
                        {'label': 'Talk to Agent', 'value': 'handoff'},
                        {'label': 'That\'s all',   'value': 'end'},
                    ],
                },
                {
                    'id':      'handoff_to_agent',
                    'type':    'handoff',
                    'order':   6,
                    'content': 'Connecting you to a support agent. Please wait...',
                    'reason':  '{{category}} issue',
                },
                {
                    'id':   'end_flow',
                    'type': 'end',
                    'order':7,
                    'content': 'Thank you for contacting us! Have a great day! 😊',
                },
            ],
            'edges': [
                {'from': 'start',           'to': 'ask_category'},
                {'from': 'ask_category',    'to': 'branch_category'},
                {'from': 'branch_category', 'to': 'handle_payment',    'condition': 'payment'},
                {'from': 'branch_category', 'to': 'handle_withdrawal', 'condition': 'withdrawal'},
                {'from': 'branch_category', 'to': 'handle_fraud',      'condition': 'fraud'},
                {'from': 'branch_category', 'to': 'handle_general',    'condition': 'else'},
                {'from': 'handle_payment',  'to': 'create_ticket'},
                {'from': 'handle_fraud',    'to': 'handoff_to_agent'},
                {'from': 'create_ticket',   'to': 'ticket_created'},
                {'from': 'handoff_to_agent','to': 'end_flow'},
            ],
        }
    }

    # ──────────────────────────────────────────
    # CRUD OPERATIONS
    # ──────────────────────────────────────────
    def create_flow(self, name: str, description: str, created_by) -> dict:
        """New bot flow create করো"""
        flow_id = str(uuid.uuid4())[:12]
        flow    = {
            'id':          flow_id,
            'name':        name,
            'description': description,
            'is_active':   False,
            'is_default':  False,
            'nodes':       [self._create_start_node()],
            'edges':       [],
            'created_by':  str(created_by.id),
            'created_at':  timezone.now().isoformat(),
            'updated_at':  timezone.now().isoformat(),
        }
        self._save_flow(flow_id, flow)
        return flow

    def get_flow(self, flow_id: str) -> dict | None:
        """Flow fetch করো"""
        # Check default flows
        if flow_id in self.DEFAULT_FLOWS:
            return self.DEFAULT_FLOWS[flow_id]
        return self._load_flow(flow_id)

    def update_flow(self, flow_id: str, updates: dict) -> dict | None:
        """Flow update করো"""
        flow = self._load_flow(flow_id)
        if not flow:
            return None

        allowed_updates = ['name', 'description', 'is_active', 'nodes', 'edges', 'settings']
        for key in allowed_updates:
            if key in updates:
                flow[key] = updates[key]

        flow['updated_at'] = timezone.now().isoformat()
        self._save_flow(flow_id, flow)
        return flow

    def delete_flow(self, flow_id: str) -> bool:
        """Flow delete করো"""
        try:
            from django.core.cache import cache
            cache.delete(f'chatbot_flow:{flow_id}')
            return True
        except Exception:
            return False

    def list_flows(self) -> list:
        """All flows list করো"""
        flows = list(self.DEFAULT_FLOWS.values())
        # Add DB/cache stored flows
        return flows

    def activate_flow(self, flow_id: str) -> bool:
        """Flow activate করো"""
        flow = self._load_flow(flow_id)
        if not flow:
            return False
        flow['is_active'] = True
        self._save_flow(flow_id, flow)
        return True

    # ──────────────────────────────────────────
    # NODE OPERATIONS
    # ──────────────────────────────────────────
    def add_node(self, flow_id: str, node_type: str, content: str, position: dict = None) -> dict | None:
        """Flow-এ node add করো"""
        if node_type not in self.NODE_TYPES:
            raise ValueError(f'Invalid node type: {node_type}')

        flow = self._load_flow(flow_id)
        if not flow:
            return None

        node = {
            'id':       str(uuid.uuid4())[:8],
            'type':     node_type,
            'content':  content,
            'position': position or {'x': 0, 'y': 0},
            'options':  [],
            'next':     None,
        }
        flow['nodes'].append(node)
        flow['updated_at'] = timezone.now().isoformat()
        self._save_flow(flow_id, flow)
        return node

    def update_node(self, flow_id: str, node_id: str, updates: dict) -> bool:
        """Node update করো"""
        flow = self._load_flow(flow_id)
        if not flow:
            return False

        for i, node in enumerate(flow['nodes']):
            if node['id'] == node_id:
                flow['nodes'][i].update(updates)
                flow['updated_at'] = timezone.now().isoformat()
                self._save_flow(flow_id, flow)
                return True
        return False

    def delete_node(self, flow_id: str, node_id: str) -> bool:
        """Node delete করো"""
        flow = self._load_flow(flow_id)
        if not flow:
            return False

        flow['nodes'] = [n for n in flow['nodes'] if n['id'] != node_id]
        flow['edges'] = [e for e in flow.get('edges', [])
                        if e['from'] != node_id and e['to'] != node_id]
        flow['updated_at'] = timezone.now().isoformat()
        self._save_flow(flow_id, flow)
        return True

    def connect_nodes(self, flow_id: str, from_id: str, to_id: str, condition: str = None) -> bool:
        """Two nodes connect করো"""
        flow = self._load_flow(flow_id)
        if not flow:
            return False

        edge = {'from': from_id, 'to': to_id}
        if condition:
            edge['condition'] = condition

        if edge not in flow.get('edges', []):
            flow.setdefault('edges', []).append(edge)
            self._save_flow(flow_id, flow)
        return True

    # ──────────────────────────────────────────
    # VALIDATION
    # ──────────────────────────────────────────
    def validate_flow(self, flow: dict) -> dict:
        """Flow validate করো before activation"""
        errors   = []
        warnings = []
        nodes    = {n['id']: n for n in flow.get('nodes', [])}
        edges    = flow.get('edges', [])

        # Must have start node
        if 'start' not in nodes and not any(n.get('order') == 0 for n in flow.get('nodes', [])):
            errors.append('Flow must have a start node')

        # Must have end node
        has_end = any(n['type'] == 'end' for n in flow.get('nodes', []))
        if not has_end:
            warnings.append('Flow has no end node — will leave users hanging')

        # Must have handoff option for complex issues
        has_handoff = any(n['type'] == 'handoff' for n in flow.get('nodes', []))
        if not has_handoff:
            warnings.append('Flow has no agent handoff — users cannot escalate')

        # Check for orphan nodes
        connected_ids = set()
        for edge in edges:
            connected_ids.add(edge['from'])
            connected_ids.add(edge['to'])

        for node in flow.get('nodes', []):
            if node['id'] not in connected_ids and node['type'] != 'end':
                if len(flow.get('nodes', [])) > 1:
                    warnings.append(f'Node "{node.get("id")}" is not connected to any other node')

        return {
            'is_valid':  len(errors) == 0,
            'errors':    errors,
            'warnings':  warnings,
            'node_count':len(flow.get('nodes', [])),
            'edge_count':len(edges),
        }

    # ──────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────
    def _create_start_node(self) -> dict:
        return {
            'id':      'start',
            'type':    'message',
            'order':   0,
            'content': 'Hello! How can I help you today?',
            'next':    None,
        }

    def _save_flow(self, flow_id: str, flow: dict) -> None:
        from django.core.cache import cache
        import json
        cache.set(f'chatbot_flow:{flow_id}', json.dumps(flow), timeout=86400 * 30)

    def _load_flow(self, flow_id: str) -> dict | None:
        from django.core.cache import cache
        import json
        data = cache.get(f'chatbot_flow:{flow_id}')
        return json.loads(data) if data else None

    def get_node_types(self) -> dict:
        """Available node types for frontend"""
        return self.NODE_TYPES

    def export_flow(self, flow_id: str) -> str:
        """Flow export as JSON"""
        import json
        flow = self.get_flow(flow_id)
        return json.dumps(flow, indent=2) if flow else ''

    def import_flow(self, json_str: str, created_by) -> dict | None:
        """JSON from export → new flow"""
        import json
        try:
            flow           = json.loads(json_str)
            flow['id']     = str(uuid.uuid4())[:12]
            flow['created_by'] = str(created_by.id)
            flow['created_at'] = timezone.now().isoformat()
            flow['is_active']  = False
            self._save_flow(flow['id'], flow)
            return flow
        except Exception as e:
            logger.error(f'Flow import failed: {e}')
            return None


# Singleton
chatbot_builder = ChatbotFlowBuilder()