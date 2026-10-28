# api/support/integrations/project_specific/subscription_sla.py
"""
Subscription SLA — premium subscribers get faster support response.

YOUR subscription app has: SubscriptionPlan, UserSubscription, Benefits.
This adapter checks user subscription → adjusts SLA deadlines accordingly.

Premium plan → 2x faster first response
Free plan → standard SLA
"""
import logging
from datetime import timedelta
from django.utils import timezone
logger = logging.getLogger(__name__)


SLA_MULTIPLIERS = {
    # plan_name_fragment: multiplier (lower = faster)
    "premium": 0.25,    # 4x faster
    "pro":     0.5,     # 2x faster
    "gold":    0.5,
    "vip":     0.25,
    "business":0.5,
    "standard":1.0,
    "free":    1.5,     # 50% slower (deprioritize free users)
    "trial":   1.0,
}


class SubscriptionSLAAdapter:
    """Adjusts SLA based on user subscription plan."""

    def get_subscription_info(self, user) -> dict:
        """Get user's current subscription plan details."""
        try:
            from django.apps import apps
            for app, sub_model in [
                ("subscription", "UserSubscription"),
                ("subscription", "Subscription"),
            ]:
                try:
                    M = apps.get_model(app, sub_model)
                    for user_field in ("user", "subscriber"):
                        sub = M.objects.filter(
                            **{user_field: user},
                            status__in=("active","trialing"),
                        ).select_related("plan").first()
                        if sub:
                            plan = getattr(sub, "plan", None)
                            return {
                                "has_subscription": True,
                                "plan_name":        plan.name if plan and hasattr(plan,"name") else "unknown",
                                "plan_tier":        getattr(plan, "tier", "standard") if plan else "standard",
                                "is_active":        True,
                                "benefits":         self._get_benefits(plan),
                            }
                except (LookupError, TypeError):
                    continue
        except Exception as e:
            logger.debug(f"SubscriptionSLAAdapter.get_subscription_info: {e}")

        return {"has_subscription": False, "plan_name": "free", "plan_tier": "free", "is_active": False}

    def _get_benefits(self, plan) -> dict:
        """Extract support-related benefits from subscription plan."""
        benefits = {"priority_support": False, "dedicated_agent": False, "chat_priority": False}
        if not plan:
            return benefits
        try:
            for benefit in plan.benefits.all() if hasattr(plan, "benefits") else []:
                benefit_type = str(getattr(benefit, "benefit_type", "")).lower()
                if "support" in benefit_type or "priority" in benefit_type:
                    benefits["priority_support"] = True
                if "dedicated" in benefit_type or "agent" in benefit_type:
                    benefits["dedicated_agent"] = True
                if "chat" in benefit_type:
                    benefits["chat_priority"] = True
        except Exception:
            pass
        return benefits

    def get_sla_multiplier(self, user) -> float:
        """Return SLA time multiplier for this user."""
        info = self.get_subscription_info(user)
        plan_name = info.get("plan_name", "free").lower()

        for key, mult in SLA_MULTIPLIERS.items():
            if key in plan_name:
                return mult

        return 1.0  # Standard SLA

    def adjust_sla_for_subscription(self, ticket) -> bool:
        """
        Adjust TicketSLA deadlines based on user subscription.
        Call after creating SLA record.
        """
        try:
            sla        = ticket.sla
            multiplier = self.get_sla_multiplier(ticket.user)

            if multiplier == 1.0:
                return False  # No adjustment needed

            now = timezone.now()
            # Recalculate deadlines
            fr_hours  = (sla.first_response_due - now).total_seconds() / 3600
            res_hours = (sla.resolution_due - now).total_seconds() / 3600

            sla.first_response_due = now + timedelta(hours=fr_hours * multiplier)
            sla.resolution_due     = now + timedelta(hours=res_hours * multiplier)
            sla.save(update_fields=["first_response_due", "resolution_due"])

            logger.info(
                f"SLA adjusted for {ticket.ticket_id} by {multiplier}x "
                f"(plan: {self.get_subscription_info(ticket.user)['plan_name']})"
            )
            return True
        except Exception as e:
            logger.debug(f"SubscriptionSLAAdapter.adjust_sla_for_subscription: {e}")
            return False

    def get_queue_priority(self, user) -> int:
        """Get chat/ticket queue priority (lower = higher priority)."""
        info = self.get_subscription_info(user)
        plan_name = info.get("plan_name", "free").lower()
        multiplier = self.get_sla_multiplier(user)
        # Convert multiplier to priority: 0.25 → 1 (top), 1.5 → 10 (low)
        return max(1, int(multiplier * 5))


subscription_sla = SubscriptionSLAAdapter()