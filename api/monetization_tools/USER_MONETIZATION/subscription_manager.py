"""USER_MONETIZATION/subscription_manager.py — Subscription lifecycle."""
from ..services import SubscriptionService


class SubscriptionManager:
    @classmethod
    def subscribe(cls, user, plan_id: int, gateway: str = "bkash",
                   trial_days: int = 0):
        return SubscriptionService.create_subscription(user, plan_id, gateway, trial_days)

    @classmethod
    def cancel(cls, user):
        return SubscriptionService.cancel_subscription(user)

    @classmethod
    def renew(cls, subscription_id: int):
        return SubscriptionService.renew(subscription_id)

    @classmethod
    def active_for_user(cls, user):
        return SubscriptionService.get_active_subscription(user)

    @classmethod
    def upgrade(cls, user, new_plan_id: int):
        return SubscriptionService.upgrade_plan(user, new_plan_id)
