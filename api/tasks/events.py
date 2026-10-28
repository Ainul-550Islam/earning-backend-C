"""
api/tasks/events.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Domain Events — strongly-typed event objects and dispatcher.
All platform events flow through here before reaching the
EventBus, KB engine, or WebSocket broadcast layer.

Event flow:
    1. Domain action occurs (task completion, withdrawal, etc.)
    2. Code creates a typed Event object
    3. EventDispatcher.dispatch(event) runs:
       a. Fires EventBus.emit()
       b. Fires kb_signal (KB rules evaluation)
       c. Optionally broadcasts to WebSocket channels
       d. Persists to EventLog for audit trail
    4. Async Celery tasks handle downstream effects

Usage:
    from api.tasks.events import EventDispatcher, TaskCompletedEvent

    EventDispatcher.dispatch(TaskCompletedEvent(
        user_id=123,
        task_id='TASK_001',
        reward_amount=Decimal('0.50'),
        ip_address='1.2.3.4',
    ))
"""

import logging
import uuid
from dataclasses import dataclass, field, asdict
from decimal import Decimal
from typing import Any, Dict, List, Optional, Type
from django.utils import timezone

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# BASE EVENT
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class BaseEvent:
    """Base class for all platform domain events."""

    event_name:    str = field(init=False, default='base.event')
    event_id:      str = field(init=False)
    occurred_at:   str = field(init=False)
    version:       int = field(init=False, default=1)

    def __post_init__(self):
        self.event_id    = str(uuid.uuid4())
        self.occurred_at = timezone.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to a serializable dictionary."""
        d = asdict(self)
        # Convert Decimal to string for JSON serialization
        for key, val in d.items():
            if isinstance(val, Decimal):
                d[key] = str(val)
        return d

    def to_payload(self) -> Dict[str, Any]:
        """Return payload dict for EventBus/KB/WebSocket."""
        return {k: v for k, v in self.to_dict().items()
                if not k.startswith('_') and k not in ('version',)}


# ══════════════════════════════════════════════════════════════════════════════
# TASK EVENTS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TaskCompletedEvent(BaseEvent):
    """Fired when a user successfully completes a task."""
    user_id:       int     = 0
    task_id:       str     = ''
    completion_id: int     = 0
    reward_amount: Decimal = Decimal('0')
    currency:      str     = 'USD'
    ip_address:    str     = ''
    device:        str     = ''
    country:       str     = ''
    category:      str     = ''

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'task.completed'


@dataclass
class TaskFailedEvent(BaseEvent):
    """Fired when a task completion attempt fails validation."""
    user_id:   int = 0
    task_id:   str = ''
    reason:    str = ''
    ip_address: str = ''

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'task.failed'


@dataclass
class TaskActivatedEvent(BaseEvent):
    """Fired when a MasterTask is activated."""
    task_id:   str = ''
    activated_by: int = 0

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'task.activated'


@dataclass
class TaskDeactivatedEvent(BaseEvent):
    """Fired when a MasterTask is deactivated."""
    task_id:     str = ''
    deactivated_by: int = 0
    reason:      str = ''

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'task.deactivated'


# ══════════════════════════════════════════════════════════════════════════════
# USER EVENTS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class UserRegisteredEvent(BaseEvent):
    """Fired when a new user registers."""
    user_id:      int = 0
    username:     str = ''
    email:        str = ''
    referral_code: str = ''
    ip_address:   str = ''
    country:      str = ''

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'user.registered'


@dataclass
class UserVerifiedEvent(BaseEvent):
    """Fired when user email is verified."""
    user_id: int = 0
    email:   str = ''

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'user.verified'


@dataclass
class UserLevelUpEvent(BaseEvent):
    """Fired when user levels up."""
    user_id:   int = 0
    old_level: int = 1
    new_level: int = 2
    xp_points: int = 0

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'user.level_up'


@dataclass
class UserStreakMilestoneEvent(BaseEvent):
    """Fired when user hits a streak milestone (7d, 30d, etc.)."""
    user_id: int = 0
    streak:  int = 0

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'user.streak_milestone'


@dataclass
class UserMilestoneReachedEvent(BaseEvent):
    """Fired when user crosses an earnings milestone."""
    user_id:        int     = 0
    total_earnings: Decimal = Decimal('0')
    milestone:      Decimal = Decimal('0')
    bonus:          Decimal = Decimal('0')

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'user.milestone_reached'


@dataclass
class BadgeAwardedEvent(BaseEvent):
    """Fired when a user earns a badge."""
    user_id:  int = 0
    badge_id: str = ''
    xp_bonus: int = 0

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'user.badge_awarded'


# ══════════════════════════════════════════════════════════════════════════════
# PAYMENT EVENTS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class WithdrawalRequestedEvent(BaseEvent):
    """Fired when a user requests a withdrawal."""
    user_id:          int     = 0
    withdrawal_id:    int     = 0
    amount:           Decimal = Decimal('0')
    payment_method:   str     = ''
    wallet_address:   str     = ''
    ip_address:       str     = ''

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'payment.withdrawal_requested'


@dataclass
class WithdrawalCompletedEvent(BaseEvent):
    """Fired when a withdrawal is successfully processed."""
    user_id:        int     = 0
    withdrawal_id:  int     = 0
    amount:         Decimal = Decimal('0')
    payment_method: str     = ''
    transaction_id: str     = ''

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'payment.completed'


@dataclass
class WithdrawalFailedEvent(BaseEvent):
    """Fired when a withdrawal processing fails."""
    user_id:       int     = 0
    withdrawal_id: int     = 0
    amount:        Decimal = Decimal('0')
    reason:        str     = ''

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'payment.failed'


@dataclass
class USDTFastPaySentEvent(BaseEvent):
    """Fired when USDT Fast Pay is successfully dispatched."""
    user_id:        int     = 0
    usdt_amount:    Decimal = Decimal('0')
    wallet_address: str     = ''
    network:        str     = 'trc20'
    txn_hash:       str     = ''

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'payment.usdt_fast_pay_sent'


# ══════════════════════════════════════════════════════════════════════════════
# OFFER / CPA EVENTS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class OfferConvertedEvent(BaseEvent):
    """Fired when a CPA offer conversion is received via postback."""
    user_id:        int     = 0
    offer_id:       str     = ''
    transaction_id: str     = ''
    payout:         Decimal = Decimal('0')
    status:         str     = 'approved'
    ip_address:     str     = ''
    country:        str     = ''

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'offer.converted'


@dataclass
class OfferClickedEvent(BaseEvent):
    """Fired when a user clicks an offer."""
    user_id:   int = 0
    offer_id:  str = ''
    click_id:  str = ''
    country:   str = ''
    device:    str = ''

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'offer.clicked'


@dataclass
class AppInstalledEvent(BaseEvent):
    """Fired when a CPI app install is verified."""
    publisher_id: int     = 0
    bundle_id:    str     = ''
    platform:     str     = ''
    click_id:     str     = ''
    payout:       Decimal = Decimal('0')
    mmp:          str     = ''

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'cpi.installed'


@dataclass
class SurveyCompletedEvent(BaseEvent):
    """Fired when a survey is completed."""
    user_id:       int     = 0
    survey_id:     str     = ''
    completion_id: int     = 0
    payout:        Decimal = Decimal('0')

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'survey.completed'


@dataclass
class QuizCompletedEvent(BaseEvent):
    """Fired when a personality quiz is completed."""
    user_id:      int     = 0
    quiz_id:      str     = ''
    session_id:   str     = ''
    payout:       Decimal = Decimal('0')
    has_email:    bool    = False

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'quiz.completed'


@dataclass
class EmailSubmittedEvent(BaseEvent):
    """Fired when an email submit offer is completed."""
    user_id:      int     = 0
    offer_id:     str     = ''
    email_hash:   str     = ''
    payout:       Decimal = Decimal('0')

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'email.submitted'


# ══════════════════════════════════════════════════════════════════════════════
# FRAUD EVENTS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FraudDetectedEvent(BaseEvent):
    """Fired when fraud is detected."""
    user_id:     int = 0
    fraud_score: int = 0
    reason:      str = ''
    ip_address:  str = ''
    action_taken: str = ''  # 'flagged' | 'suspended' | 'blocked'

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'fraud.detected'


@dataclass
class AccountSuspendedEvent(BaseEvent):
    """Fired when an account is suspended."""
    user_id:      int = 0
    suspended_by: int = 0
    reason:       str = ''

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'account.suspended'


# ══════════════════════════════════════════════════════════════════════════════
# KYC EVENTS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class KYCApprovedEvent(BaseEvent):
    """Fired when KYC is approved."""
    user_id:  int = 0
    tier:     str = 'basic'
    provider: str = ''

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'kyc.approved'


@dataclass
class KYCRejectedEvent(BaseEvent):
    """Fired when KYC is rejected."""
    user_id:  int = 0
    reason:   str = ''
    provider: str = ''

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'kyc.rejected'


# ══════════════════════════════════════════════════════════════════════════════
# CAMPAIGN EVENTS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class CampaignActivatedEvent(BaseEvent):
    """Fired when an advertiser campaign goes live."""
    campaign_id:   int = 0
    advertiser_id: int = 0
    campaign_type: str = ''

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'campaign.activated'


@dataclass
class CampaignPausedEvent(BaseEvent):
    """Fired when a campaign is paused."""
    campaign_id: int = 0
    reason:      str = ''

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'campaign.paused'


@dataclass
class PublisherTierChangedEvent(BaseEvent):
    """Fired when a publisher's tier changes."""
    user_id:   int = 0
    old_tier:  str = 'bronze'
    new_tier:  str = 'silver'

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'publisher.tier_changed'


# ══════════════════════════════════════════════════════════════════════════════
# CONTENT LOCKER EVENTS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ContentUnlockedEvent(BaseEvent):
    """Fired when content locker is unlocked."""
    user_id:      int = 0
    locker_id:    str = ''
    locker_type:  str = 'content'
    access_mode:  str = '24h'
    payout:       Decimal = Decimal('0')

    def __post_init__(self):
        super().__post_init__()
        self.event_name = 'locker.content_unlocked'


# ══════════════════════════════════════════════════════════════════════════════
# EVENT DISPATCHER
# ══════════════════════════════════════════════════════════════════════════════

class EventDispatcher:
    """
    Central dispatcher for all domain events.
    Coordinates: EventBus, KB engine, WebSocket broadcast, and audit log.
    """

    _handlers: List[Any] = []

    @classmethod
    def dispatch(cls, event: BaseEvent, async_dispatch: bool = True,
                 broadcast_ws: bool = True, persist: bool = True) -> Dict[str, Any]:
        """
        Dispatch a domain event to all registered handlers.

        Args:
            event:          The typed domain event to dispatch
            async_dispatch: If True, fire Celery tasks async
            broadcast_ws:   If True, push to WebSocket channels
            persist:        If True, save to EventLog

        Returns: dispatch summary dict
        """
        payload = event.to_payload()
        summary = {
            'event_id':     event.event_id,
            'event_name':   event.event_name,
            'occurred_at':  event.occurred_at,
            'eventbus':     False,
            'kb':           False,
            'websocket':    False,
            'persisted':    False,
        }

        # 1. EventBus
        try:
            from api.tasks.integration.event_bus import EventBus
            count = EventBus.emit(event.event_name, payload,
                                  async_dispatch=async_dispatch)
            summary['eventbus'] = count > 0
        except Exception as e:
            logger.error(f"[DISPATCH] EventBus emit '{event.event_name}': {e}")

        # 2. KB Engine
        try:
            from api.tasks.signals_kb import fire_kb_event
            result = fire_kb_event(event.event_name, payload)
            summary['kb'] = result.get('count', 0) > 0
        except Exception as e:
            logger.debug(f"[DISPATCH] KB fire '{event.event_name}': {e}")

        # 3. WebSocket broadcast
        if broadcast_ws:
            try:
                cls._ws_broadcast(event, payload)
                summary['websocket'] = True
            except Exception as e:
                logger.debug(f"[DISPATCH] WS broadcast '{event.event_name}': {e}")

        # 4. Persist to EventLog
        if persist:
            try:
                cls._persist_event(event, payload)
                summary['persisted'] = True
            except Exception as e:
                logger.debug(f"[DISPATCH] Persist '{event.event_name}': {e}")

        # 5. Custom handlers
        for handler in cls._handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"[DISPATCH] Custom handler error: {e}")

        logger.debug(
            f"[EVENT] {event.event_name} dispatched: "
            f"eb={summary['eventbus']} kb={summary['kb']}"
        )
        return summary

    @classmethod
    def register_handler(cls, handler) -> None:
        """Register a custom synchronous event handler."""
        cls._handlers.append(handler)

    @classmethod
    def _ws_broadcast(cls, event: BaseEvent, payload: Dict) -> None:
        """Broadcast event to relevant WebSocket groups."""
        try:
            from asgiref.sync import async_to_sync
            from api.tasks.consumers import broadcast_task_event
            user_id = payload.get('user_id')
            if user_id:
                async_to_sync(broadcast_task_event)(
                    user_id, event.event_name, payload
                )
        except Exception as e:
            logger.debug(f"[DISPATCH WS] {e}")

    @classmethod
    def _persist_event(cls, event: BaseEvent, payload: Dict) -> None:
        """Save event to EventLog model for audit trail."""
        try:
            from api.tasks.models.core import TaskResult  # noqa - just checking model access
            # EventLog model would live in a dedicated app
            # For now, we cache the last N events per user
            user_id = payload.get('user_id')
            if user_id:
                from django.core.cache import cache
                log_key = f'event_log_{user_id}'
                log     = cache.get(log_key) or []
                log.insert(0, {
                    'event_id':   event.event_id,
                    'event_name': event.event_name,
                    'at':         event.occurred_at,
                    'summary':    str(payload)[:200],
                })
                cache.set(log_key, log[:50], timeout=86400 * 7)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# EVENT REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

EVENT_REGISTRY: Dict[str, Type[BaseEvent]] = {
    'task.completed':              TaskCompletedEvent,
    'task.failed':                 TaskFailedEvent,
    'task.activated':              TaskActivatedEvent,
    'task.deactivated':            TaskDeactivatedEvent,
    'user.registered':             UserRegisteredEvent,
    'user.verified':               UserVerifiedEvent,
    'user.level_up':               UserLevelUpEvent,
    'user.streak_milestone':       UserStreakMilestoneEvent,
    'user.milestone_reached':      UserMilestoneReachedEvent,
    'user.badge_awarded':          BadgeAwardedEvent,
    'payment.withdrawal_requested': WithdrawalRequestedEvent,
    'payment.completed':           WithdrawalCompletedEvent,
    'payment.failed':              WithdrawalFailedEvent,
    'payment.usdt_fast_pay_sent':  USDTFastPaySentEvent,
    'offer.converted':             OfferConvertedEvent,
    'offer.clicked':               OfferClickedEvent,
    'cpi.installed':               AppInstalledEvent,
    'survey.completed':            SurveyCompletedEvent,
    'quiz.completed':              QuizCompletedEvent,
    'email.submitted':             EmailSubmittedEvent,
    'fraud.detected':              FraudDetectedEvent,
    'account.suspended':           AccountSuspendedEvent,
    'kyc.approved':                KYCApprovedEvent,
    'kyc.rejected':                KYCRejectedEvent,
    'campaign.activated':          CampaignActivatedEvent,
    'campaign.paused':             CampaignPausedEvent,
    'publisher.tier_changed':      PublisherTierChangedEvent,
    'locker.content_unlocked':     ContentUnlockedEvent,
}


def create_event(event_name: str, **kwargs) -> BaseEvent:
    """Factory: create a typed event from its name."""
    klass = EVENT_REGISTRY.get(event_name, BaseEvent)
    event = klass(**{k: v for k, v in kwargs.items()
                     if k in klass.__dataclass_fields__})
    if not hasattr(event, 'event_name') or event.event_name == 'base.event':
        event.event_name = event_name
    return event


def dispatch(event_name: str, **kwargs) -> Dict[str, Any]:
    """Shorthand: create and dispatch a typed event in one call."""
    event = create_event(event_name, **kwargs)
    return EventDispatcher.dispatch(event)


__all__ = [
    'BaseEvent', 'EventDispatcher', 'EVENT_REGISTRY',
    'create_event', 'dispatch',
    # Task events
    'TaskCompletedEvent', 'TaskFailedEvent', 'TaskActivatedEvent', 'TaskDeactivatedEvent',
    # User events
    'UserRegisteredEvent', 'UserVerifiedEvent', 'UserLevelUpEvent',
    'UserStreakMilestoneEvent', 'UserMilestoneReachedEvent', 'BadgeAwardedEvent',
    # Payment events
    'WithdrawalRequestedEvent', 'WithdrawalCompletedEvent', 'WithdrawalFailedEvent',
    'USDTFastPaySentEvent',
    # Offer events
    'OfferConvertedEvent', 'OfferClickedEvent', 'AppInstalledEvent',
    'SurveyCompletedEvent', 'QuizCompletedEvent', 'EmailSubmittedEvent',
    # Fraud events
    'FraudDetectedEvent', 'AccountSuspendedEvent',
    # KYC events
    'KYCApprovedEvent', 'KYCRejectedEvent',
    # Campaign events
    'CampaignActivatedEvent', 'CampaignPausedEvent', 'PublisherTierChangedEvent',
    # Locker events
    'ContentUnlockedEvent',
]
