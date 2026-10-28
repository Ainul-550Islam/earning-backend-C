"""
api/gamification/integrations/notifications_adapter.py

Gamification ↔ Notifications adapter।

Achievement award / leaderboard finalized / contest reward হলে
api.notifications-এ notification পাঠায়।

Wire-up:
    gamification/receivers.py-এর signal handlers থেকে call করা হয়।
    কোনো manual wire-up দরকার নেই।
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Notification types (api.notifications.choices থেকে নেওয়া)
NOTIF_ACHIEVEMENT_UNLOCKED = "achievement_unlocked"
NOTIF_MILESTONE_REACHED    = "milestone_reached"
NOTIF_LEADERBOARD_UPDATED  = "leaderboard_updated"


class NotificationsGamificationAdapter:
    """Gamification events → api.notifications."""

    def send_achievement_notification(self, achievement: Any) -> None:
        """
        Achievement award হলে user-কে push + in_app notification পাঠাও।

        Called from: gamification/receivers.py → on_achievement_awarded
        """
        user = getattr(achievement, "user", None)
        if user is None:
            logger.warning("[NotificationsAdapter] achievement.user is None — skip")
            return

        title   = getattr(achievement, "title", "Achievement Unlocked!")
        points  = getattr(achievement, "points_awarded", 0)
        ach_type = str(getattr(achievement, "achievement_type", "BADGE"))

        try:
            self._send(
                user=user,
                notification_type=NOTIF_ACHIEVEMENT_UNLOCKED,
                title="🏆 Achievement Unlocked!",
                message=f'"{title}" badge অর্জন করেছেন! +{points} points',
                data={
                    "achievement_id":   str(getattr(achievement, "id", "")),
                    "achievement_type": ach_type,
                    "points_awarded":   points,
                    "title":            title,
                },
                channels=["in_app", "push"],
                priority="high",
            )
        except Exception as exc:
            logger.error("[NotificationsAdapter] send_achievement_notification failed: %s", exc)

    def send_leaderboard_notification(self, snapshot: Any, top_n: int = 10) -> None:
        """
        Leaderboard finalize হলে top N users-কে notify করো।

        Called from: gamification/receivers.py → on_leaderboard_snapshot_finalized
        """
        try:
            entries = getattr(snapshot, "snapshot_data", []) or []
            top_entries = entries[:top_n]

            if not top_entries:
                return

            from django.contrib.auth import get_user_model
            User = get_user_model()

            for entry in top_entries:
                user_id = entry.get("user_id")
                rank    = entry.get("rank", "?")
                points  = entry.get("points", 0)

                if not user_id:
                    continue

                try:
                    user = User.objects.get(pk=user_id)
                    self._send(
                        user=user,
                        notification_type=NOTIF_LEADERBOARD_UPDATED,
                        title="📊 Leaderboard Updated!",
                        message=f"আপনি Leaderboard-এ #{rank} অবস্থানে আছেন! ({points} points)",
                        data={
                            "snapshot_id": str(getattr(snapshot, "id", "")),
                            "rank":        rank,
                            "points":      points,
                            "scope":       str(getattr(snapshot, "scope", "GLOBAL")),
                        },
                        channels=["in_app"],
                        priority="medium",
                    )
                except User.DoesNotExist:
                    continue
                except Exception as inner_exc:
                    logger.warning(
                        "[NotificationsAdapter] leaderboard notify failed for user=%s: %s",
                        user_id, inner_exc
                    )

        except Exception as exc:
            logger.error("[NotificationsAdapter] send_leaderboard_notification failed: %s", exc)

    def send_contest_reward_notification(
        self, user: Any, reward: Any, rank: int
    ) -> None:
        """
        Contest reward distribute হলে winner-কে notify করো।

        Called from: gamification.services.distribute_cycle_rewards
        """
        try:
            reward_title  = getattr(reward, "title", "Contest Reward")
            reward_value  = getattr(reward, "reward_value", 0)
            reward_type   = str(getattr(reward, "reward_type", ""))
            contest_name  = ""
            try:
                contest_name = str(reward.contest_cycle.name)
            except Exception:
                pass

            self._send(
                user=user,
                notification_type=NOTIF_MILESTONE_REACHED,
                title=f"🥇 Contest Reward! Rank #{rank}",
                message=(
                    f"{contest_name} contest-এ #{rank} হয়েছেন! "
                    f"{reward_title} পেয়েছেন।"
                ),
                data={
                    "reward_id":    str(getattr(reward, "id", "")),
                    "rank":         rank,
                    "reward_type":  reward_type,
                    "reward_value": float(reward_value),
                    "contest_name": contest_name,
                },
                channels=["in_app", "push"],
                priority="high",
            )
        except Exception as exc:
            logger.error("[NotificationsAdapter] send_contest_reward_notification failed: %s", exc)

    # ── Private ────────────────────────────────────────────────────────────────

    def _send(
        self,
        user: Any,
        notification_type: str,
        title: str,
        message: str,
        data: dict,
        channels: list,
        priority: str = "medium",
    ) -> None:
        """
        api.notifications.services.NotificationService-এ delegate করো।

        api.notifications না থাকলে gracefully skip করো।
        """
        try:
            from api.notifications.services import NotificationService
            NotificationService.send(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message,
                data=data,
                channels=channels,
                priority=priority,
            )
            logger.debug(
                "[NotificationsAdapter] Sent '%s' to user=%s",
                notification_type, getattr(user, "id", "?")
            )
        except ImportError:
            # Async fallback — Celery task দিয়ে পাঠাও
            self._send_async(
                user_id=str(user.pk),
                notification_type=notification_type,
                title=title,
                message=message,
                data=data,
            )
        except Exception as exc:
            logger.error("[NotificationsAdapter] _send failed: %s", exc)

    def _send_async(
        self,
        user_id: str,
        notification_type: str,
        title: str,
        message: str,
        data: dict,
    ) -> None:
        """Celery task দিয়ে async notification পাঠাও।"""
        try:
            from api.notifications.tasks import send_notification_task
            send_notification_task.delay(
                user_id=user_id,
                notification_type=notification_type,
                title=title,
                message=message,
                data=data,
            )
        except Exception as exc:
            logger.warning("[NotificationsAdapter] _send_async failed: %s", exc)
