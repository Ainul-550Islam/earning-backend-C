# api/support/enums.py  — WORLD #1 COMPLETE
"""Python Enum classes for type-safe status/type checking."""
from enum import Enum


class TicketStatus(str, Enum):
    OPEN         = 'open'
    IN_PROGRESS  = 'in_progress'
    WAITING_USER = 'waiting_user'
    RESOLVED     = 'resolved'
    CLOSED       = 'closed'
    SPAM         = 'spam'

    @classmethod
    def active(cls):
        return [cls.OPEN, cls.IN_PROGRESS, cls.WAITING_USER]

    @classmethod
    def closed(cls):
        return [cls.RESOLVED, cls.CLOSED]


class TicketPriority(str, Enum):
    LOW    = 'low'
    MEDIUM = 'medium'
    HIGH   = 'high'
    URGENT = 'urgent'

    @property
    def sla_first_response_hours(self) -> int:
        return {'low': 24, 'medium': 8, 'high': 4, 'urgent': 1}[self.value]

    @property
    def sla_resolution_hours(self) -> int:
        return {'low': 72, 'medium': 48, 'high': 24, 'urgent': 4}[self.value]

    @property
    def order(self) -> int:
        return {'low': 1, 'medium': 2, 'high': 3, 'urgent': 4}[self.value]


class TicketCategory(str, Enum):
    PAYMENT    = 'payment'
    WITHDRAWAL = 'withdrawal'
    COINS      = 'coins'
    ACCOUNT    = 'account'
    FRAUD      = 'fraud'
    KYC        = 'kyc'
    TECHNICAL  = 'technical'
    REFERRAL   = 'referral'
    OFFER      = 'offer'
    OTHER      = 'other'

    @property
    def default_priority(self) -> str:
        from api.support.choices import CATEGORY_PRIORITY_MAP
        return CATEGORY_PRIORITY_MAP.get(self.value, 'medium')


class ChatStatus(str, Enum):
    WAITING = 'waiting'
    ACTIVE  = 'active'
    ENDED   = 'ended'


class AgentRole(str, Enum):
    AGENT          = 'agent'
    SENIOR_AGENT   = 'senior_agent'
    SUPERVISOR     = 'supervisor'
    MANAGER        = 'manager'
    ACCOUNT_MANAGER= 'account_manager'

    @property
    def is_supervisor(self) -> bool:
        return self in (self.SUPERVISOR, self.MANAGER, self.ACCOUNT_MANAGER)


class NotificationChannel(str, Enum):
    EMAIL    = 'email'
    SMS      = 'sms'
    PUSH     = 'push'
    TELEGRAM = 'telegram'
    WHATSAPP = 'whatsapp'
    SLACK    = 'slack'


class SLABreachType(str, Enum):
    FIRST_RESPONSE = 'first_response'
    RESOLUTION     = 'resolution'


class DisputeStatus(str, Enum):
    PENDING       = 'pending'
    INVESTIGATING = 'investigating'
    APPROVED      = 'approved'
    REJECTED      = 'rejected'
    NEEDS_PROOF   = 'needs_proof'


class KBStatus(str, Enum):
    DRAFT     = 'draft'
    PUBLISHED = 'published'
    ARCHIVED  = 'archived'


class AutomationTrigger(str, Enum):
    TICKET_CREATED        = 'ticket_created'
    TICKET_UPDATED        = 'ticket_updated'
    TICKET_STATUS_CHANGED = 'ticket_status_changed'
    REPLY_RECEIVED        = 'reply_received'
    AGENT_REPLIED         = 'agent_replied'
    SLA_WARNING           = 'sla_warning'
    SLA_BREACH            = 'sla_first_response_breach'
    IDLE_1H               = 'ticket_idle_1h'
    IDLE_24H              = 'ticket_idle_24h'
    IDLE_72H              = 'ticket_idle_72h'
    ESCALATED             = 'ticket_escalated'
    RESOLVED              = 'ticket_resolved'
    RATED                 = 'ticket_rated'
    MANUAL                = 'manual'