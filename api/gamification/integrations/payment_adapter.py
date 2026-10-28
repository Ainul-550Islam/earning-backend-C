"""
api/gamification/integrations/payment_adapter.py

Payment Gateway ↔ Gamification adapter।

Deposit completed / conversion approved → milestone achievement।

api.payment_gateways.integration_system.integ_adapter-এর
GamificationIntegration class এই adapter-কে delegate করে।

Wire-up (payment_gateways/apps.py already does this via IntegrationAdapter):
    registry.register(IntegEvent.DEPOSIT_COMPLETED, gi.on_deposit_completed, ...)
    registry.register(IntegEvent.CONVERSION_APPROVED, gi.on_conversion_approved, ...)
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

# Deposit amount thresholds → achievement
DEPOSIT_THRESHOLDS = {
    100:   {"title": "Depositor I",    "points": 10},
    500:   {"title": "Depositor II",   "points": 25},
    1000:  {"title": "Depositor III",  "points": 50},
    5000:  {"title": "Depositor IV",   "points": 100},
    10000: {"title": "Depositor V",    "points": 200},
}

# Conversion/payout thresholds
CONVERSION_THRESHOLDS = {
    10:   {"title": "First Earner",    "points": 15},
    50:   {"title": "Consistent Earner","points": 30},
    100:  {"title": "Power Earner",    "points": 60},
    500:  {"title": "Super Earner",    "points": 150},
}


class PaymentGamificationAdapter:
    """Payment gateway events থেকে gamification achievements trigger করে।"""

    def on_deposit_completed(
        self,
        user: Any,
        amount: float,
        deposit: Any = None,
    ) -> None:
        """
        Deposit complete হলে milestone check করো।

        Called from:
          - api.payment_gateways IntegrationAdapter._setup_gamification()
          - api.gamification.integrations.adapter.on_payment_deposit_completed()

        Triggers: MILESTONE achievement (Depositor I–V)
        """
        if not user:
            return

        try:
            amount_dec = Decimal(str(amount))

            # Find the highest threshold that the amount qualifies for
            best_threshold, best_config = None, None
            for threshold, config in sorted(DEPOSIT_THRESHOLDS.items()):
                if amount_dec >= threshold:
                    best_threshold, best_config = threshold, config

            if best_threshold:
                self._award(
                    user=user,
                    title=best_config["title"],
                    description=f"একটি deposit-এ ৳{best_threshold} বা বেশি জমা দিয়েছেন!",
                    points=best_config["points"],
                    metadata={
                        "source":     "payment_gateway",
                        "event":      "deposit_completed",
                        "amount":     float(amount),
                        "threshold":  best_threshold,
                        "deposit_id": str(getattr(deposit, "id", "")),
                    },
                )

            self._track(user, "payment_deposit_completed", {
                "amount":     float(amount),
                "deposit_id": str(getattr(deposit, "id", "")),
            })
        except Exception as exc:
            logger.error("[PaymentAdapter] on_deposit_completed failed: %s", exc)

    def on_conversion_approved(
        self,
        user: Any,
        payout: float,
        conversion: Any = None,
    ) -> None:
        """
        Offerwall/postback conversion approve হলে।

        Called from:
          - api.payment_gateways IntegrationAdapter._setup_gamification()
          - api.gamification.integrations.adapter.on_conversion_approved()

        Triggers: MILESTONE achievement (First Earner → Super Earner)
        """
        if not user:
            return

        try:
            payout_dec = Decimal(str(payout))

            best_threshold, best_config = None, None
            for threshold, config in sorted(CONVERSION_THRESHOLDS.items()):
                if payout_dec >= threshold:
                    best_threshold, best_config = threshold, config

            if best_threshold:
                self._award(
                    user=user,
                    title=best_config["title"],
                    description=f"একটি conversion-এ ৳{best_threshold}+ payout অর্জন করেছেন!",
                    points=best_config["points"],
                    metadata={
                        "source":         "payment_gateway",
                        "event":          "conversion_approved",
                        "payout":         float(payout),
                        "threshold":      best_threshold,
                        "conversion_id":  str(getattr(conversion, "id", "")),
                    },
                )

            self._track(user, "payment_conversion_approved", {
                "payout":        float(payout),
                "conversion_id": str(getattr(conversion, "id", "")),
            })
        except Exception as exc:
            logger.error("[PaymentAdapter] on_conversion_approved failed: %s", exc)

    # ── Private ────────────────────────────────────────────────────────────────

    def _award(self, user: Any, title: str, description: str,
               points: int, metadata: dict) -> None:
        from api.gamification.services import award_achievement
        from api.gamification.choices import AchievementType
        try:
            award_achievement(
                user_id=user.pk,
                achievement_type=AchievementType.MILESTONE,
                title=title,
                description=description,
                points=points,
                metadata=metadata,
            )
        except Exception as exc:
            logger.debug("[PaymentAdapter] _award skipped: %s", exc)

    def _track(self, user: Any, event: str, properties: dict) -> None:
        try:
            from api.gamification.integrations.adapter import gamification_adapter
            gamification_adapter.track_event(event, user=user, properties=properties)
        except Exception:
            pass
