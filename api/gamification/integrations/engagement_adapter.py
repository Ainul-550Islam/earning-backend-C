"""
api/gamification/integrations/engagement_adapter.py

Engagement ↔ Gamification adapter।

Daily check-in / spin wheel → streak + bonus achievement।

Wire-up (api/engagement/apps.py ready() তে):
    from api.gamification.integrations.engagement_adapter import EngagementGamificationAdapter
    EngagementGamificationAdapter().connect_signals()
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Streak milestones → achievement
STREAK_MILESTONES = {
    3:  {"title": "3-Day Streak",   "points": 15,  "badge": "streak_3"},
    7:  {"title": "7-Day Streak",   "points": 35,  "badge": "streak_7"},
    14: {"title": "2-Week Streak",  "points": 75,  "badge": "streak_14"},
    30: {"title": "Monthly Streak", "points": 200, "badge": "streak_30"},
    60: {"title": "Iron Will",      "points": 500, "badge": "streak_60"},
    90: {"title": "Unstoppable",    "points": 1000,"badge": "streak_90"},
}

# Spin wheel big win threshold
SPIN_BIG_WIN_THRESHOLD = 50


class EngagementGamificationAdapter:
    """Engagement events থেকে gamification streak/bonus achievements trigger করে।"""

    def on_checkin(self, user: Any, consecutive_days: int) -> None:
        """
        Daily check-in হলে — streak milestone চেক করো।

        consecutive_days 3/7/14/30/60/90 হলে STREAK achievement award করো।

        Called from:
          - api.engagement.services.EngagementService.process_daily_checkin()
          - api.gamification.integrations.adapter.on_daily_checkin()
        """
        if not user:
            return

        try:
            config = STREAK_MILESTONES.get(consecutive_days)
            if config:
                self._award_streak(
                    user=user,
                    title=config["title"],
                    description=(
                        f"টানা {consecutive_days} দিন check-in করেছেন! "
                        f"+{config['points']} points"
                    ),
                    points=config["points"],
                    badge=config["badge"],
                    consecutive_days=consecutive_days,
                )

            # Daily check-in badge (first ever)
            if consecutive_days == 1:
                self._award_bonus(
                    user=user,
                    title="Daily Check-in",
                    description="প্রথম daily check-in সম্পন্ন!",
                    points=5,
                    metadata={"event": "first_checkin", "badge": "first_checkin"},
                )

            self._track(user, "engagement_daily_checkin", {
                "consecutive_days": consecutive_days,
            })
        except Exception as exc:
            logger.error("[EngagementAdapter] on_checkin failed: %s", exc)

    def on_spin(self, user: Any, coins_won: int) -> None:
        """
        Spin wheel use করলে — big win achievement চেক করো।

        coins_won >= 50 হলে BONUS achievement দাও।

        Called from:
          - api.engagement.services.EngagementService.spin_wheel()
          - api.gamification.integrations.adapter.on_spin_wheel()
        """
        if not user:
            return

        try:
            if coins_won >= SPIN_BIG_WIN_THRESHOLD:
                self._award_bonus(
                    user=user,
                    title="Big Spinner!",
                    description=f"Spin wheel-এ {coins_won} coins জিতেছেন!",
                    points=coins_won // 5,  # proportional points
                    metadata={
                        "event":      "spin_big_win",
                        "coins_won":  coins_won,
                        "badge":      "spin_big_win",
                    },
                )

            self._track(user, "engagement_spin_wheel", {"coins_won": coins_won})
        except Exception as exc:
            logger.error("[EngagementAdapter] on_spin failed: %s", exc)

    def connect_signals(self) -> None:
        """
        api.engagement signals → gamification connect করো।
        api/engagement/apps.py ready()-তে call করো।

        Example:
            class EngagementConfig(AppConfig):
                def ready(self):
                    from api.gamification.integrations.engagement_adapter import (
                        EngagementGamificationAdapter
                    )
                    EngagementGamificationAdapter().connect_signals()
        """
        try:
            from django.db.models.signals import post_save

            adapter = self

            @post_save.connect
            def _on_checkin(sender, instance, created, **kwargs):
                if sender.__name__ == "DailyCheckIn" and created:
                    user = getattr(instance, "user", None)
                    days = getattr(instance, "consecutive_days", 1)
                    if user:
                        adapter.on_checkin(user=user, consecutive_days=days)

            @post_save.connect
            def _on_spin(sender, instance, created, **kwargs):
                if sender.__name__ == "SpinWheel" and created:
                    user       = getattr(instance, "user", None)
                    coins_won  = int(getattr(instance, "coins_won", 0))
                    if user:
                        adapter.on_spin(user=user, coins_won=coins_won)

            logger.info("[EngagementAdapter] Signals connected.")
        except Exception as exc:
            logger.error("[EngagementAdapter] connect_signals failed: %s", exc)

    # ── Private ────────────────────────────────────────────────────────────────

    def _award_streak(self, user: Any, title: str, description: str,
                      points: int, badge: str, consecutive_days: int) -> None:
        from api.gamification.services import award_achievement
        from api.gamification.choices import AchievementType
        try:
            award_achievement(
                user_id=user.pk,
                achievement_type=AchievementType.STREAK,
                title=title,
                description=description,
                points=points,
                metadata={
                    "badge":            badge,
                    "consecutive_days": consecutive_days,
                    "source":           "engagement",
                },
            )
        except Exception as exc:
            logger.debug("[EngagementAdapter] _award_streak skipped: %s", exc)

    def _award_bonus(self, user: Any, title: str, description: str,
                     points: int, metadata: dict) -> None:
        from api.gamification.services import award_achievement
        from api.gamification.choices import AchievementType
        try:
            award_achievement(
                user_id=user.pk,
                achievement_type=AchievementType.BONUS,
                title=title,
                description=description,
                points=points,
                metadata={"source": "engagement", **metadata},
            )
        except Exception as exc:
            logger.debug("[EngagementAdapter] _award_bonus skipped: %s", exc)

    def _track(self, user: Any, event: str, properties: dict) -> None:
        try:
            from api.gamification.integrations.adapter import gamification_adapter
            gamification_adapter.track_event(event, user=user, properties=properties)
        except Exception:
            pass
