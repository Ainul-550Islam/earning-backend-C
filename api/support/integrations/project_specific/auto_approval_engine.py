# api/support/integrations/project_specific/auto_approval_engine.py
"""
Auto Approval Engine — orchestrates dispute auto-approval using multiple signals.

Combines:
  - auto_mod.AutoApprovalRule (your configurable rules)
  - ai_engine fraud predictor
  - postback verification
  - behavior analysis
  - subscription tier

This is the main decision engine for "should we auto-approve this dispute?"
"""
import logging
from decimal import Decimal
logger = logging.getLogger(__name__)


class DisputeAutoApprovalEngine:
    """
    Multi-signal dispute auto-approval decision engine.
    
    Decision factors:
      1. auto_mod rules (highest weight)
      2. Postback verification confidence
      3. User fraud risk score
      4. Dispute history / behavior
      5. Amount threshold
      6. Subscription tier
    """

    # Weights for each signal (must sum to 1.0)
    WEIGHTS = {
        "postback_confidence": 0.35,
        "auto_mod_rules":      0.25,
        "fraud_risk":          0.20,
        "behavior":            0.10,
        "subscription":        0.05,
        "amount":              0.05,
    }

    AUTO_APPROVE_THRESHOLD = 0.75  # 75% score → auto-approve
    AUTO_REJECT_THRESHOLD  = 0.20  # 20% score → auto-reject

    def evaluate(self, dispute, request=None) -> dict:
        """
        Full auto-approval evaluation for a dispute.
        
        Returns:
            {
              decision: "auto_approve" | "auto_reject" | "manual_review",
              score: float (0-1),
              confidence: float,
              factors: dict,
              reason: str,
            }
        """
        scores = {}
        details = {}

        # ── Factor 1: Postback Verification (35%) ────────────
        try:
            from api.support.integrations.integ_adapter import postback_adapter
            pb = postback_adapter.verify_offer_completion(
                dispute.user, dispute.offer_id, dispute.click_id
            )
            scores["postback_confidence"] = pb.get("confidence", 0.1)
            details["postback"] = pb.get("status", "unknown")
        except Exception:
            scores["postback_confidence"] = 0.1
            details["postback"] = "unavailable"

        # ── Factor 2: auto_mod Rules (25%) ───────────────────
        try:
            from api.support.integrations.project_specific.auto_mod_adapter import auto_mod_adapter
            context = {
                "fraud_score": scores.get("fraud_risk_raw", 0),
                "kyc_verified": self._get_kyc_status(dispute.user),
            }
            rule_result = auto_mod_adapter.evaluate_dispute_rules(dispute, context)
            if rule_result.get("auto_approve"):
                scores["auto_mod_rules"] = 0.95
            elif rule_result.get("auto_reject"):
                scores["auto_mod_rules"] = 0.05
            else:
                scores["auto_mod_rules"] = 0.5
            details["auto_mod"] = rule_result.get("action", "manual")
        except Exception:
            scores["auto_mod_rules"] = 0.5
            details["auto_mod"] = "unavailable"

        # ── Factor 3: Fraud Risk (20%) ────────────────────────
        try:
            from api.support.integrations.integ_adapter import fraud_adapter
            risk = fraud_adapter.get_risk_score(dispute.user)
            fraud_score = risk.get("score", 0)
            scores["fraud_risk_raw"] = fraud_score
            # Convert: low fraud (0) = high score, high fraud (100) = low score
            scores["fraud_risk"] = max(0.0, 1.0 - (fraud_score / 100))
            details["fraud_risk"] = f"score:{fraud_score}"
        except Exception:
            scores["fraud_risk"] = 0.5
            details["fraud_risk"] = "unavailable"

        # ── Factor 4: Behavior (10%) ──────────────────────────
        try:
            from api.support.integrations.project_specific.behavior_tracker import behavior_tracker
            behavior = behavior_tracker.detect_abnormal_dispute_pattern(dispute.user)
            risk_map = {"low": 0.9, "medium": 0.5, "high": 0.1}
            scores["behavior"] = risk_map.get(behavior.get("risk", "low"), 0.5)
            details["behavior"] = behavior.get("risk", "low")
        except Exception:
            scores["behavior"] = 0.7
            details["behavior"] = "unavailable"

        # ── Factor 5: Subscription (5%) ───────────────────────
        try:
            from api.support.integrations.project_specific.subscription_sla import subscription_sla
            mult = subscription_sla.get_sla_multiplier(dispute.user)
            # Premium (0.25x) → high score, Free (1.5x) → low score
            scores["subscription"] = max(0.0, min(1.0, 1.5 - mult))
            details["subscription"] = subscription_sla.get_subscription_info(dispute.user).get("plan_name", "free")
        except Exception:
            scores["subscription"] = 0.5
            details["subscription"] = "unavailable"

        # ── Factor 6: Amount (5%) ─────────────────────────────
        amount = float(dispute.expected_amount or 0)
        if amount <= 10:
            scores["amount"] = 0.95
        elif amount <= 50:
            scores["amount"] = 0.75
        elif amount <= 200:
            scores["amount"] = 0.5
        else:
            scores["amount"] = 0.2  # Large amounts need manual review
        details["amount"] = amount

        # ── Compute weighted score ────────────────────────────
        final_score = sum(
            scores.get(factor, 0.5) * weight
            for factor, weight in self.WEIGHTS.items()
        )
        final_score = round(final_score, 3)

        # ── Decision ──────────────────────────────────────────
        if final_score >= self.AUTO_APPROVE_THRESHOLD:
            decision = "auto_approve"
            reason   = f"High confidence ({final_score:.0%}): postback={details['postback']}, fraud_risk={details['fraud_risk']}"
        elif final_score <= self.AUTO_REJECT_THRESHOLD:
            decision = "auto_reject"
            reason   = f"Low confidence ({final_score:.0%}): Risk signals detected"
        else:
            decision = "manual_review"
            reason   = f"Confidence {final_score:.0%} — manual agent review required"

        return {
            "decision":   decision,
            "score":      final_score,
            "confidence": min(0.99, abs(final_score - 0.5) * 2),
            "factors":    scores,
            "details":    details,
            "reason":     reason,
        }

    def _get_kyc_status(self, user) -> bool:
        try:
            from api.support.integrations.integ_adapter import kyc_adapter
            return kyc_adapter.is_verified(user)
        except Exception:
            return False


auto_approval_engine = DisputeAutoApprovalEngine()