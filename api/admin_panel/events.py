# api/admin_panel/events.py
"""
Admin Panel Domain Events — strongly-typed event definitions.
All cross-app events are typed here; INTEGRATION_SYSTEM fires them.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List
from django.utils import timezone


@dataclass
class AdminEvent:
    """Base admin domain event."""
    event_type: str
    source: str = 'admin_panel'
    timestamp: str = field(default_factory=lambda: timezone.now().isoformat())
    correlation_id: str = ''
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'event_type': self.event_type,
            'source': self.source,
            'timestamp': self.timestamp,
            'correlation_id': self.correlation_id,
            'payload': self.payload,
        }


@dataclass
class UserBannedEvent(AdminEvent):
    event_type: str = 'user.banned'
    user_id: Any = None
    reason: str = ''
    banned_by: str = ''

    def __post_init__(self):
        self.payload = {'user_id': self.user_id, 'reason': self.reason, 'by': self.banned_by}


@dataclass
class WithdrawalApprovedEvent(AdminEvent):
    event_type: str = 'wallet.withdrawal_approved'
    item_id: Any = None
    amount: float = 0.0
    gateway: str = ''
    user_id: Any = None

    def __post_init__(self):
        self.payload = {'item_id': self.item_id, 'amount': self.amount,
                        'gateway': self.gateway, 'user_id': self.user_id}


@dataclass
class FraudDetectedEvent(AdminEvent):
    event_type: str = 'fraud.detected'
    user_id: Any = None
    fraud_score: int = 0
    attempt_type: str = ''
    ip_address: str = ''
    auto_action: str = ''

    def __post_init__(self):
        self.payload = {
            'user_id': self.user_id, 'fraud_score': self.fraud_score,
            'attempt_type': self.attempt_type, 'ip': self.ip_address,
            'action': self.auto_action,
        }


@dataclass
class ConfigUpdatedEvent(AdminEvent):
    event_type: str = 'system.config_updated'
    config_key: str = ''
    old_value: Any = None
    new_value: Any = None
    updated_by: str = ''

    def __post_init__(self):
        self.payload = {'key': self.config_key, 'old': self.old_value,
                        'new': self.new_value, 'by': self.updated_by}


@dataclass
class MaintenanceStartedEvent(AdminEvent):
    event_type: str = 'system.maintenance_started'
    message: str = ''
    duration_minutes: int = 0
    started_by: str = ''

    def __post_init__(self):
        self.payload = {'message': self.message, 'duration': self.duration_minutes,
                        'by': self.started_by}


@dataclass
class FeatureFlagChangedEvent(AdminEvent):
    event_type: str = 'system.feature_flag_changed'
    flag_key: str = ''
    is_enabled: bool = False
    rollout_pct: int = 100
    changed_by: str = ''

    def __post_init__(self):
        self.payload = {'flag': self.flag_key, 'enabled': self.is_enabled,
                        'rollout': self.rollout_pct, 'by': self.changed_by}


@dataclass
class BroadcastSentEvent(AdminEvent):
    event_type: str = 'notification.broadcast_sent'
    title: str = ''
    audience_type: str = 'all'
    sent_count: int = 0

    def __post_init__(self):
        self.payload = {'title': self.title, 'audience': self.audience_type, 'sent': self.sent_count}


def fire_event(event: AdminEvent) -> None:
    """Fire a typed event through the EventBus."""
    try:
        from api.admin_panel.INTEGRATION_SYSTEM.event_bus import event_bus
        event_bus.publish(
            event_type=event.event_type,
            payload=event.payload,
            source=event.source,
            correlation_id=event.correlation_id,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).debug(f"[events.fire_event] {e}")