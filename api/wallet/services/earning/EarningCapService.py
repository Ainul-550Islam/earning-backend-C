# api/wallet/services/earning/EarningCapService.py
"""
Daily earning cap enforcement.
Prevents abuse by limiting how much a user can earn per day from each source.

Caps are configured in EarningCap model:
  - Global caps apply to all users
  - Tier-specific caps apply per user tier
  - User-specific caps override everything

Reset daily at midnight by earning_cap_reset_tasks.
"""
import logging
from decimal import Decimal
from datetime import date

from django.db.models import Sum

from ...models import EarningCap, EarningRecord, EarningSource, Wallet
from ...constants import DEFAULT_DAILY_EARN_CAP

logger = logging.getLogger("wallet.service.earning_cap")


class EarningCapService:

    @staticmethod
    def check(
        wallet: Wallet,
        amount: Decimal,
        source_type: str,
        source: EarningSource = None,
    ) -> tuple:
        """
        Check if wallet can earn `amount` from `source_type` today.
        Returns (allowed: bool, remaining: Decimal).
        """
        today       = date.today()
        user        = wallet.user
        tier        = getattr(user, "tier", "FREE")

        # Today's earnings from this source type
        today_earned = EarningRecord.objects.filter(
            wallet=wallet,
            source_type=source_type,
            earned_at__date=today,
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

        # Get applicable cap
        cap_amount = EarningCapService._get_cap(wallet, user, tier, source_type, source)

        remaining = cap_amount - today_earned
        if remaining <= 0:
            logger.info(f"Cap reached: wallet={wallet.id} source={source_type} "
                        f"today={today_earned} cap={cap_amount}")
            return False, Decimal("0")

        if amount > remaining:
            logger.info(f"Cap partial: wallet={wallet.id} source={source_type} "
                        f"requested={amount} remaining={remaining}")
            return False, remaining

        return True, remaining - amount

    @staticmethod
    def _get_cap(wallet, user, tier: str, source_type: str, source: EarningSource = None) -> Decimal:
        """
        Return the most specific applicable cap amount.
        Priority: user-specific > tier-specific > global > default constant.
        """
        # User-specific cap
        user_cap = EarningCap.objects.filter(
            wallet=wallet, cap_type="user", is_active=True,
            source__source_type=source_type,
        ).first() or EarningCap.objects.filter(
            wallet=wallet, cap_type="user", is_active=True, source__isnull=True
        ).first()
        if user_cap:
            return user_cap.cap_amount

        # Tier-specific cap
        tier_cap = EarningCap.objects.filter(
            cap_type="tier", tier=tier, is_active=True,
            source__source_type=source_type,
        ).first() or EarningCap.objects.filter(
            cap_type="tier", tier=tier, is_active=True, source__isnull=True
        ).first()
        if tier_cap:
            return tier_cap.cap_amount

        # Global cap
        global_cap = EarningCap.objects.filter(
            cap_type="global", is_active=True,
            source__source_type=source_type,
        ).first() or EarningCap.objects.filter(
            cap_type="global", is_active=True, source__isnull=True
        ).first()
        if global_cap:
            return global_cap.cap_amount

        # Fallback to constant
        return DEFAULT_DAILY_EARN_CAP

    @staticmethod
    def get_cap_status(wallet: Wallet, source_type: str = None) -> dict:
        """
        Return cap status for dashboard — how much earned vs cap today.
        """
        today = date.today()
        user  = wallet.user
        tier  = getattr(user, "tier", "FREE")

        source_types = [source_type] if source_type else [
            s for s in ["task","offer","cpa","cpi","cpc","referral","bonus","survey"]
        ]

        result = {}
        for st in source_types:
            cap = EarningCapService._get_cap(wallet, user, tier, st)
            today_earned = EarningRecord.objects.filter(
                wallet=wallet, source_type=st, earned_at__date=today
            ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

            result[st] = {
                "cap":          float(cap),
                "earned_today": float(today_earned),
                "remaining":    float(max(cap - today_earned, Decimal("0"))),
                "pct_used":     float(today_earned / cap * 100) if cap > 0 else 0,
            }

        return result
