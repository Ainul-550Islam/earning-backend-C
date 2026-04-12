"""USER_MONETIZATION/paywall_manager.py — Subscription paywall logic."""
from ..models import UserSubscription


class PaywallManager:
    """Controls content gating behind subscription paywall."""

    @classmethod
    def is_subscribed(cls, user) -> bool:
        return UserSubscription.objects.filter(
            user=user, status__in=["trial", "active"]
        ).exists()

    @classmethod
    def has_feature(cls, user, feature: str) -> bool:
        from ..REVENUE_MODELS.premium_features import PremiumFeatureManager
        return PremiumFeatureManager.has_feature(user, feature)

    @classmethod
    def get_paywall_config(cls, user, tenant=None) -> dict:
        subscribed = cls.is_subscribed(user)
        plans      = list(
            __import__("..models", fromlist=["SubscriptionPlan"])
              .SubscriptionPlan.objects.filter(is_active=True)
              .order_by("sort_order", "price")
              .values("id", "name", "slug", "price", "currency", "interval", "features")
        )
        return {"subscribed": subscribed, "plans": plans}
