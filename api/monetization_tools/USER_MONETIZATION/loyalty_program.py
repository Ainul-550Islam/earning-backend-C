"""USER_MONETIZATION/loyalty_program.py — Loyalty rewards program."""
from decimal import Decimal


LOYALTY_TIERS = [
    {"name": "Bronze", "min_points": 0,      "bonus_pct": Decimal("0")},
    {"name": "Silver", "min_points": 1000,   "bonus_pct": Decimal("5")},
    {"name": "Gold",   "min_points": 5000,   "bonus_pct": Decimal("10")},
    {"name": "Platinum","min_points": 20000,  "bonus_pct": Decimal("20")},
    {"name": "Diamond","min_points": 100000, "bonus_pct": Decimal("30")},
]


class LoyaltyProgram:
    @classmethod
    def tier(cls, total_coins: Decimal) -> dict:
        tier = LOYALTY_TIERS[0]
        for t in LOYALTY_TIERS:
            if total_coins >= t["min_points"]:
                tier = t
        return tier

    @classmethod
    def bonus_multiplier(cls, user) -> Decimal:
        earned = getattr(user, "total_earned", Decimal("0"))
        t      = cls.tier(Decimal(str(earned)))
        return Decimal("1") + t["bonus_pct"] / 100

    @classmethod
    def points_to_next_tier(cls, total_coins: Decimal) -> int:
        for i, t in enumerate(LOYALTY_TIERS):
            if total_coins < t["min_points"]:
                return int(t["min_points"] - total_coins)
        return 0
