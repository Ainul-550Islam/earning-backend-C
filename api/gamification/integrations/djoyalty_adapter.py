"""
api/gamification/integrations/djoyalty_adapter.py

DJoyalty ↔ Gamification bidirectional bridge।

djoyalty.events (POINTS_EARNED, TIER_UPGRADED, BADGE_UNLOCKED, STREAK_MILESTONE)
↔ api.gamification.UserAchievement

djoyalty already has its own loyalty system — gamification reads from it and syncs
badge/tier events so both systems stay consistent.

Wire-up (api/djoyalty/apps.py ready() বা event_handlers.py-তে):
    from api.gamification.integrations.djoyalty_adapter import DJoyaltyGamificationAdapter
    DJoyaltyGamificationAdapter().register_handlers()
"""
from __future__ import annotations
import logging
from typing import Any
logger = logging.getLogger(__name__)

# DJoyalty tier → gamification achievement map
TIER_MAP = {
    "bronze":   {"title": "Bronze Loyalist",   "points": 10},
    "silver":   {"title": "Silver Loyalist",   "points": 30},
    "gold":     {"title": "Gold Loyalist",     "points": 75},
    "platinum": {"title": "Platinum Loyalist", "points": 150},
    "diamond":  {"title": "Diamond Loyalist",  "points": 300},
}


class DJoyaltyGamificationAdapter:

    def on_tier_upgraded(self, event: Any) -> None:
        """DJoyalty TIER_UPGRADED → gamification tier achievement।"""
        user     = getattr(event, "customer", None) or getattr(event, "user", None)
        new_tier = str(getattr(event, "new_tier", "") or "").lower()
        if not user or not new_tier:
            return
        try:
            cfg = TIER_MAP.get(new_tier)
            if cfg:
                self._award(user, cfg["title"],
                            f"DJoyalty {new_tier.title()} tier-এ উন্নীত হয়েছেন!",
                            cfg["points"],
                            {"source": "djoyalty", "tier": new_tier, "event": "tier_upgraded"})
            self._track(user, "djoyalty_tier_upgraded", {"new_tier": new_tier})
        except Exception as exc:
            logger.error("[DJoyaltyAdapter] on_tier_upgraded failed: %s", exc)

    def on_badge_unlocked(self, event: Any) -> None:
        """DJoyalty BADGE_UNLOCKED → gamification BADGE achievement।"""
        user       = getattr(event, "customer", None) or getattr(event, "user", None)
        badge_name = str(getattr(event, "badge_name", "") or "")
        if not user or not badge_name:
            return
        try:
            self._award(user, f"Badge: {badge_name}",
                        f"DJoyalty-এ '{badge_name}' badge অর্জন করেছেন!",
                        25,
                        {"source": "djoyalty", "badge": badge_name, "event": "badge_unlocked"})
            self._track(user, "djoyalty_badge_unlocked", {"badge": badge_name})
        except Exception as exc:
            logger.error("[DJoyaltyAdapter] on_badge_unlocked failed: %s", exc)

    def on_streak_milestone(self, event: Any) -> None:
        """DJoyalty STREAK_MILESTONE → gamification STREAK achievement।"""
        user  = getattr(event, "customer", None) or getattr(event, "user", None)
        days  = int(getattr(event, "streak_days", 0) or 0)
        if not user or not days:
            return
        try:
            from api.gamification.integrations.adapter import gamification_adapter
            gamification_adapter.on_daily_checkin(user=user, consecutive_days=days)
        except Exception as exc:
            logger.error("[DJoyaltyAdapter] on_streak_milestone failed: %s", exc)

    def on_points_earned(self, event: Any) -> None:
        """DJoyalty POINTS_EARNED → gamification analytics track।"""
        user   = getattr(event, "customer", None) or getattr(event, "user", None)
        points = int(getattr(event, "points", 0) or 0)
        if not user:
            return
        try:
            self._track(user, "djoyalty_points_earned", {"points": points})
        except Exception as exc:
            logger.error("[DJoyaltyAdapter] on_points_earned failed: %s", exc)

    def register_handlers(self) -> None:
        """DJoyalty EventRegistry-তে gamification handlers register করো।"""
        try:
            from api.djoyalty.events import (
                EventRegistry, TIER_UPGRADED, BADGE_UNLOCKED,
                STREAK_MILESTONE, POINTS_EARNED
            )
            registry = EventRegistry.get_instance()
            adapter  = self
            registry.register(TIER_UPGRADED,    adapter.on_tier_upgraded)
            registry.register(BADGE_UNLOCKED,   adapter.on_badge_unlocked)
            registry.register(STREAK_MILESTONE, adapter.on_streak_milestone)
            registry.register(POINTS_EARNED,    adapter.on_points_earned)
            logger.info("[DJoyaltyAdapter] Event handlers registered.")
        except ImportError:
            logger.warning("[DJoyaltyAdapter] djoyalty not available — skipping handlers.")
        except Exception as exc:
            logger.error("[DJoyaltyAdapter] register_handlers failed: %s", exc)

    def push_achievement_to_djoyalty(self, achievement: Any) -> None:
        """
        Gamification achievement → DJoyalty points push (reverse sync)।
        Called from gamification receivers.on_achievement_awarded।
        """
        try:
            from api.djoyalty.events import EventDispatcher, POINTS_EARNED, LoyaltyEvent
            user   = getattr(achievement, "user", None)
            points = int(getattr(achievement, "points_awarded", 0) or 0)
            if not user or not points:
                return
            event = LoyaltyEvent(
                event_type=POINTS_EARNED,
                customer=user,
                points=points,
                metadata={"source": "gamification",
                          "achievement_id": str(getattr(achievement, "id", ""))}
            )
            EventDispatcher.dispatch(event)
        except ImportError:
            pass
        except Exception as exc:
            logger.debug("[DJoyaltyAdapter] push_achievement_to_djoyalty failed: %s", exc)

    def _award(self, user, title, description, points, metadata):
        from api.gamification.services import award_achievement
        from api.gamification.choices import AchievementType
        try:
            award_achievement(user_id=user.pk, achievement_type=AchievementType.BADGE,
                              title=title, description=description, points=points, metadata=metadata)
        except Exception as exc:
            logger.debug("[DJoyaltyAdapter] _award skipped: %s", exc)

    def _track(self, user, event, properties):
        try:
            from api.gamification.integrations.adapter import gamification_adapter
            gamification_adapter.track_event(event, user=user, properties=properties)
        except Exception:
            pass
