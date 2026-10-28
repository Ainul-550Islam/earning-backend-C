# api/support/integrations/project_specific/churn_risk_support.py
"""
Churn Risk Support — identify and prioritize high-churn-risk users.

Uses ai_engine.PREDICTION_ENGINES.churn_predictor.
High-risk churners get:
  - Automatically escalated priority
  - Personal agent assignment
  - Bonus resolution credits
  - Proactive outreach after resolution
"""
import logging
logger = logging.getLogger(__name__)


class ChurnRiskSupportManager:
    """Manage support for users at high risk of churning."""

    CHURN_HIGH_THRESHOLD   = 0.7
    CHURN_MEDIUM_THRESHOLD = 0.4

    def get_churn_risk(self, user) -> dict:
        """Get churn probability from ai_engine."""
        try:
            from api.ai_engine.PREDICTION_ENGINES.churn_predictor import ChurnPredictor
            predictor = ChurnPredictor()
            result = predictor.predict_user(user.id)
            prob = result.get("probability", 0.0)
            return {
                "probability": prob,
                "risk_level":  "high" if prob >= self.CHURN_HIGH_THRESHOLD else "medium" if prob >= self.CHURN_MEDIUM_THRESHOLD else "low",
                "is_high_risk":prob >= self.CHURN_HIGH_THRESHOLD,
                "factors":     result.get("top_factors", []),
            }
        except Exception as e:
            logger.debug(f"ChurnRiskSupportManager.get_churn_risk: {e}")
            return {"probability": 0.0, "risk_level": "low", "is_high_risk": False}

    def adjust_ticket_for_churn_risk(self, ticket) -> dict:
        """
        Adjust ticket handling based on churn risk.
        Called during ticket creation.
        """
        churn = self.get_churn_risk(ticket.user)
        actions = {}

        if churn["is_high_risk"]:
            # Auto-upgrade priority
            if ticket.priority in ("low", "medium"):
                ticket.priority = "high"
                ticket.save(update_fields=["priority"])
                actions["priority_upgraded"] = True

            # Add internal note for agent
            try:
                from api.support.models import TicketMessage
                from django.contrib.auth import get_user_model
                bot = get_user_model().objects.filter(is_superuser=True).first()
                if bot:
                    TicketMessage.objects.create(
                        ticket=ticket, sender=bot, is_agent=True, is_internal=True,
                        content=(
                            "⚠️ CHURN RISK ALERT\n"
                            f"User churn probability: {churn['probability']:.0%} (HIGH)\n"
                            f"Factors: {', '.join(churn['factors'][:3])}\n"
                            "Please handle with extra care and quick resolution."
                        ),
                    )
                    actions["churn_note_added"] = True
            except Exception:
                pass

        actions["churn_risk"] = churn["risk_level"]
        return actions

    def post_resolution_action(self, ticket) -> dict:
        """
        After resolving ticket for high-churn-risk user:
        - Send extra satisfaction survey
        - Offer bonus points
        - Schedule follow-up
        """
        churn = self.get_churn_risk(ticket.user)
        actions = {}

        if churn["is_high_risk"]:
            # Award extra loyalty points
            try:
                from api.support.integrations.project_specific.gamification_bridge import gamification_bridge
                gamification_bridge._award_points(
                    user   = ticket.user,
                    points = 50,
                    reason = f"Priority resolution bonus (ticket {ticket.ticket_id})",
                    event  = "churn_risk_resolution_bonus",
                )
                actions["bonus_points_awarded"] = 50
            except Exception:
                pass

        return actions


churn_risk_manager = ChurnRiskSupportManager()