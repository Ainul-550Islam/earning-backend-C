# api/support/admin/__init__.py
from .ticket_admin import SupportTicketAdmin
from .settings_admin import SupportSettingsAdmin
from .faq_admin import FAQAdmin
from .agent_admin import SupportAgentAdmin
from .chat_admin import ChatSessionAdmin
from .kb_admin import KBCategoryAdmin, KBArticleAdmin
from .sla_admin import SLAPolicyAdmin, SLABreachAdmin
from .automation_admin import AutomationRuleAdmin
from .canned_response_admin import CannedResponseAdmin
from .insight_admin import SupportInsightAdmin
from .department_admin import DepartmentAdmin