"""GAMIFICATION/badge_system.py — Badge / trophy system."""
from ..models import Achievement

BADGE_DEFINITIONS = {
    "first_offer":     {"title": "First Offer!",        "icon": "🎯", "category": "offer"},
    "streak_7":        {"title": "7-Day Streak",         "icon": "🔥", "category": "engagement"},
    "streak_30":       {"title": "30-Day Legend",        "icon": "⚡", "category": "engagement"},
    "referral_hero":   {"title": "Referral Hero",        "icon": "🤝", "category": "social"},
    "subscriber":      {"title": "Premium Member",       "icon": "👑", "category": "subscription"},
    "vip":             {"title": "VIP User",             "icon": "💎", "category": "tier"},
    "top_earner":      {"title": "Top Earner",           "icon": "🏆", "category": "earning"},
    "spin_master":     {"title": "Spin Master",          "icon": "🎡", "category": "gaming"},
}


class BadgeSystem:
    @classmethod
    def award(cls, user, badge_key: str, tenant=None) -> bool:
        info = BADGE_DEFINITIONS.get(badge_key)
        if not info:
            return False
        if Achievement.objects.filter(user=user, achievement_key=badge_key).exists():
            return False
        Achievement.objects.create(
            user=user, achievement_key=badge_key,
            title=info["title"], category=info["category"], tenant=tenant,
        )
        return True

    @classmethod
    def badges_for_user(cls, user) -> list:
        keys = list(Achievement.objects.filter(
            user=user, achievement_key__in=BADGE_DEFINITIONS.keys()
        ).values_list("achievement_key", flat=True))
        return [{"key": k, **BADGE_DEFINITIONS[k]} for k in keys]
