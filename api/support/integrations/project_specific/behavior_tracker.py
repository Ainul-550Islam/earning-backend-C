# api/support/integrations/project_specific/behavior_tracker.py
"""
Behavior Tracker — tracks support ticket behavior patterns.

Uses your behavior_analytics app to:
  - Track ticket submission patterns (time of day, category trends)
  - Detect abnormal dispute submission behavior
  - Feed data back to behavior_analytics for user profiling
  - Trigger proactive support based on behavioral signals
"""
import logging
from django.utils import timezone
logger = logging.getLogger(__name__)


class SupportBehaviorTracker:
    """Tracks support interactions in behavior_analytics."""

    def track_ticket_event(self, user, event_type: str, properties: dict = None) -> bool:
        """Track a support event in behavior_analytics."""
        try:
            from django.apps import apps
            # Try different behavior analytics event models
            for app, model in [
                ("behavior_analytics", "UserEvent"),
                ("behavior_analytics", "BehaviorEvent"),
                ("analytics", "Event"),
            ]:
                try:
                    M = apps.get_model(app, model)
                    event_data = {
                        "event_type":  event_type,
                        "properties":  {**(properties or {}), "source": "support"},
                    }
                    for user_field in ("user", "actor"):
                        try:
                            M.objects.create(**{user_field: user, **event_data})
                            return True
                        except TypeError:
                            continue
                except LookupError:
                    continue
            return False
        except Exception as e:
            logger.debug(f"SupportBehaviorTracker.track_ticket_event: {e}")
            return False

    def track_ticket_created(self, ticket) -> None:
        """Track when user creates a support ticket."""
        self.track_ticket_event(
            ticket.user,
            "support_ticket_created",
            {
                "ticket_id": ticket.ticket_id,
                "category":  ticket.category or "",
                "priority":  ticket.priority or "medium",
                "channel":   ticket.channel or "web",
                "hour":      timezone.now().hour,
            }
        )

    def track_dispute_submitted(self, dispute) -> None:
        """Track offer dispute submission — detect gaming behavior."""
        self.track_ticket_event(
            dispute.user,
            "offer_dispute_submitted",
            {
                "offer_id":        dispute.offer_id,
                "expected_amount": float(dispute.expected_amount or 0),
            }
        )

    def track_csat_rating(self, ticket, score: int) -> None:
        """Track customer satisfaction rating."""
        self.track_ticket_event(
            ticket.user,
            "support_csat_submitted",
            {
                "ticket_id": ticket.ticket_id,
                "score":     score,
                "category":  ticket.category or "",
            }
        )

    def track_chat_session(self, session) -> None:
        """Track live chat session start."""
        self.track_ticket_event(
            session.user,
            "support_chat_started",
            {"session_id": str(session.session_id)}
        )

    def get_user_support_profile(self, user) -> dict:
        """Get user's historical support behavior profile."""
        try:
            from api.support.models import SupportTicket, OfferDispute
            tickets  = SupportTicket.objects.filter(user=user)
            disputes = OfferDispute.objects.filter(user=user)
            return {
                "total_tickets":      tickets.count(),
                "open_tickets":       tickets.filter(status__in=["open","in_progress","waiting_user"]).count(),
                "resolved_tickets":   tickets.filter(status="resolved").count(),
                "total_disputes":     disputes.count(),
                "approved_disputes":  disputes.filter(status="approved").count(),
                "rejected_disputes":  disputes.filter(status="rejected").count(),
                "avg_csat":           self._get_avg_csat(tickets),
                "dispute_success_rate": self._get_dispute_rate(disputes),
                "is_frequent_disputer": disputes.count() >= 5,
            }
        except Exception as e:
            logger.debug(f"get_user_support_profile: {e}")
            return {}

    def _get_avg_csat(self, tickets) -> float:
        try:
            rated = tickets.filter(satisfaction_rating__isnull=False)
            if not rated.exists():
                return 0.0
            return round(sum(t.satisfaction_rating for t in rated) / rated.count(), 2)
        except Exception:
            return 0.0

    def _get_dispute_rate(self, disputes) -> float:
        total = disputes.count()
        if not total:
            return 0.0
        approved = disputes.filter(status="approved").count()
        return round(approved / total * 100, 1)

    def detect_abnormal_dispute_pattern(self, user) -> dict:
        """
        Detect if user is gaming the dispute system.
        Returns risk assessment.
        """
        from api.support.models import OfferDispute
        from datetime import timedelta
        now = timezone.now()
        profile = self.get_user_support_profile(user)
        red_flags = []
        risk = "low"

        week_disputes = OfferDispute.objects.filter(
            user=user, created_at__gte=now - timedelta(days=7)
        ).count()
        if week_disputes >= 5:
            red_flags.append(f"{week_disputes} disputes in last 7 days")
            risk = "high"

        reject_rate = 100 - profile.get("dispute_success_rate", 100)
        if reject_rate > 60 and profile.get("total_disputes", 0) >= 3:
            red_flags.append(f"{reject_rate:.0f}% rejection rate")
            risk = "high" if risk == "high" else "medium"

        return {
            "risk":       risk,
            "red_flags":  red_flags,
            "week_count": week_disputes,
        }


behavior_tracker = SupportBehaviorTracker()