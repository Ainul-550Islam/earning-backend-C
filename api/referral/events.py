# api/referral/events.py
# Structured event emitters — fire hooks and analytics events
# ============================================================

import logging
from typing import Any, Dict, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)


class ReferralEvents:
    """
    Central event emitter for referral module.
    Other modules listen via hooks.py or INTEGRATION_SYSTEM signals.
    """

    @staticmethod
    def commission_paid(user, amount: Decimal, level: int, from_user, source: str = '') -> None:
        """Emit when commission is paid to a user."""
        try:
            from api.referral.hooks import ReferralHooks
            ReferralHooks.on_commission_paid(
                user=user, amount=amount, level=level,
                from_user=from_user, source=source,
            )
        except Exception as e:
            logger.debug(f'[Events] commission_paid hook failed: {e}')

        # WebSocket broadcast
        try:
            from asgiref.sync import async_to_sync
            from api.referral.consumers import broadcast_commission_paid
            async_to_sync(broadcast_commission_paid)(
                user_id=user.id, amount=float(amount), level=level
            )
        except Exception:
            pass

    @staticmethod
    def referral_created(referrer, referred_user, referral_id: int) -> None:
        """Emit when new referral relationship is created."""
        try:
            from api.referral.hooks import ReferralHooks
            ReferralHooks.on_referral_created(
                referrer=referrer, referred_user=referred_user, referral_id=referral_id
            )
        except Exception as e:
            logger.debug(f'[Events] referral_created hook failed: {e}')

    @staticmethod
    def milestone_reached(user, milestone_value: Decimal, bonus_amount: Decimal) -> None:
        try:
            from api.referral.hooks import ReferralHooks
            ReferralHooks.on_milestone_reached(
                user=user, milestone_value=milestone_value, bonus_amount=bonus_amount
            )
        except Exception as e:
            logger.debug(f'[Events] milestone_reached hook failed: {e}')

    @staticmethod
    def fraud_flagged(referral_id: int, fraud_score: int) -> None:
        try:
            from api.referral.hooks import ReferralHooks
            ReferralHooks.on_fraud_flagged(referral_id=referral_id, fraud_score=fraud_score)
        except Exception as e:
            logger.debug(f'[Events] fraud_flagged hook failed: {e}')

    @staticmethod
    def campaign_started(campaign) -> None:
        try:
            from api.referral.hooks import ReferralHooks
            ReferralHooks.on_campaign_started(campaign=campaign)
        except Exception as e:
            logger.debug(f'[Events] campaign_started hook failed: {e}')

    @staticmethod
    def contest_prize_won(user, contest, rank: int, prize_amount: Decimal) -> None:
        try:
            from api.referral.hooks import ReferralHooks
            ReferralHooks.on_contest_prize_won(
                user=user, contest=contest, rank=rank, prize_amount=prize_amount
            )
        except Exception as e:
            logger.debug(f'[Events] contest_prize_won hook failed: {e}')

    @staticmethod
    def publish(event_name: str, **kwargs) -> None:
        """Generic event publish to event bus."""
        try:
            from api.referral.INTEGRATION_SYSTEM.event_bus import get_event_bus
            get_event_bus().publish(event_name, async_mode=True, **kwargs)
        except Exception as e:
            logger.debug(f'[Events] publish {event_name} failed: {e}')