"""
api/gamification/integrations/postback_engine_adapter.py

PostbackEngine ↔ Gamification adapter।

postback_rewarded / conversion_approved / conversion_credited → milestone।

Wire-up (api/postback_engine/receivers.py-তে add করো):
    from api.gamification.integrations.postback_engine_adapter import PostbackEngineGamificationAdapter
    _pb = PostbackEngineGamificationAdapter()
    # postback_rewarded receiver-এর শেষে:
    _pb.on_postback_rewarded(raw_log=raw_log, conversion=conversion)
"""
from __future__ import annotations
import logging
from decimal import Decimal
from typing import Any
logger = logging.getLogger(__name__)

POINTS_AWARD_MILESTONES = {
    1000:   {"title": "Points Collector",   "points": 20},
    5000:   {"title": "Points Hunter",      "points": 50},
    10000:  {"title": "Points Master",      "points": 120},
    50000:  {"title": "Points Legend",      "points": 400},
}

USD_MILESTONES = {
    10:   {"title": "First $10 Earned",  "points": 25},
    50:   {"title": "First $50 Earned",  "points": 75},
    100:  {"title": "Century Earner",    "points": 150},
    500:  {"title": "Elite Earner",      "points": 400},
}


class PostbackEngineGamificationAdapter:

    def on_postback_rewarded(self, raw_log: Any = None, conversion: Any = None) -> None:
        """
        postback_rewarded signal — points/USD milestone check।
        """
        user = self._get_user(raw_log, conversion)
        if not user:
            return
        try:
            points_awarded = int(getattr(conversion, "points_awarded", 0) or 0)
            usd_awarded    = float(getattr(conversion, "usd_awarded", 0) or 0)

            self._check_points_total(user, points_awarded)
            self._check_usd_total(user, usd_awarded)

            self._track(user, "postback_rewarded", {
                "points": points_awarded,
                "usd":    usd_awarded,
                "conversion_id": str(getattr(conversion, "id", "")),
            })
        except Exception as exc:
            logger.error("[PostbackEngineAdapter] on_postback_rewarded failed: %s", exc)

    def on_conversion_credited(self, conversion: Any) -> None:
        """conversion_credited signal — wallet credited → achievement check।"""
        user = self._get_user(None, conversion)
        if not user:
            return
        try:
            self._track(user, "conversion_credited", {
                "conversion_id": str(getattr(conversion, "id", "")),
                "wallet_tx_id":  str(getattr(conversion, "wallet_tx_id", "")),
            })
        except Exception as exc:
            logger.error("[PostbackEngineAdapter] on_conversion_credited failed: %s", exc)

    def _check_points_total(self, user: Any, new_points: int) -> None:
        total = self._get_total_points_awarded(user)
        new_total = total + new_points
        for threshold, cfg in sorted(POINTS_AWARD_MILESTONES.items()):
            if total < threshold <= new_total:
                self._award(user, cfg["title"],
                            f"Postback-এ মোট {threshold:,} points earn করেছেন!",
                            cfg["points"],
                            {"source": "postback_engine", "points_threshold": threshold})

    def _check_usd_total(self, user: Any, new_usd: float) -> None:
        total = self._get_total_usd_awarded(user)
        new_total = total + Decimal(str(new_usd))
        for threshold, cfg in sorted(USD_MILESTONES.items()):
            if total < threshold <= new_total:
                self._award(user, cfg["title"],
                            f"Postback-এ মোট ${threshold} USD earn করেছেন!",
                            cfg["points"],
                            {"source": "postback_engine", "usd_threshold": threshold})

    def _get_user(self, raw_log: Any, conversion: Any) -> Any:
        for obj in (conversion, raw_log):
            user = getattr(obj, "user", None)
            if user:
                return user
            user_id = getattr(obj, "user_id", None)
            if user_id:
                try:
                    from django.contrib.auth import get_user_model
                    return get_user_model().objects.get(pk=user_id)
                except Exception:
                    pass
        return None

    def _get_total_points_awarded(self, user: Any) -> int:
        try:
            from django.apps import apps
            from django.db.models import Sum
            M = apps.get_model("postback_engine", "Conversion")
            result = M.objects.filter(user=user, status="approved").aggregate(
                total=Sum("points_awarded"))
            return int(result.get("total") or 0)
        except Exception:
            return 0

    def _get_total_usd_awarded(self, user: Any) -> Decimal:
        try:
            from django.apps import apps
            from django.db.models import Sum
            M = apps.get_model("postback_engine", "Conversion")
            result = M.objects.filter(user=user, status="approved").aggregate(
                total=Sum("usd_awarded"))
            return Decimal(str(result.get("total") or 0))
        except Exception:
            return Decimal("0")

    def _award(self, user, title, description, points, metadata):
        from api.gamification.services import award_achievement
        from api.gamification.choices import AchievementType
        try:
            award_achievement(user_id=user.pk, achievement_type=AchievementType.MILESTONE,
                              title=title, description=description, points=points, metadata=metadata)
        except Exception as exc:
            logger.debug("[PostbackEngineAdapter] _award skipped: %s", exc)

    def _track(self, user, event, properties):
        try:
            from api.gamification.integrations.adapter import gamification_adapter
            gamification_adapter.track_event(event, user=user, properties=properties)
        except Exception:
            pass
