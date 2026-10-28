"""
api/gamification/integrations/monetization_adapter.py

MonetizationTools ↔ Gamification adapter।

monetization_tools.UserLevel (XP system) ↔ api.gamification sync।
monetization_tools.OfferCompletion → achievement।

Wire-up (api/monetization_tools/signals.py তে existing post_save receiver-এর শেষে):
    from api.gamification.integrations.monetization_adapter import MonetizationGamificationAdapter
    _mt = MonetizationGamificationAdapter()
    _mt.on_offer_completed(instance)   # OfferCompletion post_save
    _mt.on_level_up(instance)          # UserLevel post_save
"""
from __future__ import annotations
import logging
from typing import Any
logger = logging.getLogger(__name__)

# UserLevel current_level → gamification achievement
LEVEL_ACHIEVEMENTS = {
    5:   {"title": "Level 5 Achiever",  "points": 30},
    10:  {"title": "Level 10 Veteran",  "points": 75},
    20:  {"title": "Level 20 Elite",    "points": 150},
    30:  {"title": "Level 30 Master",   "points": 300},
    50:  {"title": "Level 50 Legend",   "points": 700},
}

# XP thresholds
XP_MILESTONES = {
    500:   {"title": "XP Collector",  "points": 15},
    1000:  {"title": "XP Hunter",     "points": 30},
    5000:  {"title": "XP Master",     "points": 80},
    10000: {"title": "XP Legend",     "points": 200},
}


class MonetizationGamificationAdapter:

    def on_offer_completed(self, completion: Any) -> None:
        """
        monetization_tools.OfferCompletion approved → achievement check।
        Called from: api/monetization_tools/signals.py post_save receiver
        """
        status = str(getattr(completion, "status", "") or "")
        if status not in ("approved", "completed"):
            return
        user = getattr(completion, "user", None)
        if not user:
            return
        try:
            from api.gamification.integrations.offerwall_adapter import OfferwallGamificationAdapter
            payout  = float(getattr(completion, "payout_amount", 0) or 0)
            offer   = getattr(completion, "offer", None)
            network = str(getattr(offer, "network", "") or "") if offer else ""
            OfferwallGamificationAdapter().on_offer_completed(
                user=user, payout=payout, network=network,
                offer_id=str(getattr(completion, "id", ""))
            )
        except Exception as exc:
            logger.error("[MonetizationAdapter] on_offer_completed failed: %s", exc)

    def on_level_up(self, user_level: Any) -> None:
        """
        monetization_tools.UserLevel level up → gamification level achievement。
        Called from: api/monetization_tools/signals.py UserLevel post_save
        """
        user  = getattr(user_level, "user", None)
        level = int(getattr(user_level, "current_level", 0) or 0)
        xp    = int(getattr(user_level, "total_xp_earned", 0) or 0)
        if not user:
            return
        try:
            # Level milestone
            cfg = LEVEL_ACHIEVEMENTS.get(level)
            if cfg:
                self._award(user, cfg["title"],
                            f"Level {level} অর্জন করেছেন! অভিনন্দন!",
                            cfg["points"],
                            {"source": "monetization_tools", "level": level, "xp": xp})

            # XP milestones
            prev_xp = xp - int(getattr(user_level, "current_xp", 0) or 0)
            for threshold, xcfg in sorted(XP_MILESTONES.items()):
                if prev_xp < threshold <= xp:
                    self._award(user, xcfg["title"],
                                f"মোট {threshold:,} XP অর্জন করেছেন!",
                                xcfg["points"],
                                {"source": "monetization_tools", "xp_threshold": threshold})

            self._track(user, "monetization_level_up", {"level": level, "xp": xp})
        except Exception as exc:
            logger.error("[MonetizationAdapter] on_level_up failed: %s", exc)

    def sync_gamification_points_to_xp(self, user: Any, points: int) -> None:
        """
        Gamification achievement points → monetization_tools UserLevel XP sync (reverse)।
        Ratio: 1 gamification point = 2 XP।
        """
        if not user or not points:
            return
        try:
            from api.monetization_tools.models import UserLevel
            ul, _ = UserLevel.objects.get_or_create(user=user)
            xp_to_add = points * 2
            ul.current_xp     = (ul.current_xp or 0) + xp_to_add
            ul.total_xp_earned = (ul.total_xp_earned or 0) + xp_to_add
            ul.save(update_fields=["current_xp", "total_xp_earned"])
            logger.debug("[MonetizationAdapter] Synced %d pts → %d XP for user=%s",
                         points, xp_to_add, getattr(user, "id", "?"))
        except ImportError:
            pass
        except Exception as exc:
            logger.debug("[MonetizationAdapter] sync_gamification_points_to_xp failed: %s", exc)

    def _award(self, user, title, description, points, metadata):
        from api.gamification.services import award_achievement
        from api.gamification.choices import AchievementType
        try:
            award_achievement(user_id=user.pk, achievement_type=AchievementType.MILESTONE,
                              title=title, description=description, points=points, metadata=metadata)
        except Exception as exc:
            logger.debug("[MonetizationAdapter] _award skipped: %s", exc)

    def _track(self, user, event, properties):
        try:
            from api.gamification.integrations.adapter import gamification_adapter
            gamification_adapter.track_event(event, user=user, properties=properties)
        except Exception:
            pass
