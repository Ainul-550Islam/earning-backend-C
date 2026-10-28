# api/support/integrations/project_specific/auto_mod_adapter.py
"""
Auto Moderation Adapter — uses YOUR auto_mod app for dispute automation.

YOUR auto_mod has:
  - AutoApprovalRule — configurable rules for automatic decisions
  - SuspiciousSubmission — AI-flagged suspicious content
  - ProofScanner — scans proof images/documents
  - TaskBot — autonomous processor for pending submissions

This adapter uses auto_mod to:
  1. Auto-approve simple offer disputes using configurable rules
  2. Flag suspicious dispute submissions
  3. Scan proof images via ProofScanner
  4. Queue complex disputes to TaskBot
"""
import logging
from decimal import Decimal
from typing import Optional
logger = logging.getLogger(__name__)


class AutoModAdapter:
    """Integrates support dispute system with auto_mod app."""

    def evaluate_dispute_rules(self, dispute, user_context: dict = None) -> dict:
        """
        Check if dispute matches any AutoApprovalRule for auto-resolution.
        
        Returns: {auto_approve: bool, rule_name: str, confidence: float, action: str}
        """
        try:
            from django.apps import apps
            AutoApprovalRule = apps.get_model("auto_mod", "AutoApprovalRule")

            # Get active rules applicable to offer disputes
            rules = AutoApprovalRule.objects.filter(
                is_active=True,
            ).order_by("priority")

            for rule in rules:
                result = self._evaluate_single_rule(rule, dispute, user_context or {})
                if result["matches"]:
                    return {
                        "auto_approve": result.get("action") == "approve",
                        "auto_reject":  result.get("action") == "reject",
                        "rule_name":    rule.name if hasattr(rule, "name") else str(rule.id),
                        "confidence":   result.get("confidence", 0.8),
                        "action":       result.get("action", "manual_review"),
                        "reason":       result.get("reason", ""),
                    }

            return {"auto_approve": False, "auto_reject": False, "action": "manual_review"}

        except Exception as e:
            logger.debug(f"AutoModAdapter.evaluate_dispute_rules: {e}")
            return {"auto_approve": False, "auto_reject": False, "action": "manual_review"}

    def _evaluate_single_rule(self, rule, dispute, context: dict) -> dict:
        """Evaluate a single auto_mod rule against a dispute."""
        try:
            # Use rule's built-in evaluation if available
            if hasattr(rule, "evaluate"):
                return rule.evaluate({
                    "amount":          float(dispute.expected_amount),
                    "offer_id":        dispute.offer_id,
                    "user_id":         dispute.user_id,
                    "fraud_score":     context.get("fraud_score", 0),
                    "kyc_verified":    context.get("kyc_verified", False),
                    "account_age_days":context.get("account_age_days", 0),
                })

            # Basic fallback evaluation
            amount = float(dispute.expected_amount or 0)
            fraud  = context.get("fraud_score", 0)

            # Simple rules
            if amount <= 10 and fraud < 30:
                return {"matches": True, "action": "approve", "confidence": 0.9, "reason": "Low-value, low-risk"}
            if fraud >= 90:
                return {"matches": True, "action": "reject", "confidence": 0.95, "reason": "High fraud risk"}
            return {"matches": False}

        except Exception as e:
            logger.debug(f"_evaluate_single_rule: {e}")
            return {"matches": False}

    def flag_suspicious_dispute(self, dispute, reason: str, evidence: dict = None) -> Optional[object]:
        """
        Create SuspiciousSubmission record for a flagged dispute.
        """
        try:
            from django.apps import apps
            SuspiciousSubmission = apps.get_model("auto_mod", "SuspiciousSubmission")

            submission = SuspiciousSubmission.objects.create(
                user           = dispute.user,
                submission_type= "offer_dispute",
                content        = f"Offer: {dispute.offer_id} Amount: {dispute.expected_amount}",
                flag_reason    = reason,
                evidence       = evidence or {},
                status         = "pending_review",
            )
            logger.warning(f"Dispute {dispute.id} flagged as suspicious: {reason}")
            return submission

        except Exception as e:
            logger.debug(f"AutoModAdapter.flag_suspicious_dispute: {e}")
            return None

    def scan_proof_image(self, image_file, dispute) -> dict:
        """
        Use ProofScanner to validate dispute proof images.
        Checks for: screenshot validity, manipulation, relevance.
        """
        try:
            from django.apps import apps
            ProofScanner = apps.get_model("auto_mod", "ProofScanner")

            scanner = ProofScanner.objects.create(
                scan_type  = "image",
                entity_id  = dispute.id,
                entity_type= "offer_dispute",
                status     = "pending",
            )

            # Trigger scan (uses CV engine internally)
            if hasattr(scanner, "run_scan"):
                result = scanner.run_scan(image_file)
                return {
                    "valid":       result.get("is_valid", False),
                    "confidence":  result.get("confidence", 0.0),
                    "scan_id":     scanner.id,
                    "findings":    result.get("findings", []),
                }

            return {"valid": False, "confidence": 0.0, "scan_id": scanner.id}

        except Exception as e:
            logger.debug(f"AutoModAdapter.scan_proof_image: {e}")
            return {"valid": False, "confidence": 0.0, "scan_id": None}

    def queue_to_taskbot(self, dispute) -> bool:
        """
        Queue a complex dispute to TaskBot for autonomous processing.
        TaskBot runs in background and processes pending submissions.
        """
        try:
            from django.apps import apps
            TaskBot = apps.get_model("auto_mod", "TaskBot")

            bot = TaskBot.objects.filter(
                status__in=["active", "idle"],
            ).first()

            if bot and hasattr(bot, "queue_task"):
                bot.queue_task({
                    "task_type":   "dispute_review",
                    "dispute_id":  dispute.id,
                    "offer_id":    dispute.offer_id,
                    "amount":      str(dispute.expected_amount),
                    "user_id":     dispute.user_id,
                })
                logger.info(f"Dispute {dispute.id} queued to TaskBot")
                return True
            return False

        except Exception as e:
            logger.debug(f"AutoModAdapter.queue_to_taskbot: {e}")
            return False

    def get_moderation_history(self, user) -> list:
        """Get auto_mod history for a user — useful for dispute context."""
        try:
            from django.apps import apps
            SuspiciousSubmission = apps.get_model("auto_mod", "SuspiciousSubmission")

            records = SuspiciousSubmission.objects.filter(user=user).order_by("-created_at")[:10]
            return [{
                "type":       getattr(r, "submission_type", ""),
                "reason":     getattr(r, "flag_reason", ""),
                "status":     getattr(r, "status", ""),
                "created_at": r.created_at.isoformat() if hasattr(r, "created_at") else "",
            } for r in records]
        except Exception:
            return []


auto_mod_adapter = AutoModAdapter()