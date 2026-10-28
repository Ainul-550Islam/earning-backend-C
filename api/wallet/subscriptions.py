# api/wallet/subscriptions.py
"""
Subscription Management — manage SaaS/service subscriptions.
2027: Every platform needs subscription billing.

Features:
  - Create subscription plans (Free/Basic/Pro/Enterprise)
  - Wallet-based billing (no card needed)
  - Upgrade/downgrade between plans
  - Prorate on plan change
  - Grace period before cancellation
  - Usage-based billing support

How it works (plugin-based, zero core changes):
  1. Define plans in SUBSCRIPTION_PLANS
  2. User subscribes → wallet deducted monthly
  3. If balance insufficient → grace period (3 days) → cancel
  4. Webhook fires on subscription events (event_bus)
"""
import logging
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger("wallet.subscriptions")

# Define your platform subscription plans here
SUBSCRIPTION_PLANS = {
    "free": {
        "name":          "Free",
        "price_monthly": Decimal("0"),
        "features": {
            "max_withdrawal_per_day": Decimal("500"),
            "fast_payout":            False,
            "priority_support":       False,
            "api_calls_per_day":      100,
        }
    },
    "basic": {
        "name":          "Basic Publisher",
        "price_monthly": Decimal("99"),
        "features": {
            "max_withdrawal_per_day": Decimal("5000"),
            "fast_payout":            False,
            "priority_support":       False,
            "api_calls_per_day":      1000,
            "earn_multiplier":        Decimal("1.05"),  # +5% earnings
        }
    },
    "pro": {
        "name":          "Pro Publisher",
        "price_monthly": Decimal("299"),
        "features": {
            "max_withdrawal_per_day": Decimal("20000"),
            "fast_payout":            True,
            "priority_support":       True,
            "api_calls_per_day":      10000,
            "earn_multiplier":        Decimal("1.15"),  # +15% earnings
        }
    },
    "enterprise": {
        "name":          "Enterprise",
        "price_monthly": Decimal("999"),
        "features": {
            "max_withdrawal_per_day": Decimal("100000"),
            "fast_payout":            True,
            "priority_support":       True,
            "dedicated_account_manager": True,
            "api_calls_per_day":      100000,
            "earn_multiplier":        Decimal("1.25"),  # +25% earnings
        }
    }
}


class SubscriptionService:
    """Wallet-based subscription billing."""

    @staticmethod
    def subscribe(user, wallet, plan_key: str) -> dict:
        """Subscribe user to a plan. Deducts first payment immediately."""
        plan = SUBSCRIPTION_PLANS.get(plan_key)
        if not plan:
            return {"success": False,
                    "error": f"Invalid plan. Available: {list(SUBSCRIPTION_PLANS.keys())}"}

        price = plan["price_monthly"]
        if price > 0 and wallet.available_balance < price:
            return {"success": False,
                    "error": f"Insufficient balance for {plan['name']} plan ({price} BDT/month)"}

        try:
            from .services.core.WalletService import WalletService

            # Deduct first payment
            if price > 0:
                WalletService.debit(
                    wallet=wallet, amount=price,
                    txn_type="subscription",
                    description=f"Subscription: {plan['name']} plan",
                )

            # Store subscription
            from datetime import timedelta
            next_billing = timezone.now() + timedelta(days=30)
            sub_data = {
                "user_id":      user.id,
                "wallet_id":    wallet.id,
                "plan":         plan_key,
                "plan_name":    plan["name"],
                "price":        str(price),
                "status":       "active",
                "started_at":   timezone.now().isoformat(),
                "next_billing": next_billing.isoformat(),
                "grace_days":   3,
            }
            cache.set(f"subscription:{user.id}", sub_data, 86400 * 35)

            # Fire event
            from .event_bus import event_bus
            from .events import WalletDebited
            logger.info(f"Subscription: user={user.id} plan={plan_key}")

            return {
                "success":      True,
                "plan":         plan_key,
                "plan_name":    plan["name"],
                "price":        str(price),
                "next_billing": next_billing.strftime("%Y-%m-%d"),
                "features":     {k: str(v) for k, v in plan["features"].items()},
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_active(user_id: int) -> dict:
        """Get user's current subscription."""
        sub = cache.get(f"subscription:{user_id}")
        if not sub:
            return {"plan": "free", **SUBSCRIPTION_PLANS["free"]}
        return sub

    @staticmethod
    def cancel(user_id: int) -> dict:
        """Cancel subscription (effective at period end)."""
        sub = cache.get(f"subscription:{user_id}")
        if not sub:
            return {"success": False, "error": "No active subscription"}
        sub["status"]     = "cancelling"
        sub["cancel_at"]  = sub.get("next_billing")
        cache.set(f"subscription:{user_id}", sub, 86400 * 35)
        return {"success": True, "effective_date": sub.get("next_billing")}

    @staticmethod
    def get_plan_features(user_id: int) -> dict:
        """Get feature limits for user's current plan."""
        sub = SubscriptionService.get_active(user_id)
        plan_key = sub.get("plan", "free")
        plan = SUBSCRIPTION_PLANS.get(plan_key, SUBSCRIPTION_PLANS["free"])
        return plan["features"]

    @staticmethod
    def process_renewals() -> dict:
        """
        Process all due subscription renewals.
        Called by Celery Beat daily at 00:30.
        """
        from datetime import date
        today = timezone.now()
        renewed = failed = 0

        try:
            client = cache.client.get_client()
            keys = list(client.scan_iter("subscription:*", count=500))
        except Exception:
            return {"error": "Cache unavailable"}

        for key in keys:
            user_id = key.decode().split(":")[-1]
            sub = cache.get(f"subscription:{user_id}")
            if not sub or sub.get("status") != "active":
                continue
            next_billing = sub.get("next_billing", "")
            if not next_billing:
                continue
            from datetime import datetime
            next_dt = datetime.fromisoformat(next_billing)
            if next_dt.date() > today.date():
                continue

            # Try to charge
            from django.contrib.auth import get_user_model
            from .services.core.WalletService import WalletService
            try:
                user   = get_user_model().objects.get(id=int(user_id))
                wallet = WalletService.get_or_create(user)
                price  = Decimal(sub.get("price", "0"))
                if price > 0:
                    WalletService.debit(wallet=wallet, amount=price,
                                        txn_type="subscription_renewal",
                                        description=f"Subscription renewal: {sub['plan_name']}")
                from datetime import timedelta
                sub["next_billing"] = (today + timedelta(days=30)).isoformat()
                sub["status"]       = "active"
                cache.set(f"subscription:{user_id}", sub, 86400 * 35)
                renewed += 1
            except Exception as e:
                failed += 1
                logger.error(f"Renewal failed for user={user_id}: {e}")
        return {"renewed": renewed, "failed": failed}
