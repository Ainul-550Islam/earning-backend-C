"""
api/gamification/integrations/referral_adapter.py

Referral ↔ Gamification adapter।

api.referral.ReferralContest ↔ api.gamification.ContestCycle sync করে।

Wire-up (api/referral/apps.py ready() তে):
    from api.gamification.integrations.referral_adapter import ReferralGamificationAdapter
    ReferralGamificationAdapter().connect_signals()
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

# Referral milestone thresholds → achievement points
REFERRAL_MILESTONES = {
    1:   {"title": "First Referral",    "points": 30},
    5:   {"title": "Referral Pro",      "points": 50},
    10:  {"title": "Referral Expert",   "points": 100},
    25:  {"title": "Referral Master",   "points": 200},
    50:  {"title": "Referral Legend",   "points": 500},
}

COMMISSION_MILESTONES = {
    100:   {"title": "Commission Starter",  "points": 20},
    500:   {"title": "Commission Expert",   "points": 50},
    1000:  {"title": "Commission Pro",      "points": 100},
    5000:  {"title": "Commission Master",   "points": 250},
}


class ReferralGamificationAdapter:
    """Referral events থেকে gamification actions trigger করে।"""

    def on_contest_started(self, referral_contest: Any) -> None:
        """
        ReferralContest start হলে gamification ContestCycle তৈরি করো।

        api.referral.ReferralContest → api.gamification.ContestCycle (DRAFT)

        Args:
            referral_contest: api.referral.models.ReferralContest instance
        """
        try:
            from api.gamification.services import create_contest_cycle
            from api.gamification.choices import ContestCycleStatus

            title      = getattr(referral_contest, "title", "Referral Contest")
            start_date = getattr(referral_contest, "start_date", None)
            end_date   = getattr(referral_contest, "end_date", None)
            prize_pool = float(getattr(referral_contest, "prize_pool", 0))

            if not (start_date and end_date):
                logger.warning(
                    "[ReferralAdapter] on_contest_started: missing dates for contest=%s",
                    getattr(referral_contest, "id", "?")
                )
                return

            # Slug: referral_contest_{id}
            slug = f"referral-contest-{getattr(referral_contest, 'id', 'unknown')}"

            cycle = create_contest_cycle(
                name=f"[Referral] {title}",
                slug=slug,
                start_date=start_date,
                end_date=end_date,
                description=(
                    f"Referral Contest: {title}. "
                    f"Prize pool: ৳{prize_pool}"
                ),
                metadata={
                    "source":               "referral",
                    "referral_contest_id":  str(getattr(referral_contest, "id", "")),
                    "prize_pool":           prize_pool,
                    "contest_type":         str(getattr(referral_contest, "contest_type", "")),
                },
            )

            # Store the gamification cycle ID back on the referral contest
            try:
                referral_contest.gamification_cycle_id = str(cycle.id)
                referral_contest.save(update_fields=["gamification_cycle_id"])
            except Exception:
                pass  # field may not exist — skip

            logger.info(
                "[ReferralAdapter] ContestCycle %s created for ReferralContest %s",
                cycle.id, getattr(referral_contest, "id", "?")
            )
        except Exception as exc:
            logger.error("[ReferralAdapter] on_contest_started failed: %s", exc)

    def on_commission_earned(
        self,
        user: Any,
        amount: float,
        referral_count: int,
        **kwargs,
    ) -> None:
        """
        Referral commission earn হলে achievement check করো।

        1. referral_count milestone চেক করো
        2. total commission milestone চেক করো
        """
        try:
            # Referral count milestones
            for threshold, config in sorted(REFERRAL_MILESTONES.items()):
                if referral_count == threshold:
                    self._award(
                        user=user,
                        title=config["title"],
                        description=f"{threshold}টি সফল referral সম্পন্ন!",
                        points=config["points"],
                        metadata={
                            "milestone_type":  "referral_count",
                            "referral_count":  referral_count,
                        },
                    )

            # Commission amount milestones
            total_commission = self._get_total_commission(user)
            new_total = total_commission + Decimal(str(amount))

            for threshold, config in sorted(COMMISSION_MILESTONES.items()):
                if total_commission < threshold <= new_total:
                    self._award(
                        user=user,
                        title=config["title"],
                        description=f"Referral commission ৳{threshold} ছাড়িয়েছেন!",
                        points=config["points"],
                        metadata={
                            "milestone_type": "commission_earned",
                            "threshold":      threshold,
                            "total":          float(new_total),
                        },
                    )

            self._track(user, "referral_commission_earned", {
                "amount":          amount,
                "referral_count":  referral_count,
            })
        except Exception as exc:
            logger.error("[ReferralAdapter] on_commission_earned failed: %s", exc)

    def connect_signals(self) -> None:
        """
        api.referral signals → gamification adapter connect করো।
        api/referral/apps.py ready()-তে call করো।

        Example:
            class ReferralConfig(AppConfig):
                def ready(self):
                    from api.gamification.integrations.referral_adapter import (
                        ReferralGamificationAdapter
                    )
                    ReferralGamificationAdapter().connect_signals()
        """
        try:
            from django.db.models.signals import post_save

            adapter = self

            @post_save.connect
            def _on_contest_save(sender, instance, created, **kwargs):
                if sender.__name__ == "ReferralContest" and created:
                    adapter.on_contest_started(instance)

            @post_save.connect
            def _on_commission_credited(sender, instance, created, **kwargs):
                if sender.__name__ in ("ReferralCommission", "CommissionTransaction") and created:
                    user   = getattr(instance, "user", None) or getattr(instance, "referrer", None)
                    amount = float(getattr(instance, "amount", 0))
                    if user:
                        count = self._get_referral_count(user)
                        adapter.on_commission_earned(
                            user=user, amount=amount, referral_count=count
                        )

            logger.info("[ReferralAdapter] Signals connected.")
        except Exception as exc:
            logger.error("[ReferralAdapter] connect_signals failed: %s", exc)

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
            logger.debug("[ReferralAdapter] _award skipped: %s", exc)

    def _get_total_commission(self, user: Any) -> Decimal:
        try:
            from django.apps import apps
            from django.db.models import Sum
            for model_name in ("ReferralCommission", "CommissionTransaction"):
                try:
                    M = apps.get_model("referral", model_name)
                    result = M.objects.filter(
                        **{"referrer": user} if hasattr(M, "referrer") else {"user": user}
                    ).aggregate(total=Sum("amount"))
                    return Decimal(str(result.get("total") or 0))
                except (LookupError, Exception):
                    continue
        except Exception:
            pass
        return Decimal("0")

    def _get_referral_count(self, user: Any) -> int:
        try:
            from django.apps import apps
            for model_name in ("Referral", "ReferralEntry", "ContestEntry"):
                try:
                    M = apps.get_model("referral", model_name)
                    field = "referrer" if hasattr(M, "referrer") else "user"
                    return M.objects.filter(**{field: user}).count()
                except (LookupError, Exception):
                    continue
        except Exception:
            pass
        return 0

    def _track(self, user: Any, event: str, properties: dict) -> None:
        try:
            from api.gamification.integrations.adapter import gamification_adapter
            gamification_adapter.track_event(event, user=user, properties=properties)
        except Exception:
            pass
