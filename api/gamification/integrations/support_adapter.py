"""
api/gamification/integrations/support_adapter.py

Support ↔ Gamification adapter।

Ticket resolve / CSAT rating → loyalty points + achievement।
User gamification status → support priority।

Wire-up (api/support/hooks.py বা apps.py তে):
    from api.gamification.integrations.support_adapter import SupportGamificationAdapter
    SupportGamificationAdapter().connect_hooks()
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Ticket category → points map
CATEGORY_POINTS = {
    "payment":    50,
    "withdrawal": 50,
    "fraud":      100,
    "kyc":        30,
    "coins":      20,
    "other":      10,
}

# CSAT score → points
CSAT_POINTS = {5: 15, 4: 5}

# VIP achievement keywords
VIP_KEYWORDS = {"vip", "gold", "premium", "top", "elite", "diamond", "platinum"}


class SupportGamificationAdapter:
    """Support events থেকে gamification actions trigger করে।"""

    def on_ticket_resolved(self, ticket: Any) -> None:
        """
        Support ticket resolve হলে user-কে BONUS points দাও।

        Points: category অনুযায়ী (payment=50, fraud=100, other=10)

        Called from: api.support.hooks / signals (ticket status → resolved)
        """
        user = getattr(ticket, "user", None)
        if user is None:
            logger.warning("[SupportAdapter] ticket.user is None — skip")
            return

        category = str(getattr(ticket, "category", "other") or "other").lower()
        points   = CATEGORY_POINTS.get(category, 10)
        ticket_id = str(getattr(ticket, "ticket_id", getattr(ticket, "id", "?")))

        try:
            self._award(
                user=user,
                title=f"Issue Resolved ({category.title()})",
                description=f"Support ticket #{ticket_id} সফলভাবে সমাধান হয়েছে।",
                points=points,
                metadata={
                    "source":     "support",
                    "ticket_id":  ticket_id,
                    "category":   category,
                    "event":      "ticket_resolved",
                },
            )
            logger.info(
                "[SupportAdapter] Awarded %d points to user=%s (ticket=%s)",
                points, getattr(user, "id", "?"), ticket_id
            )
            self._track(user, "support_ticket_resolved", {
                "ticket_id": ticket_id,
                "category":  category,
                "points":    points,
            })
        except Exception as exc:
            logger.error("[SupportAdapter] on_ticket_resolved failed: %s", exc)

    def on_csat_submitted(self, ticket: Any, score: int) -> None:
        """
        CSAT rating submit হলে — good rating-এ user + agent উভয়কে award করো।

        score 5 → 15 points (user)
        score 4 → 5 points  (user)
        score 5 → agent-কেও 20 points

        Called from: api.support (rating submitted signal)
        """
        user     = getattr(ticket, "user", None)
        agent    = getattr(ticket, "assigned_agent", None) or getattr(ticket, "agent", None)
        ticket_id = str(getattr(ticket, "ticket_id", getattr(ticket, "id", "?")))

        # User reward
        if user and score >= 4:
            points = CSAT_POINTS.get(score, 0)
            if points:
                try:
                    self._award(
                        user=user,
                        title="Feedback Champion",
                        description=f"Support feedback দিয়েছেন — {score}⭐ rating!",
                        points=points,
                        metadata={
                            "source":    "support",
                            "ticket_id": ticket_id,
                            "event":     "csat_submitted",
                            "score":     score,
                        },
                    )
                except Exception as exc:
                    logger.debug("[SupportAdapter] on_csat_submitted (user) skipped: %s", exc)

        # Agent reward — 5-star only
        if agent and score == 5:
            try:
                self._award(
                    user=agent,
                    title="5-Star Agent",
                    description=f"Ticket #{ticket_id}-এ 5-star CSAT অর্জন করেছেন!",
                    points=20,
                    metadata={
                        "source":    "support",
                        "ticket_id": ticket_id,
                        "event":     "agent_high_csat",
                        "score":     score,
                    },
                )
                logger.info(
                    "[SupportAdapter] Agent %s awarded 20pts for 5-star CSAT (ticket=%s)",
                    getattr(agent, "id", "?"), ticket_id
                )
            except Exception as exc:
                logger.debug("[SupportAdapter] on_csat_submitted (agent) skipped: %s", exc)

        self._track(user, "support_csat_submitted", {"score": score, "ticket_id": ticket_id})

    def get_user_context(self, user: Any) -> dict:
        """
        User-এর gamification status বের করো — support priority নির্ধারণে ব্যবহার হয়।

        Returns:
            {
                "is_vip":             bool,
                "total_achievements": int,
                "achievement_names":  list[str],
                "priority":           "high" | "medium" | "low",
                "total_points":       int,
            }

        Called from: api.support (SLA/ticket priority logic)
        """
        try:
            from api.gamification.models import UserAchievement
            from api.gamification.services import get_user_total_points

            achievements = UserAchievement.objects.filter(
                user=user, is_awarded=True
            ).values_list("achievement_type", "title")

            names   = [f"{t}: {n}" for t, n in achievements[:10]]
            is_vip  = any(
                kw in (title or "").lower()
                for _, title in achievements
                for kw in VIP_KEYWORDS
            )

            total_points = 0
            try:
                total_points = get_user_total_points(user_id=user.pk) or 0
            except Exception:
                pass

            count    = achievements.count()
            priority = "high" if is_vip else ("medium" if count >= 10 else "low")

            return {
                "is_vip":             is_vip,
                "total_achievements": count,
                "achievement_names":  names,
                "priority":           priority,
                "total_points":       total_points,
            }
        except Exception as exc:
            logger.error("[SupportAdapter] get_user_context failed: %s", exc)
            return {
                "is_vip":             False,
                "total_achievements": 0,
                "achievement_names":  [],
                "priority":           "low",
                "total_points":       0,
            }

    def connect_hooks(self) -> None:
        """
        api.support.hooks-এ gamification hooks register করো।
        api/support/apps.py ready()-তে call করো।

        Example:
            class SupportConfig(AppConfig):
                def ready(self):
                    from api.gamification.integrations.support_adapter import (
                        SupportGamificationAdapter
                    )
                    SupportGamificationAdapter().connect_hooks()
        """
        try:
            from django.db.models.signals import post_save

            adapter = self

            @post_save.connect
            def _on_ticket_save(sender, instance, **kwargs):
                sname = sender.__name__
                if sname in ("SupportTicket", "Ticket"):
                    status = getattr(instance, "status", "")
                    if status in ("resolved", "closed"):
                        adapter.on_ticket_resolved(instance)

            @post_save.connect
            def _on_rating_save(sender, instance, created, **kwargs):
                if sender.__name__ in ("TicketRating", "CSATRating") and created:
                    ticket = getattr(instance, "ticket", None)
                    score  = int(getattr(instance, "score", getattr(instance, "rating", 0)))
                    if ticket:
                        adapter.on_csat_submitted(ticket=ticket, score=score)

            logger.info("[SupportAdapter] Hooks connected.")
        except Exception as exc:
            logger.error("[SupportAdapter] connect_hooks failed: %s", exc)

    # ── Private ────────────────────────────────────────────────────────────────

    def _award(self, user: Any, title: str, description: str,
               points: int, metadata: dict) -> None:
        from api.gamification.services import award_achievement
        from api.gamification.choices import AchievementType
        award_achievement(
            user_id=user.pk,
            achievement_type=AchievementType.BONUS,
            title=title,
            description=description,
            points=points,
            metadata=metadata,
        )

    def _track(self, user: Any, event: str, properties: dict) -> None:
        try:
            from api.gamification.integrations.adapter import gamification_adapter
            gamification_adapter.track_event(event, user=user, properties=properties)
        except Exception:
            pass
