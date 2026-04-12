"""REVENUE_MODELS/premium_features.py — Premium feature gating and revenue."""
from decimal import Decimal


PREMIUM_FEATURES = {
    "no_ads":           {"plan_level": "basic",   "monthly_value": Decimal("49.00")},
    "unlimited_spins":  {"plan_level": "basic",   "monthly_value": Decimal("29.00")},
    "double_rewards":   {"plan_level": "pro",     "monthly_value": Decimal("99.00")},
    "priority_payouts": {"plan_level": "pro",     "monthly_value": Decimal("49.00")},
    "custom_branding":  {"plan_level": "enterprise", "monthly_value": Decimal("499.00")},
    "api_access":       {"plan_level": "enterprise", "monthly_value": Decimal("999.00")},
}


class PremiumFeatureManager:
    """Controls access to premium features based on subscription plan."""

    @classmethod
    def has_feature(cls, user, feature: str) -> bool:
        try:
            from ..models import UserSubscription
            sub = UserSubscription.objects.filter(
                user=user, status__in=["trial", "active"]
            ).select_related("plan").first()
            if not sub or not sub.is_currently_active:
                return False
            plan_features = sub.plan.features or []
            return feature in plan_features
        except Exception:
            return False

    @classmethod
    def feature_revenue(cls, feature: str, subscribers: int) -> Decimal:
        info = PREMIUM_FEATURES.get(feature, {})
        value = info.get("monthly_value", Decimal("0"))
        return (value * subscribers).quantize(Decimal("0.01"))

    @classmethod
    def all_features_for_plan(cls, plan_slug: str) -> list:
        from ..models import SubscriptionPlan
        plan = SubscriptionPlan.objects.filter(slug=plan_slug).first()
        return plan.features if plan else []
