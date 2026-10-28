# api/referral/hooks.py
# Extension hooks — lets other apps plug into referral events without tight coupling
# Register custom hooks via ReferralHooks.register()
# ============================================================

import logging
from typing import Callable, Dict, List
from decimal import Decimal

logger = logging.getLogger(__name__)


class ReferralHooks:
    """
    Extension point system for referral module.
    Other modules register callbacks here — fired on referral events.

    Usage from another module:
        from api.referral.hooks import ReferralHooks

        def my_handler(user, amount, level, **kwargs):
            # do something when commission is paid
            pass

        ReferralHooks.register('commission_paid', my_handler)
    """

    _registry: Dict[str, List[Callable]] = {}

    @classmethod
    def register(cls, event: str, handler: Callable) -> None:
        """Register a hook handler for an event."""
        if event not in cls._registry:
            cls._registry[event] = []
        cls._registry[event].append(handler)
        logger.debug(f'[Hooks] Registered: {event} → {handler.__name__}')

    @classmethod
    def unregister(cls, event: str, handler: Callable) -> bool:
        if event in cls._registry:
            try:
                cls._registry[event].remove(handler)
                return True
            except ValueError:
                pass
        return False

    @classmethod
    def fire(cls, event: str, **kwargs) -> List:
        """Fire all handlers for an event. Returns list of results."""
        handlers = cls._registry.get(event, [])
        results = []
        for handler in handlers:
            try:
                result = handler(**kwargs)
                results.append(result)
            except Exception as e:
                logger.warning(f'[Hooks] Handler {handler.__name__} failed for {event}: {e}')
        return results

    # ── Built-in hook events ──────────────────────────────────────────────────

    @classmethod
    def on_commission_paid(cls, user, amount: Decimal, level: int, from_user, source: str = '') -> None:
        cls.fire('commission_paid', user=user, amount=amount, level=level,
                 from_user=from_user, source=source)

    @classmethod
    def on_referral_created(cls, referrer, referred_user, referral_id: int) -> None:
        cls.fire('referral_created', referrer=referrer,
                 referred_user=referred_user, referral_id=referral_id)

    @classmethod
    def on_milestone_reached(cls, user, milestone_value: Decimal, bonus_amount: Decimal) -> None:
        cls.fire('milestone_reached', user=user,
                 milestone_value=milestone_value, bonus_amount=bonus_amount)

    @classmethod
    def on_fraud_flagged(cls, referral_id: int, fraud_score: int) -> None:
        cls.fire('fraud_flagged', referral_id=referral_id, fraud_score=fraud_score)

    @classmethod
    def on_campaign_started(cls, campaign) -> None:
        cls.fire('campaign_started', campaign=campaign)

    @classmethod
    def on_contest_prize_won(cls, user, contest, rank: int, prize_amount: Decimal) -> None:
        cls.fire('contest_prize_won', user=user, contest=contest,
                 rank=rank, prize_amount=prize_amount)

    @classmethod
    def on_payout_completed(cls, user, amount: Decimal, payout_id: int) -> None:
        cls.fire('payout_completed', user=user, amount=amount, payout_id=payout_id)

    @classmethod
    def on_tier_upgraded(cls, user, old_tier, new_tier) -> None:
        cls.fire('tier_upgraded', user=user, old_tier=old_tier, new_tier=new_tier)


# ── Default Hook Registrations ────────────────────────────────────────────────

def _register_default_hooks() -> None:
    """Called from apps.py ready() — register built-in hook handlers."""

    # Update user stats on commission paid
    def update_user_referral_earnings(user, amount, **kwargs):
        try:
            from django.db.models import F
            from django.contrib.auth import get_user_model
            User = get_user_model()
            User.objects.filter(id=user.id).update(
                referral_earnings=F('referral_earnings') + amount
            )
        except Exception:
            pass

    ReferralHooks.register('commission_paid', update_user_referral_earnings)

    # Update total_referrals count on new referral
    def update_referral_count(referrer, **kwargs):
        try:
            from django.db.models import F
            from django.contrib.auth import get_user_model
            User = get_user_model()
            User.objects.filter(id=referrer.id).update(
                total_referrals=F('total_referrals') + 1,
                referral_count=F('referral_count') + 1,
            )
        except Exception:
            pass

    ReferralHooks.register('referral_created', update_referral_count)

    logger.info('[Hooks] Default hooks registered')