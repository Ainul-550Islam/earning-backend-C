# api/support/integrations/project_specific/customer_journey.py
"""
Customer Journey — full user timeline for agent context.

When agent opens a ticket, shows complete user history:
  - All support tickets
  - Wallet transactions
  - Offer completions
  - KYC status changes
  - Fraud alerts
  - Login history
  - Subscription changes
  - Gamification milestones

This gives agents full picture without switching apps.
"""
import logging
logger = logging.getLogger(__name__)


class CustomerJourneyBuilder:
    """Build comprehensive user journey timeline for support agents."""

    def build_timeline(self, user, days: int = 90) -> dict:
        """
        Build complete user journey timeline.
        Returns structured data for agent display.
        """
        from django.utils import timezone
        from datetime import timedelta
        since = timezone.now() - timedelta(days=days)

        timeline = {
            "user_id":        user.id,
            "username":       user.username,
            "email":          user.email,
            "member_since":   str(user.date_joined.date()) if hasattr(user, "date_joined") else "",
            "period_days":    days,
            "generated_at":   timezone.now().isoformat(),
            "sections":       {},
        }

        # ── Support History ────────────────────────────────────
        timeline["sections"]["support"] = self._get_support_history(user, since)

        # ── Wallet ────────────────────────────────────────────
        timeline["sections"]["wallet"] = self._get_wallet_history(user, since)

        # ── Offers/Postback ───────────────────────────────────
        timeline["sections"]["offers"] = self._get_offer_history(user, since)

        # ── KYC ───────────────────────────────────────────────
        timeline["sections"]["kyc"] = self._get_kyc_history(user)

        # ── Fraud Alerts ──────────────────────────────────────
        timeline["sections"]["fraud"] = self._get_fraud_history(user, since)

        # ── Subscription ──────────────────────────────────────
        timeline["sections"]["subscription"] = self._get_subscription_info(user)

        # ── Gamification ──────────────────────────────────────
        timeline["sections"]["gamification"] = self._get_gamification_data(user)

        # ── Risk Summary ──────────────────────────────────────
        timeline["risk_summary"] = self._compute_risk_summary(timeline["sections"])

        return timeline

    def _get_support_history(self, user, since) -> dict:
        try:
            from api.support.models import SupportTicket, OfferDispute
            tickets  = SupportTicket.objects.filter(user=user, created_at__gte=since).order_by("-created_at")
            disputes = OfferDispute.objects.filter(user=user, created_at__gte=since).order_by("-created_at")
            return {
                "tickets": [{"id":t.ticket_id,"status":t.status,"category":t.category,"created_at":t.created_at.isoformat()} for t in tickets[:10]],
                "total_tickets": tickets.count(),
                "open_tickets":  tickets.filter(status__in=["open","in_progress","waiting_user"]).count(),
                "disputes":      [{"id":d.id,"offer_id":d.offer_id,"status":d.status,"amount":str(d.expected_amount)} for d in disputes[:5]],
                "total_disputes":disputes.count(),
            }
        except Exception:
            return {}

    def _get_wallet_history(self, user, since) -> dict:
        try:
            from api.support.integrations.integ_adapter import wallet_adapter
            balance = wallet_adapter.get_balance(user)
            txns    = wallet_adapter.get_transactions(user, limit=10)
            return {
                "current_balance": balance.get("available", 0),
                "total_earned":    balance.get("total_earned", 0),
                "is_locked":       balance.get("is_locked", False),
                "recent_transactions": txns,
            }
        except Exception:
            return {}

    def _get_offer_history(self, user, since) -> dict:
        try:
            from django.apps import apps
            result = {}
            for app, model in [("offerwall","OfferConversion"), ("postback","PostbackLog")]:
                try:
                    M = apps.get_model(app, model)
                    qs = M.objects.filter(
                        **{"user": user} if hasattr(M, "user") else {},
                        created_at__gte=since,
                    )
                    result[app] = {"count": qs.count()}
                except Exception:
                    pass
            return result
        except Exception:
            return {}

    def _get_kyc_history(self, user) -> dict:
        try:
            from api.support.integrations.integ_adapter import kyc_adapter
            return kyc_adapter.get_status(user)
        except Exception:
            return {}

    def _get_fraud_history(self, user, since) -> dict:
        try:
            from api.support.integrations.integ_adapter import fraud_adapter
            risk = fraud_adapter.get_risk_score(user)
            mod  = fraud_adapter.get_offer_completions(user, "")
            return {"risk_score": risk.get("score",0), "is_flagged": risk.get("is_flagged",False)}
        except Exception:
            return {}

    def _get_subscription_info(self, user) -> dict:
        try:
            from api.support.integrations.project_specific.subscription_sla import subscription_sla
            return subscription_sla.get_subscription_info(user)
        except Exception:
            return {}

    def _get_gamification_data(self, user) -> dict:
        try:
            from api.support.integrations.project_specific.gamification_bridge import gamification_bridge
            return gamification_bridge.check_user_achievements(user)
        except Exception:
            return {}

    def _compute_risk_summary(self, sections: dict) -> dict:
        fraud = sections.get("fraud", {})
        return {
            "fraud_score":      fraud.get("risk_score", 0),
            "is_flagged":       fraud.get("is_flagged", False),
            "kyc_verified":     sections.get("kyc", {}).get("is_verified", False),
            "has_subscription": sections.get("subscription", {}).get("has_subscription", False),
            "total_tickets":    sections.get("support", {}).get("total_tickets", 0),
            "total_disputes":   sections.get("support", {}).get("total_disputes", 0),
        }

    def get_quick_summary(self, user) -> str:
        """One-line summary for agent tooltip."""
        try:
            from api.support.models import SupportTicket, OfferDispute
            tickets  = SupportTicket.objects.filter(user=user).count()
            disputes = OfferDispute.objects.filter(user=user).count()
            return f"Tickets: {tickets} | Disputes: {disputes} | Member since {user.date_joined.strftime('%Y-%m') if hasattr(user,'date_joined') else 'N/A'}"
        except Exception:
            return ""


customer_journey = CustomerJourneyBuilder()