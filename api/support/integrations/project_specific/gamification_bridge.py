# api/support/integrations/project_specific/gamification_bridge.py
"""
Gamification Bridge — connects support outcomes with gamification/djoyalty.

YOUR gamification app has: ContestCycle, LeaderboardSnapshot, UserAchievement
YOUR djoyalty app handles: loyalty points

This bridge:
  1. Awards loyalty points when users get issues resolved
  2. Gives achievements for good support interactions
  3. Checks user achievements to determine support priority
  4. Rewards agents for high CSAT scores
"""
import logging
logger = logging.getLogger(__name__)


class GamificationBridge:
    """Connect support outcomes to gamification and loyalty systems."""

    # ── User Rewards ─────────────────────────────────────────
    def award_resolution_points(self, ticket) -> bool:
        """Award loyalty points to user when ticket is resolved."""
        try:
            POINTS = {
                "payment":    50,  # Important issues get more points
                "withdrawal": 50,
                "fraud":      100, # Security-related get bonus
                "kyc":        30,
                "coins":      20,
                "other":      10,
            }
            points = POINTS.get(ticket.category or "other", 10)
            return self._award_points(
                user   = ticket.user,
                points = points,
                reason = f"Support ticket resolved: {ticket.ticket_id}",
                event  = "ticket_resolved",
            )
        except Exception as e:
            logger.debug(f"GamificationBridge.award_resolution_points: {e}")
            return False

    def award_rating_points(self, ticket, score: int) -> bool:
        """Award points when user submits a CSAT rating (encourages feedback)."""
        if score >= 4:
            return self._award_points(
                user   = ticket.user,
                points = 5,
                reason = "Support feedback submitted",
                event  = "csat_submitted",
            )
        return False

    def _award_points(self, user, points: int, reason: str, event: str) -> bool:
        """Award loyalty points via djoyalty app."""
        try:
            from django.apps import apps
            # Try djoyalty first
            for app, model in [("djoyalty", "LoyaltyTransaction"), ("djoyalty", "PointsTransaction")]:
                try:
                    M = apps.get_model(app, model)
                    M.objects.create(
                        user   = user,
                        points = points,
                        reason = reason,
                        event  = event,
                        source = "support",
                    )
                    logger.info(f"Awarded {points} points to {user.username}: {reason}")
                    return True
                except (LookupError, TypeError):
                    continue

            # Try gamification
            for app, model in [("gamification", "PointsAward"), ("gamification", "UserPoints")]:
                try:
                    M = apps.get_model(app, model)
                    M.objects.create(
                        user   = user,
                        points = points,
                        reason = reason,
                    )
                    return True
                except (LookupError, TypeError):
                    continue
            return False
        except Exception as e:
            logger.debug(f"GamificationBridge._award_points: {e}")
            return False

    def check_user_achievements(self, user) -> dict:
        """
        Check user's achievements — VIP/high-level users get priority support.
        Returns context useful for SLA prioritization.
        """
        try:
            from django.apps import apps
            UserAchievement = apps.get_model("gamification", "UserAchievement")
            achievements = UserAchievement.objects.filter(user=user)

            achievement_names = [str(a.achievement_type) for a in achievements if hasattr(a, "achievement_type")]
            is_vip = any(kw in name.lower() for name in achievement_names
                         for kw in ["vip","gold","premium","top","elite"])

            return {
                "total_achievements": achievements.count(),
                "is_vip":             is_vip,
                "achievement_names":  achievement_names[:5],
            }
        except Exception:
            return {"total_achievements": 0, "is_vip": False}

    # ── Agent Rewards ─────────────────────────────────────────
    def reward_agent_high_csat(self, agent_user, ticket, score: int) -> bool:
        """Reward agents who get 5-star ratings."""
        if score == 5:
            return self._award_points(
                user   = agent_user,
                points = 20,
                reason = f"5-star CSAT on ticket {ticket.ticket_id}",
                event  = "agent_high_csat",
            )
        return False

    def get_support_priority_from_gamification(self, user) -> str:
        """
        Determine support queue priority based on user's gamification status.
        Returns: "urgent" | "high" | "medium" | "low"
        """
        data = self.check_user_achievements(user)
        if data.get("is_vip"):
            return "high"
        if data.get("total_achievements", 0) >= 10:
            return "medium"
        return "low"


gamification_bridge = GamificationBridge()