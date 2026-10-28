"""
api/gamification/integrations/kyc_adapter.py

KYC ↔ Gamification adapter।

KYC verified/rejected/expired events → achievement/penalty।

Wire-up (api/kyc/apps.py ready() তে):
    from api.gamification.integrations.kyc_adapter import KYCGamificationAdapter
    KYCGamificationAdapter().connect_signals()
"""
from __future__ import annotations
import logging
from typing import Any
logger = logging.getLogger(__name__)

KYC_ACHIEVEMENT_MAP = {
    "verified": {
        "title":       "Identity Verified",
        "description": "KYC সফলভাবে যাচাই হয়েছে — আপনি trusted user!",
        "points":      75,
        "badge":       "kyc_verified",
    },
    "re_verified": {
        "title":       "Re-Verified",
        "description": "KYC পুনরায় যাচাই সম্পন্ন।",
        "points":      25,
        "badge":       "kyc_re_verified",
    },
}


class KYCGamificationAdapter:

    def on_kyc_verified(self, user: Any, kyc: Any = None) -> None:
        """KYC approved → KYC Verified badge + 75 points।"""
        try:
            cfg = KYC_ACHIEVEMENT_MAP["verified"]
            self._award(user, cfg["title"], cfg["description"], cfg["points"],
                        {"badge": cfg["badge"], "kyc_id": str(getattr(kyc, "id", ""))})
            self._track(user, "kyc_verified", {"kyc_id": str(getattr(kyc, "id", ""))})
        except Exception as exc:
            logger.error("[KYCAdapter] on_kyc_verified failed: %s", exc)

    def on_kyc_rejected(self, user: Any, kyc: Any = None, reason: str = "") -> None:
        """KYC rejected — shudhu log, kono penalty নেই।"""
        try:
            self._track(user, "kyc_rejected", {
                "kyc_id": str(getattr(kyc, "id", "")),
                "reason": reason[:200],
            })
        except Exception as exc:
            logger.error("[KYCAdapter] on_kyc_rejected failed: %s", exc)

    def on_kyc_expired(self, user: Any, kyc: Any = None) -> None:
        """KYC expired — achievements freeze করো।"""
        try:
            self._track(user, "kyc_expired", {"kyc_id": str(getattr(kyc, "id", ""))})
            logger.info("[KYCAdapter] KYC expired for user=%s — no new awards until re-verified.",
                        getattr(user, "id", "?"))
        except Exception as exc:
            logger.error("[KYCAdapter] on_kyc_expired failed: %s", exc)

    def connect_signals(self) -> None:
        """api/kyc/apps.py ready()-তে call করো।"""
        try:
            from django.db.models.signals import post_save
            adapter = self

            @post_save.connect
            def _on_kyc_save(sender, instance, **kwargs):
                if sender.__name__ not in ("KYC", "KYCSubmission", "KYCRecord"):
                    return
                status = getattr(instance, "status", "")
                user   = getattr(instance, "user", None)
                if not user:
                    return
                if status == "verified":
                    adapter.on_kyc_verified(user=user, kyc=instance)
                elif status == "rejected":
                    reason = getattr(instance, "rejection_reason", "") or ""
                    adapter.on_kyc_rejected(user=user, kyc=instance, reason=reason)
                elif status == "expired":
                    adapter.on_kyc_expired(user=user, kyc=instance)

            logger.info("[KYCAdapter] Signals connected.")
        except Exception as exc:
            logger.error("[KYCAdapter] connect_signals failed: %s", exc)

    def _award(self, user, title, description, points, metadata):
        from api.gamification.services import award_achievement
        from api.gamification.choices import AchievementType
        try:
            award_achievement(user_id=user.pk, achievement_type=AchievementType.BADGE,
                              title=title, description=description, points=points, metadata=metadata)
        except Exception as exc:
            logger.debug("[KYCAdapter] _award skipped: %s", exc)

    def _track(self, user, event, properties):
        try:
            from api.gamification.integrations.adapter import gamification_adapter
            gamification_adapter.track_event(event, user=user, properties=properties)
        except Exception:
            pass
