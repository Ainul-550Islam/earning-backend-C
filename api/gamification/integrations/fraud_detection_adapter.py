"""
api/gamification/integrations/fraud_detection_adapter.py

FraudDetection ↔ Gamification protection adapter।

High fraud score / auto-ban → achievements pause + reverse suspect awards।
Fraud cleared → resume।

Wire-up (api/fraud_detection/services/AutoBanService.py তে):
    from api.gamification.integrations.fraud_detection_adapter import FraudDetectionGamificationAdapter
    FraudDetectionGamificationAdapter().on_user_banned(user=user, score=score, reason=reason)
"""
from __future__ import annotations
import logging
from typing import Any
logger = logging.getLogger(__name__)

HIGH_FRAUD_SCORE_THRESHOLD = 80  # AutoBanService-এর auto_suspend_threshold


class FraudDetectionGamificationAdapter:

    def on_high_fraud_score(self, user: Any, score: float,
                            signals: list = None) -> None:
        """
        Fraud score >= threshold হলে — user-এর pending achievements block করো।
        """
        if not user:
            return
        try:
            if score >= HIGH_FRAUD_SCORE_THRESHOLD:
                self._pause_user_achievements(
                    user, reason=f"fraud_score:{score:.0f}",
                    score=score, signals=signals or []
                )
                self._track(user, "fraud_achievement_paused", {
                    "score": score, "threshold": HIGH_FRAUD_SCORE_THRESHOLD
                })
                logger.warning("[FraudAdapter] Achievements paused for user=%s (score=%.1f)",
                               getattr(user, "id", "?"), score)
        except Exception as exc:
            logger.error("[FraudAdapter] on_high_fraud_score failed: %s", exc)

    def on_user_auto_banned(self, user: Any, ban_type: str = "auto_ban",
                            score: float = 0) -> None:
        """
        AutoBanService ban/suspend করলে — সব pending + recent awards reverse করো।
        """
        if not user:
            return
        try:
            self._pause_user_achievements(
                user, reason=f"auto_ban:{ban_type}", score=score
            )
            self._revoke_recent_suspicious_awards(user)
            self._track(user, "fraud_user_banned", {
                "ban_type": ban_type, "score": score
            })
            logger.error("[FraudAdapter] Achievements revoked for auto-banned user=%s",
                         getattr(user, "id", "?"))
        except Exception as exc:
            logger.error("[FraudAdapter] on_user_auto_banned failed: %s", exc)

    def on_fraud_cleared(self, user: Any) -> None:
        """Fraud flag cleared → resume achievements।"""
        if not user:
            return
        try:
            from api.gamification.models import UserAchievement
            paused = UserAchievement.objects.filter(
                user=user, is_awarded=False, metadata__fraud_paused=True
            )
            for ach in paused:
                meta = ach.metadata or {}
                meta.pop("fraud_paused", None)
                meta.pop("fraud_reason", None)
                ach.metadata = meta
                ach.save(update_fields=["metadata"])
            self._track(user, "fraud_achievement_resumed", {"count": paused.count()})
            logger.info("[FraudAdapter] Achievements resumed for user=%s",
                        getattr(user, "id", "?"))
        except Exception as exc:
            logger.error("[FraudAdapter] on_fraud_cleared failed: %s", exc)

    def is_user_fraud_flagged(self, user: Any) -> bool:
        """
        award_achievement guard — fraud-flagged user-দের award করা যাবে না।
        """
        try:
            from django.apps import apps
            M = apps.get_model("fraud_detection", "FraudFlag")
            return M.objects.filter(user=user, is_active=True).exists()
        except (LookupError, ImportError):
            return False
        except Exception:
            return False

    def _pause_user_achievements(self, user: Any, reason: str, **meta) -> None:
        try:
            from api.gamification.models import UserAchievement
            UserAchievement.objects.filter(
                user=user, is_awarded=False
            ).update(metadata={"fraud_paused": True, "fraud_reason": reason, **meta})
        except Exception as exc:
            logger.error("[FraudAdapter] _pause_user_achievements failed: %s", exc)

    def _revoke_recent_suspicious_awards(self, user: Any,
                                         lookback_hours: int = 24) -> None:
        """Last 24h-এর suspicious achievements revoke করো।"""
        try:
            from django.utils import timezone
            from datetime import timedelta
            from api.gamification.models import UserAchievement
            cutoff = timezone.now() - timedelta(hours=lookback_hours)
            suspicious = UserAchievement.objects.filter(
                user=user, is_awarded=True, awarded_at__gte=cutoff
            )
            count = suspicious.count()
            if count:
                suspicious.update(
                    is_awarded=False, awarded_at=None,
                    metadata={"revoked": True, "revoke_reason": "fraud_detection"}
                )
                logger.warning("[FraudAdapter] Revoked %d recent awards for user=%s",
                               count, getattr(user, "id", "?"))
        except Exception as exc:
            logger.error("[FraudAdapter] _revoke_recent_suspicious_awards failed: %s", exc)

    def _track(self, user, event, properties):
        try:
            from api.gamification.integrations.adapter import gamification_adapter
            gamification_adapter.track_event(event, user=user, properties=properties)
        except Exception:
            pass
