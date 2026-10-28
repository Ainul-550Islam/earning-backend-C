# engagement/services/integration/__init__.py
"""
Engagement ↔ External System Integration Layer
================================================
Single entry-point for ALL cross-app communication.

Other apps MUST use these bridges, never import engagement internals directly.
Engagement MUST use these bridges, never import wallet/notifications/referral directly.

Available bridges:
    WalletBridge       — credit / debit / balance via api.wallet
    NotificationBridge — push/in-app/email via api.notifications
    ReferralBridge     — commission propagation via api.referral
    UserBridge         — profile, tier, KYC via api.users
    EventBus           — fire-and-forget inter-app events
    EngagementBridge   — inbound API for OTHER apps to call engagement
"""

from .wallet_bridge import WalletBridge
from .notification_bridge import NotificationBridge
from .referral_bridge import ReferralBridge
from .user_bridge import UserBridge
from .event_bus import EngagementEventBus
from .inbound_bridge import EngagementBridge

__all__ = [
    "WalletBridge",
    "NotificationBridge",
    "ReferralBridge",
    "UserBridge",
    "EngagementEventBus",
    "EngagementBridge",
]
