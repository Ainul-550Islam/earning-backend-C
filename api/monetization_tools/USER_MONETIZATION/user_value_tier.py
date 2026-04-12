"""USER_MONETIZATION/user_value_tier.py — User value tiers (whale, dolphin, minnow)."""
from decimal import Decimal


USER_TIERS = {
    "whale":   {"min_earned": Decimal("10000"), "label": "Whale",   "multiplier": Decimal("2.0")},
    "dolphin": {"min_earned": Decimal("1000"),  "label": "Dolphin", "multiplier": Decimal("1.5")},
    "fish":    {"min_earned": Decimal("100"),   "label": "Fish",    "multiplier": Decimal("1.2")},
    "minnow":  {"min_earned": Decimal("0"),     "label": "Minnow",  "multiplier": Decimal("1.0")},
}


class UserValueTier:
    @classmethod
    def classify(cls, total_earned: Decimal) -> dict:
        for tier, info in USER_TIERS.items():
            if total_earned >= info["min_earned"]:
                return {"tier": tier, **info}
        return {"tier": "minnow", **USER_TIERS["minnow"]}

    @classmethod
    def reward_multiplier(cls, user) -> Decimal:
        earned = getattr(user, "total_earned", Decimal("0"))
        return cls.classify(Decimal(str(earned)))["multiplier"]
