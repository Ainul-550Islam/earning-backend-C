# api/referral/INTEGRATION_SYSTEM/bridge.py
# Integration bridge — referral ↔ all modules
# Single entry point for cross-module data exchange
# ============================================================

import logging
from decimal import Decimal
from typing import Optional, Any, Dict
from django.db import transaction
from .integ_adapter import AdapterFactory
from .integ_exceptions import BridgeError, ModuleUnavailableError
from .integ_constants import (
    SOURCE_TASK, SOURCE_OFFER, SOURCE_WITHDRAWAL, SOURCE_SIGNUP,
)

logger = logging.getLogger(__name__)


class ReferralBridge:
    """
    The master bridge between referral module and everything else.

    Usage (from any module):
        from api.referral.INTEGRATION_SYSTEM.bridge import ReferralBridge
        bridge = ReferralBridge()
        bridge.on_task_earned(user=user, task=task, amount=100)
        bridge.on_signup(new_user=new_user, referral_code='EARN1234')
    """

    def __init__(self):
        self._adapters = AdapterFactory

    # ── INBOUND: External modules call these ──────────────────────────────────

    def on_task_earned(
        self, user, task=None, amount: float = 0, completion=None, **kwargs
    ) -> dict:
        """
        Called when user earns from a task.
        Processes referral commission for all ancestors.
        """
        if not amount or float(amount) <= 0:
            return {'processed': False, 'reason': 'zero_amount'}
        try:
            from api.referral.INTEGRATION_SYSTEM.integ_handler import (
                handle_task_completed
            )
            return handle_task_completed(
                user=user, task=task,
                earned_amount=Decimal(str(amount)),
                completion=completion, **kwargs
            )
        except Exception as e:
            logger.error(f'[Bridge] on_task_earned error: {e}')
            return {'processed': False, 'error': str(e)}

    def on_offer_completed(
        self, user, offer_id: str = '', user_net_reward: float = 0,
        conversion=None, **kwargs
    ) -> dict:
        """
        Called when offer conversion is approved.
        """
        if not user_net_reward or float(user_net_reward) <= 0:
            return {'processed': False, 'reason': 'zero_amount'}
        try:
            from api.referral.INTEGRATION_SYSTEM.integ_handler import (
                handle_offer_completed
            )
            return handle_offer_completed(
                user=user, conversion=conversion,
                user_net_reward=Decimal(str(user_net_reward)),
                offer_id=offer_id, **kwargs
            )
        except Exception as e:
            logger.error(f'[Bridge] on_offer_completed error: {e}')
            return {'processed': False, 'error': str(e)}

    def on_signup(
        self, new_user, referral_code: str = '',
        ip: str = '', device_fp: str = '', **kwargs
    ) -> dict:
        """
        Called when a new user registers.
        Processes referral signup and assigns bonus.
        """
        try:
            from api.referral.INTEGRATION_SYSTEM.integ_handler import (
                handle_user_registered
            )
            return handle_user_registered(
                new_user=new_user,
                referral_code=referral_code,
                new_user_ip=ip,
                device_fingerprint=device_fp, **kwargs
            )
        except Exception as e:
            logger.error(f'[Bridge] on_signup error: {e}')
            return {'processed': False, 'error': str(e)}

    def on_withdrawal(
        self, user, amount: float = 0, transaction_id: str = '', **kwargs
    ) -> dict:
        """Called when withdrawal is approved."""
        try:
            from api.referral.INTEGRATION_SYSTEM.integ_handler import (
                handle_withdrawal_approved
            )
            return handle_withdrawal_approved(
                user=user,
                amount=Decimal(str(amount)),
                transaction_id=transaction_id, **kwargs
            )
        except Exception as e:
            logger.debug(f'[Bridge] on_withdrawal error: {e}')
            return {'processed': False, 'error': str(e)}

    def on_fraud_confirmed(
        self, user=None, referral_id: int = None,
        fraud_score: int = 100, **kwargs
    ) -> dict:
        """Called when fraud is confirmed — triggers clawback."""
        try:
            from api.referral.INTEGRATION_SYSTEM.integ_handler import (
                handle_fraud_confirmed
            )
            return handle_fraud_confirmed(
                user=user, referral_id=referral_id,
                fraud_score=fraud_score, **kwargs
            )
        except Exception as e:
            logger.error(f'[Bridge] on_fraud_confirmed error: {e}')
            return {'processed': False, 'error': str(e)}

    # ── OUTBOUND: Referral module calls these ─────────────────────────────────

    def credit_commission(
        self, user, amount: Decimal, level: int,
        referred_user_id: int, source_id: str = ''
    ) -> Optional[Any]:
        """Credit commission to wallet via WalletAdapter."""
        return self._adapters.wallet().credit_referral_commission(
            user=user, amount=amount, level=level,
            referred_user_id=referred_user_id, source_id=source_id,
        )

    def credit_bonus(self, user, amount: Decimal, description: str) -> Optional[Any]:
        """Credit signup/milestone bonus."""
        return self._adapters.wallet().credit_bonus(
            user=user, amount=amount, description=description
        )

    def send_notification(
        self, user, title: str, message: str,
        notification_type: str = 'referral_commission',
        priority: str = 'medium',
    ) -> bool:
        """Send notification via NotificationAdapter."""
        return self._adapters.notification().send(
            user=user, title=title, message=message,
            notification_type=notification_type, priority=priority,
        )

    def award_loyalty_points(self, referrer, referee) -> bool:
        """Award djoyalty points for referral."""
        return self._adapters.djoyalty().award_referral_points(
            referrer=referrer, referee=referee
        )

    def track_analytics(self, event: str, user, data: dict = None) -> None:
        """Track analytics event."""
        self._adapters.analytics().track_event(event, user, data or {})

    def check_rate_limit(self, user) -> bool:
        """Check if user is within referral activity rate limits."""
        return self._adapters.rate_limit().check_referral_activity(user)

    def get_project_fraud_score(self, user) -> Optional[float]:
        """Get project-wide fraud risk score."""
        return self._adapters.fraud().get_user_risk_score(user)

    # ── QUERY: Cross-module data queries ──────────────────────────────────────

    def get_user_referral_summary(self, user) -> dict:
        """
        Complete referral summary for a user.
        Safe to call from any module (users, promotions, etc.)
        """
        try:
            from api.referral.services.ReferralService import ReferralService
            return ReferralService.get_referral_stats(user)
        except Exception as e:
            logger.warning(f'[Bridge] get_user_referral_summary error: {e}')
            return {
                'referral_code': getattr(user, 'referral_code', ''),
                'total_referrals': 0, 'total_commission': 0,
                'level1_count': 0, 'level2_count': 0, 'level3_count': 0,
            }

    def get_referral_code(self, user) -> str:
        """Get user's primary referral code. Safe to call from any module."""
        try:
            from api.referral.models import ReferralCode
            code = ReferralCode.objects.filter(
                user=user, is_primary=True, is_active=True
            ).values_list('code', flat=True).first()
            return code or getattr(user, 'referral_code', '') or ''
        except Exception:
            return getattr(user, 'referral_code', '') or ''

    def validate_referral_code(self, code: str) -> dict:
        """Validate a referral code. Used by registration views."""
        try:
            from api.referral.services.ReferralCodeService import ReferralCodeService
            return ReferralCodeService.validate_code(code)
        except Exception as e:
            return {'valid': False, 'error': str(e)}

    def get_active_campaign(self) -> Optional[Any]:
        """Get active referral campaign (for frontend display)."""
        try:
            from api.referral.services.ReferralCampaignService import (
                ReferralCampaignService
            )
            return ReferralCampaignService.get_active_campaign()
        except Exception:
            return None


# ── Global Singleton ──────────────────────────────────────────────────────────

_bridge: Optional[ReferralBridge] = None


def get_bridge() -> ReferralBridge:
    """
    Get the global ReferralBridge singleton.

    Usage from any module:
        from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge
        bridge = get_bridge()
        bridge.on_task_earned(user=user, task=task, amount=earned)
    """
    global _bridge
    if _bridge is None:
        _bridge = ReferralBridge()
    return _bridge