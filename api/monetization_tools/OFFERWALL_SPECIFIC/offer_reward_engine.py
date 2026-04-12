"""OFFERWALL_SPECIFIC/offer_reward_engine.py — Offer reward calculation."""
from decimal import Decimal


class OfferRewardEngine:
    """Calculates final reward coins for offer completions."""

    @classmethod
    def calculate(cls, base_coins: Decimal, user=None,
                   tenant=None, offer_type: str = "") -> dict:
        multiplier = Decimal("1.0")
        bonus_coins = Decimal("0")
        reasons    = []

        # Flash sale multiplier
        from ..services import FlashSaleService
        flash_mult = FlashSaleService.get_best_multiplier(tenant, offer_type)
        if flash_mult > Decimal("1.0"):
            multiplier *= flash_mult
            reasons.append(f"Flash sale x{flash_mult}")

        # User loyalty tier multiplier
        if user:
            from ..USER_MONETIZATION.user_value_tier import UserValueTier
            tier_mult = UserValueTier.reward_multiplier(user)
            if tier_mult > Decimal("1.0"):
                multiplier *= tier_mult
                reasons.append(f"Loyalty tier x{tier_mult}")

        final = (base_coins * multiplier + bonus_coins).quantize(Decimal("0.01"))
        return {
            "base_coins":  base_coins,
            "multiplier":  multiplier,
            "bonus_coins": bonus_coins,
            "final_coins": final,
            "reasons":     reasons,
        }
