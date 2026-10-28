"""
api/gamification/integrations/offerwall_adapter.py

Offerwall ↔ Gamification adapter।

Offer completion (AdGate, Tapjoy, AdGem, etc.) → milestone achievement।

Wire-up (api/offerwall/signals.py বা receivers.py-তে):
    from api.gamification.integrations.offerwall_adapter import OfferwallGamificationAdapter
    _ow = OfferwallGamificationAdapter()
"""
from __future__ import annotations
import logging
from decimal import Decimal
from typing import Any
logger = logging.getLogger(__name__)

OFFER_COUNT_MILESTONES = {
    1:   {"title": "First Offer!",        "points": 20},
    5:   {"title": "Offer Hunter",        "points": 40},
    10:  {"title": "Offer Pro",           "points": 80},
    25:  {"title": "Offer Expert",        "points": 150},
    50:  {"title": "Offer Master",        "points": 300},
    100: {"title": "Offer Legend",        "points": 700},
}

PAYOUT_THRESHOLDS = {
    50:   {"title": "Small Earner",   "points": 10},
    100:  {"title": "Solid Earner",   "points": 25},
    500:  {"title": "Big Earner",     "points": 75},
    1000: {"title": "Power Earner",   "points": 150},
}

# Network name → display name
NETWORK_NAMES = {
    "adgate":  "AdGate",
    "tapjoy":  "Tapjoy",
    "adgem":   "AdGem",
    "fyber":   "Fyber",
    "ironsrc":  "IronSource",
}


class OfferwallGamificationAdapter:

    def on_offer_completed(self, user: Any, payout: float,
                           network: str = "", offer_id: str = "") -> None:
        """
        Offer completion → count milestone + payout milestone。

        Called from: offerwall signals / OfferProcessor.process_completion()
        """
        if not user:
            return
        try:
            count = self._get_offer_count(user)
            cfg   = OFFER_COUNT_MILESTONES.get(count)
            if cfg:
                net_name = NETWORK_NAMES.get(network.lower(), network or "Offerwall")
                self._award(user, cfg["title"],
                            f"{net_name}-এ {count}টি offer সম্পন্ন করেছেন!",
                            cfg["points"],
                            {"source": "offerwall", "network": network,
                             "offer_id": offer_id, "count": count})

            # Payout threshold check
            total = self._get_total_payout(user)
            new_total = total + Decimal(str(payout))
            for threshold, tcfg in sorted(PAYOUT_THRESHOLDS.items()):
                if total < threshold <= new_total:
                    self._award(user, tcfg["title"],
                                f"Offerwall থেকে মোট ৳{threshold} earn করেছেন!",
                                tcfg["points"],
                                {"source": "offerwall", "threshold": threshold,
                                 "total_payout": float(new_total)})

            self._track(user, "offerwall_offer_completed", {
                "network": network, "payout": payout, "offer_id": offer_id,
            })
        except Exception as exc:
            logger.error("[OfferwallAdapter] on_offer_completed failed: %s", exc)

    def _get_offer_count(self, user: Any) -> int:
        try:
            from django.apps import apps
            for m in ("OfferCompletion", "CompletedOffer", "OfferwallConversion"):
                try:
                    M = apps.get_model("offerwall", m)
                    field = "user" if hasattr(M, "user") else "publisher"
                    return M.objects.filter(**{field: user}, status="approved").count()
                except (LookupError, Exception):
                    continue
        except Exception:
            pass
        return 0

    def _get_total_payout(self, user: Any) -> Decimal:
        try:
            from django.apps import apps
            from django.db.models import Sum
            for m in ("OfferCompletion", "CompletedOffer"):
                try:
                    M = apps.get_model("offerwall", m)
                    result = M.objects.filter(user=user, status="approved").aggregate(
                        total=Sum("payout"))
                    return Decimal(str(result.get("total") or 0))
                except (LookupError, Exception):
                    continue
        except Exception:
            pass
        return Decimal("0")

    def _award(self, user, title, description, points, metadata):
        from api.gamification.services import award_achievement
        from api.gamification.choices import AchievementType
        try:
            award_achievement(user_id=user.pk, achievement_type=AchievementType.MILESTONE,
                              title=title, description=description, points=points, metadata=metadata)
        except Exception as exc:
            logger.debug("[OfferwallAdapter] _award skipped: %s", exc)

    def _track(self, user, event, properties):
        try:
            from api.gamification.integrations.adapter import gamification_adapter
            gamification_adapter.track_event(event, user=user, properties=properties)
        except Exception:
            pass
