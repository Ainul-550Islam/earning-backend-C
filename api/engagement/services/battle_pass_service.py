# engagement/services/battle_pass_service.py
import logging
from django.db import transaction
from django.utils import timezone
from .coin_service import CoinService
from .xp_service import XPService
from ..models.battle_pass import BattlePass, BattlePassTier, UserBattlePass, BattlePassXPSource

logger = logging.getLogger(__name__)


class BattlePassService:

    @classmethod
    def get_or_enroll(cls, user, battle_pass: BattlePass, tenant=None) -> UserBattlePass:
        """Enroll user in a battle pass (free tier) if not already enrolled."""
        ubp, created = UserBattlePass.objects.get_or_create(
            user=user, battle_pass=battle_pass,
            defaults={"tenant": tenant or getattr(user, "tenant", None)},
        )
        if created:
            logger.info("BattlePassService: user=%s enrolled in season=%d", user.pk, battle_pass.season_num)
        return ubp

    @classmethod
    @transaction.atomic
    def grant_xp(cls, user, action: str, tenant=None) -> dict:
        """
        Grant Battle Pass XP for a given action.
        Returns dict with xp_granted, new_tier, tier_ups.
        """
        bp = BattlePass.objects.filter(is_active=True, tenant=tenant).first()
        if not bp or not bp.is_live:
            return {"xp_granted": 0, "new_tier": 0, "tier_ups": []}

        try:
            source = BattlePassXPSource.objects.get(battle_pass=bp, action=action)
        except BattlePassXPSource.DoesNotExist:
            return {"xp_granted": 0, "new_tier": 0, "tier_ups": []}

        xp_amount = source.xp_amount
        ubp = cls.get_or_enroll(user, bp, tenant)
        old_tier = ubp.current_tier
        ubp.current_xp += xp_amount

        # Calculate new tier from cumulative XP
        tiers = list(BattlePassTier.objects.filter(battle_pass=bp).order_by("tier_number"))
        new_tier = old_tier
        for tier in tiers:
            if ubp.current_xp >= tier.xp_required and tier.tier_number > new_tier:
                new_tier = tier.tier_number

        tier_ups = list(range(old_tier + 1, new_tier + 1)) if new_tier > old_tier else []
        ubp.current_tier = new_tier
        ubp.save(update_fields=["current_xp", "current_tier"])

        logger.info("BattlePassService: user=%s action=%s +%dXP tier %d→%d", user.pk, action, xp_amount, old_tier, new_tier)
        return {"xp_granted": xp_amount, "new_tier": new_tier, "tier_ups": tier_ups}

    @classmethod
    @transaction.atomic
    def claim_tier_rewards(cls, user, tier_number: int, tenant=None) -> dict:
        """Claim free (and premium if applicable) rewards for a tier."""
        bp  = BattlePass.objects.filter(is_active=True, tenant=tenant).first()
        ubp = UserBattlePass.objects.select_for_update().get(user=user, battle_pass=bp)

        if tier_number > ubp.current_tier:
            return {"error": "Tier not yet reached."}
        if tier_number <= ubp.last_claimed_tier:
            return {"error": "Already claimed."}

        try:
            tier = BattlePassTier.objects.get(battle_pass=bp, tier_number=tier_number)
        except BattlePassTier.DoesNotExist:
            return {"error": "Tier not found."}

        result = {"free": {}, "premium": {}}

        # Free rewards
        if tier.free_coins > 0:
            CoinService.add(user, tier.free_coins, source="battle_pass", ref_id=str(tier.pk))
            result["free"]["coins"] = float(tier.free_coins)
        if tier.free_xp > 0:
            XPService.grant(user, tier.free_xp, source="battle_pass", ref_id=str(tier.pk))
            result["free"]["xp"] = tier.free_xp

        # Premium rewards (only if user has premium)
        if ubp.is_premium:
            if tier.premium_coins > 0:
                CoinService.add(user, tier.premium_coins, source="battle_pass_premium", ref_id=str(tier.pk))
                result["premium"]["coins"] = float(tier.premium_coins)
            if tier.premium_xp > 0:
                XPService.grant(user, tier.premium_xp, source="battle_pass_premium", ref_id=str(tier.pk))
                result["premium"]["xp"] = tier.premium_xp

        ubp.last_claimed_tier = tier_number
        ubp.save(update_fields=["last_claimed_tier"])
        return result

    @classmethod
    @transaction.atomic
    def unlock_premium(cls, user, tenant=None) -> dict:
        """Spend coins to unlock the premium track."""
        bp  = BattlePass.objects.filter(is_active=True, tenant=tenant).first()
        if not bp:
            return {"error": "No active battle pass."}
        ubp = cls.get_or_enroll(user, bp, tenant)
        if ubp.is_premium:
            return {"error": "Already premium."}
        CoinService.deduct(user, bp.premium_price_coins, source="battle_pass_premium_unlock")
        ubp.is_premium          = True
        ubp.premium_unlocked_at = timezone.now()
        ubp.save(update_fields=["is_premium", "premium_unlocked_at"])
        return {"success": True, "coins_spent": float(bp.premium_price_coins)}
