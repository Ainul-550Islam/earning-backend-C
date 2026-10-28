# engagement/services/adapters/fraud_detection_adapter.py
"""
FraudDetectionAdapter
=====================
Wraps api.fraud_detection for engagement.

Called after every significant action:
    - checkin, spin, quest complete, achievement claim
    - shop purchase, auction bid/win
    - referral registration
    - scratch card, loot box open

Decisions:
    score 0-59   → allow, log only
    score 60-69  → flag for review
    score 70-79  → restrict (no withdrawal/referral)
    score 80-89  → suspend account
    score 90-100 → auto-ban

Engagement side-effects after ban/suspend:
    - Block spin/checkin via AntiCheatService
    - Fire ANTI_CHEAT_FLAG event
    - Notify user via NotificationBridge
"""

import logging
from decimal import Decimal
from typing import Optional

logger = logging.getLogger("engagement.adapters.fraud_detection")

# ── Risk level thresholds ─────────────────────────────────────────────────────
RISK_LEVELS = {
    "clean":    (0,  59),
    "flag":     (60, 69),
    "restrict": (70, 79),
    "suspend":  (80, 89),
    "ban":      (90, 100),
}


def _risk_level(score: int) -> str:
    for level, (lo, hi) in RISK_LEVELS.items():
        if lo <= score <= hi:
            return level
    return "clean"


class FraudDetectionAdapter:
    """
    Engagement → api.fraud_detection adapter.
    Never import FraudScoreCalculator / AutoBanService directly in engagement.
    """

    @staticmethod
    def score_user(user, action: str = "engagement", ip: str = None,
                   metadata: dict = None) -> dict:
        """
        Calculate fraud risk score for a user.

        Returns:
            {
                "score": int,          # 0-100
                "level": str,          # clean|flag|restrict|suspend|ban
                "should_block": bool,  # True if score >= 70
                "breakdown": dict,     # detailed factors (if available)
                "source": str,         # "fraud_app" | "engagement_anti_cheat"
            }
        """
        # ── Try api.fraud_detection ───────────────────────────────────────────
        try:
            from api.fraud_detection.services.FraudScoreCalculator import FraudScoreCalculator
            calc = FraudScoreCalculator(user)
            score = calc.calculate_overall_risk()
            breakdown = {}
            try:
                breakdown = calc.calculate_risk_breakdown().get("breakdown", {})
            except Exception:
                pass
            level = _risk_level(score)
            logger.info(
                f"FraudDetectionAdapter.score_user user={user.pk} "
                f"action={action} score={score} level={level}"
            )
            return {
                "score": score,
                "level": level,
                "should_block": score >= 70,
                "breakdown": breakdown,
                "source": "fraud_app",
            }
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"FraudDetectionAdapter.score_user fraud_app error user={user.pk}: {e}")

        # ── Fallback: engagement AntiCheatService ─────────────────────────────
        try:
            from api.engagement.services.anti_cheat_service import AntiCheatService
            from api.engagement.models.anti_cheat import UserRiskScore
            risk = UserRiskScore.objects.filter(user=user).first()
            score = int(risk.score) if risk else 0
            return {
                "score": score,
                "level": _risk_level(score),
                "should_block": score >= 70,
                "breakdown": {},
                "source": "engagement_anti_cheat",
            }
        except Exception:
            return {"score": 0, "level": "clean", "should_block": False,
                    "breakdown": {}, "source": "unavailable"}

    @staticmethod
    def score_and_act(user, action: str, ip: str = None,
                      metadata: dict = None) -> dict:
        """
        Score the user AND take automatic action if score is high.

        Flow:
            1. Calculate score
            2. If >= 60 → flag in engagement anti-cheat log
            3. If >= 70 → restrict + fire event
            4. If >= 80 → suspend via AutoBanService
            5. If >= 90 → auto-ban via AutoBanService

        Returns the score result dict + "action_taken" key.
        """
        result = FraudDetectionAdapter.score_user(user, action, ip, metadata)
        score = result["score"]
        level = result["level"]
        result["action_taken"] = "none"

        if score < 60:
            return result

        # ── Flag in engagement anti-cheat ─────────────────────────────────────
        try:
            from api.engagement.services.anti_cheat_service import AntiCheatService
            from api.engagement.services.integration.event_bus import EngagementEventBus
            AntiCheatService.recalculate_risk(user)
            EngagementEventBus.emit_anti_cheat_flag(
                user, rule_slug=f"fraud_{level}",
                severity=score // 10,
                details={"action": action, "ip": ip, "score": score}
            )
        except Exception as e:
            logger.warning(f"FraudDetectionAdapter flag engagement: {e}")

        # ── Auto-ban / suspend via api.fraud_detection ────────────────────────
        if score >= 70:
            try:
                from api.fraud_detection.services.AutoBanService import AutoBanService
                from api.fraud_detection.models import FraudAttempt, FraudRule

                # Create a synthetic FraudAttempt for AutoBanService
                rule = FraudRule.objects.filter(is_active=True).order_by("-severity").first()
                if rule:
                    attempt = FraudAttempt.objects.create(
                        user=user,
                        fraud_score=score,
                        rule=rule,
                        action_type=action,
                        ip_address=ip or "",
                        metadata=metadata or {},
                    )
                    ban_svc = AutoBanService()
                    ban_result = ban_svc.process_fraud_attempt(attempt)
                    result["action_taken"] = ban_result.get("action", "flagged")
                    result["ban_result"] = ban_result
                    logger.warning(
                        f"FraudDetectionAdapter.score_and_act ACTED user={user.pk} "
                        f"score={score} action_taken={result['action_taken']}"
                    )
            except Exception as e:
                logger.error(f"FraudDetectionAdapter AutoBanService error user={user.pk}: {e}")
                result["action_taken"] = "flag_only"

        return result

    @staticmethod
    def is_banned(user) -> bool:
        """Quick check if user is currently banned."""
        # Check engagement anti-cheat
        try:
            from api.engagement.models.anti_cheat import UserRiskScore
            risk = UserRiskScore.objects.filter(user=user).first()
            if risk and risk.score >= 90:
                return True
        except Exception:
            pass

        # Check api.fraud_detection
        try:
            from api.fraud_detection.models import UserRiskProfile
            profile = UserRiskProfile.objects.filter(user=user).first()
            if profile and profile.is_banned:
                return True
        except Exception:
            pass

        # Check user model flags
        for attr in ("is_banned", "is_blocked", "is_suspended"):
            if getattr(user, attr, False):
                return True

        return False

    @staticmethod
    def check_before_reward(user, action: str, amount: Decimal,
                             ip: str = None) -> dict:
        """
        Called BEFORE crediting coins. Blocks reward if high-risk.

        Returns:
            {"allow": bool, "score": int, "reason": str}
        """
        if FraudDetectionAdapter.is_banned(user):
            return {"allow": False, "score": 100, "reason": "user_banned"}

        result = FraudDetectionAdapter.score_user(user, action, ip)
        score = result["score"]

        if score >= 80:
            return {"allow": False, "score": score, "reason": f"fraud_score_{score}"}

        return {"allow": True, "score": score, "reason": "ok"}

    @staticmethod
    def report_suspicious_action(user, action: str, details: dict,
                                  ip: str = None, severity: int = 1) -> bool:
        """
        Manually report suspicious action from engagement code.
        Stores in api.fraud_detection.FraudAttempt if available.
        """
        try:
            from api.fraud_detection.models import FraudAttempt, FraudRule
            rule = FraudRule.objects.filter(
                action_type=action, is_active=True
            ).first()
            if rule:
                FraudAttempt.objects.create(
                    user=user,
                    rule=rule,
                    fraud_score=severity * 10,
                    action_type=action,
                    ip_address=ip or "",
                    metadata=details,
                )
                return True
        except Exception as e:
            logger.warning(f"FraudDetectionAdapter.report_suspicious: {e}")

        # Fallback: engagement anti-cheat log
        try:
            from api.engagement.models.anti_cheat import AntiCheatLog, AntiCheatRule
            rule = AntiCheatRule.objects.filter(slug__icontains=action).first()
            if rule:
                AntiCheatLog.objects.create(
                    user=user, rule=rule, severity=severity, details=details
                )
                return True
        except Exception:
            pass
        return False
