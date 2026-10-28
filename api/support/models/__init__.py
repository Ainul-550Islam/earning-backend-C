# api/support/models/__init__.py  — WORLD #1
# Exports all 42 models from split files
from .core import SupportSettings, SupportTicket, FAQ
from .ticket import (
    TicketMessage, TicketAttachment, TicketTag, TicketTagging,
    TicketAssignment, TicketSLA, TicketRating, TicketMerge,
)
from .livechat import (
    ChatSession, ChatMessage, ChatAttachment, ChatRating, ChatQueue, ChatTranscript,
)
from .agent import (
    Department, SupportAgent, AgentShift, AgentPerformance, AgentSkill, AgentStatus,
)
from .knowledge_base import (
    KBCategory, KBArticle, KBArticleVersion, KBSearch, KBFeedback,
)
from .automation import (
    AutomationRule, AutomationCondition, AutomationAction, AutomationLog, CannedResponse,
)
from .sla import SLAPolicy, SLABreach, BusinessHours, Holiday
from .notification_log import SupportNotificationLog
from .analytics import (
    SupportInsight, CSATReport, AgentReport, ChannelReport, TopicCluster,
)

# Legacy models (still in main models.py for backward compat)
# These are re-exported here so imports work from either location
__all__ = [
    'SupportSettings', 'SupportTicket', 'FAQ',
    'TicketMessage', 'TicketAttachment', 'TicketTag', 'TicketTagging',
    'TicketAssignment', 'TicketSLA', 'TicketRating', 'TicketMerge',
    'ChatSession', 'ChatMessage', 'ChatAttachment', 'ChatRating', 'ChatQueue', 'ChatTranscript',
    'Department', 'SupportAgent', 'AgentShift', 'AgentPerformance', 'AgentSkill', 'AgentStatus',
    'KBCategory', 'KBArticle', 'KBArticleVersion', 'KBSearch', 'KBFeedback',
    'AutomationRule', 'AutomationCondition', 'AutomationAction', 'AutomationLog', 'CannedResponse',
    'SLAPolicy', 'SLABreach', 'BusinessHours', 'Holiday',
    'SupportInsight', 'CSATReport', 'AgentReport', 'ChannelReport', 'TopicCluster',
]

# --- restored from the shadowed legacy models.py / cpa/models.py ---
from .audit import TicketAuditLog  # noqa: E402
from .cpa import (  # noqa: E402
    OfferDispute, WithdrawalDispute, NetworkAnnouncement, PublisherProfile,
)

__all__ += [
    'TicketAuditLog', 'OfferDispute', 'WithdrawalDispute',
    'NetworkAnnouncement', 'PublisherProfile',
]
