# =============================================================================
# auto_mod/services.py
# =============================================================================
"""
Service layer — all AI moderation business logic lives here.
Views and tasks call services; services call managers/models and ML modules.

Services:
  ModerationService    — orchestrates scan → rule evaluation → decision
  RuleEngineService    — evaluates AutoApprovalRules against a submission
  SubmissionService    — CRUD helpers for SuspiciousSubmission
  BotService           — TaskBot lifecycle management
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from .choices import (
    BotStatus,
    FlagReason,
    ModerationStatus,
    RiskLevel,
    RuleAction,
    ScanType,
)
from .constants import (
    AUTO_APPROVE_THRESHOLD,
    AUTO_REJECT_THRESHOLD,
    BOT_HEARTBEAT_INTERVAL_SEC,
    CACHE_KEY_ACTIVE_RULES,
    CACHE_KEY_BOT_STATUS,
    CACHE_KEY_SCAN_RESULT,
    CACHE_TTL_RULES,
    CACHE_TTL_SCAN_RESULT,
    FLAG_AUTO_ESCALATE_SCORE,
    RISK_SCORE_HIGH,
    RISK_SCORE_LOW,
    RISK_SCORE_MEDIUM,
)
from .exceptions import (
    AIServiceUnavailableError,
    BotAlreadyRunningError,
    RuleEvaluationError,
    ScanFailedError,
    SubmissionAlreadyProcessedError,
    SubmissionNotFoundError,
)
from .models import AutoApprovalRule, ProofScanner, SuspiciousSubmission, TaskBot

User = get_user_model()
logger = logging.getLogger(__name__)


# =============================================================================
# ModerationService
# =============================================================================

class ModerationService:
    """
    Orchestrates the full moderation pipeline for a single submission.

    Pipeline:
      1. Create / fetch SuspiciousSubmission record
      2. Run ProofScanner (image + text)
      3. Aggregate scanner results → confidence + risk score
      4. Evaluate AutoApprovalRules
      5. Apply decision (approve / reject / human-review / escalate)
      6. Update submission status + cache result
    """

    @staticmethod
    @transaction.atomic
    def process_submission(
        *,
        content_type: str,
        content_id: str,
        submission_type: str,
        submitted_by=None,
        text_content: str = "",
        file_urls: list[str] | None = None,
        metadata: dict | None = None,
    ) -> SuspiciousSubmission:
        """
        Full moderation pipeline for a new submission.

        Returns the SuspiciousSubmission after the decision is applied.

        Raises:
            SubmissionAlreadyProcessedError: if this content was already processed.
            AIServiceUnavailableError: if the AI backend is unreachable.
        """
        # ----------------------------------------------------------------
        # 1. Upsert the submission record
        # ----------------------------------------------------------------
        submission, created = SuspiciousSubmission.objects.get_or_create(
            content_type=content_type,
            content_id=content_id,
            defaults={
                "submission_type": submission_type,
                "submitted_by":    submitted_by,
                "status":          ModerationStatus.SCANNING,
            },
        )

        if not created and submission.is_resolved:
            raise SubmissionAlreadyProcessedError()

        if not created:
            submission.status = ModerationStatus.SCANNING
            submission.save(update_fields=["status", "updated_at"])

        # ----------------------------------------------------------------
        # 2. Run scanners
        # ----------------------------------------------------------------
        scan_results = ScannerService.run_all_scans(
            submission=submission,
            text_content=text_content,
            file_urls=file_urls or [],
        )

        # ----------------------------------------------------------------
        # 3. Aggregate → confidence + risk
        # ----------------------------------------------------------------
        confidence, risk_score = ModerationService._aggregate_scan_results(scan_results)
        risk_level  = ModerationService._compute_risk_level(risk_score)
        flag_reason = ModerationService._determine_flag_reason(scan_results, submission_type)
        explanation = ModerationService._build_explanation(scan_results, confidence)

        submission.set_ai_result(
            confidence=confidence,
            risk_score=risk_score,
            risk_level=risk_level,
            flag_reason=flag_reason,
            explanation=explanation,
            metadata=metadata or {},
        )

        # ----------------------------------------------------------------
        # 4. Rule evaluation
        # ----------------------------------------------------------------
        matched_rule, rule_action = RuleEngineService.evaluate(
            submission=submission,
            submission_type=submission_type,
            confidence=confidence,
        )
        if matched_rule:
            submission.matched_rule = matched_rule

        # ----------------------------------------------------------------
        # 5. Apply decision
        # ----------------------------------------------------------------
        new_status = ModerationService._decide_status(
            confidence=confidence,
            risk_score=risk_score,
            rule_action=rule_action,
        )
        submission.status = new_status
        submission.save()

        # Cache result
        _safe_cache_set(
            CACHE_KEY_SCAN_RESULT.format(submission_id=submission.pk),
            {
                "status":     new_status,
                "confidence": confidence,
                "risk_score": risk_score,
                "risk_level": risk_level,
            },
            CACHE_TTL_SCAN_RESULT,
        )

        logger.info(
            "moderation.processed content_type=%s content_id=%s "
            "status=%s confidence=%.3f risk=%s",
            content_type, content_id, new_status, confidence, risk_level,
        )
        return submission

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _aggregate_scan_results(
        scan_results: list[ProofScanner],
    ) -> tuple[float, float]:
        """Average confidence and risk across all successful scanners."""
        successful = [s for s in scan_results if s.succeeded]
        if not successful:
            return 0.0, 0.5   # unknown → moderate risk

        avg_confidence = sum(s.confidence for s in successful) / len(successful)

        # Risk is inverse of confidence for a "clean" scan:
        # if scanner is 0.95 confident it's CLEAN → risk ≈ 0.05
        # if scanner is 0.95 confident it's FLAGGED → risk ≈ 0.95
        flagged = [s for s in successful if s.is_flagged]
        if flagged:
            avg_risk = sum(s.confidence for s in flagged) / len(successful)
        else:
            avg_risk = 1.0 - avg_confidence

        return round(avg_confidence, 4), round(avg_risk, 4)

    @staticmethod
    def _compute_risk_level(risk_score: float) -> str:
        if risk_score >= RISK_SCORE_HIGH:
            return RiskLevel.HIGH
        if risk_score >= RISK_SCORE_MEDIUM:
            return RiskLevel.MEDIUM
        if risk_score >= RISK_SCORE_LOW:
            return RiskLevel.LOW
        return RiskLevel.LOW

    @staticmethod
    def _determine_flag_reason(
        scan_results: list[ProofScanner],
        submission_type: str,
    ) -> str:
        """Pick the most likely flag reason from scanner labels."""
        all_labels: list[str] = []
        for scan in scan_results:
            if isinstance(scan.labels, list):
                all_labels.extend([str(l).lower() for l in scan.labels])

        if any("spam" in l for l in all_labels):
            return FlagReason.SPAM
        if any("fake" in l or "manipulated" in l for l in all_labels):
            return FlagReason.FAKE_PROOF
        if any("duplicate" in l for l in all_labels):
            return FlagReason.DUPLICATE
        if any("nsfw" in l or "adult" in l or "inappropriate" in l for l in all_labels):
            return FlagReason.INAPPROPRIATE
        if submission_type == "task_proof":
            return FlagReason.LOW_QUALITY
        return FlagReason.SUSPICIOUS_PATTERN

    @staticmethod
    def _build_explanation(
        scan_results: list[ProofScanner],
        confidence: float,
    ) -> str:
        parts = []
        for scan in scan_results:
            if scan.succeeded:
                status = "flagged" if scan.is_flagged else "clean"
                parts.append(
                    f"{scan.scan_type} scan: {status} "
                    f"(confidence={scan.confidence:.2f})"
                )
            else:
                parts.append(f"{scan.scan_type} scan: failed — {scan.error_message}")
        return "; ".join(parts) or f"Overall AI confidence: {confidence:.2f}"

    @staticmethod
    def _decide_status(
        confidence: float,
        risk_score: float,
        rule_action: str | None,
    ) -> str:
        """Map AI results + rule action to a final ModerationStatus."""
        # Rule action takes priority if present
        action_map = {
            RuleAction.APPROVE:  ModerationStatus.AUTO_APPROVED,
            RuleAction.REJECT:   ModerationStatus.AUTO_REJECTED,
            RuleAction.ESCALATE: ModerationStatus.ESCALATED,
            RuleAction.FLAG:     ModerationStatus.HUMAN_REVIEW,
        }
        if rule_action and rule_action in action_map:
            return action_map[rule_action]

        # Confidence-based fallback
        if risk_score <= (1 - AUTO_APPROVE_THRESHOLD):
            return ModerationStatus.AUTO_APPROVED
        if risk_score >= AUTO_REJECT_THRESHOLD:
            return ModerationStatus.AUTO_REJECTED
        if risk_score >= FLAG_AUTO_ESCALATE_SCORE:
            return ModerationStatus.ESCALATED
        return ModerationStatus.HUMAN_REVIEW


# =============================================================================
# ScannerService
# =============================================================================

class ScannerService:
    """
    Runs image and text scanners against a SuspiciousSubmission.
    Returns a list of ProofScanner records.
    """

    @staticmethod
    def run_all_scans(
        *,
        submission: SuspiciousSubmission,
        text_content: str = "",
        file_urls: list[str] | None = None,
    ) -> list[ProofScanner]:
        """Run all applicable scanners and return results."""
        results: list[ProofScanner] = []

        if text_content:
            results.append(
                ScannerService._run_text_scan(submission, text_content)
            )

        for url in (file_urls or []):
            results.append(
                ScannerService._run_image_scan(submission, url)
            )

        return results

    @staticmethod
    def _run_text_scan(
        submission: SuspiciousSubmission,
        text: str,
    ) -> ProofScanner:
        from .ml.text_analyzer import TextAnalyzer
        scan = ProofScanner(
            submission=submission,
            scan_type=ScanType.TEXT,
            input_text=text[:10_000],
        )
        start = time.monotonic()
        try:
            analyzer = TextAnalyzer()
            result   = analyzer.analyze(text)
            scan.confidence   = result.confidence
            scan.is_flagged   = result.is_flagged
            scan.labels       = result.labels
            scan.raw_result   = result.raw
            scan.model_version = result.model_version
        except Exception as exc:
            logger.exception("scanner.text_scan_error submission_id=%s", submission.pk)
            scan.error_message = str(exc)[:500]
        finally:
            scan.duration_ms = int((time.monotonic() - start) * 1000)
            scan.save()
        return scan

    @staticmethod
    def _run_image_scan(
        submission: SuspiciousSubmission,
        file_url: str,
    ) -> ProofScanner:
        from .ml.image_scanner import ImageScanner
        scan = ProofScanner(
            submission=submission,
            scan_type=ScanType.IMAGE,
            file_url=file_url,
        )
        start = time.monotonic()
        try:
            scanner = ImageScanner()
            result  = scanner.scan(file_url)
            scan.confidence   = result.confidence
            scan.is_flagged   = result.is_flagged
            scan.labels       = result.labels
            scan.ocr_text     = result.ocr_text or ""
            scan.raw_result   = result.raw
            scan.model_version = result.model_version
        except Exception as exc:
            logger.exception("scanner.image_scan_error submission_id=%s url=%s", submission.pk, file_url)
            scan.error_message = str(exc)[:500]
        finally:
            scan.duration_ms = int((time.monotonic() - start) * 1000)
            scan.save()
        return scan


# =============================================================================
# RuleEngineService
# =============================================================================

class RuleEngineService:
    """
    Evaluates all active AutoApprovalRules for a submission.
    Returns the first matching (rule, action) pair, or (None, None).
    """

    @staticmethod
    def evaluate(
        *,
        submission: SuspiciousSubmission,
        submission_type: str,
        confidence: float,
    ) -> tuple[AutoApprovalRule | None, str | None]:
        """
        Evaluate rules in priority order.
        Returns (matched_rule, action) or (None, None).
        """
        cache_key = CACHE_KEY_ACTIVE_RULES.format(submission_type=submission_type)
        rules = _safe_cache_get(cache_key)

        if rules is None:
            rules = list(
                AutoApprovalRule.objects.for_evaluation(submission_type)
                .values("id", "conditions", "action", "confidence_threshold")
            )
            _safe_cache_set(cache_key, rules, CACHE_TTL_RULES)

        submission_data = RuleEngineService._build_evaluation_context(
            submission, confidence
        )

        for rule_data in rules:
            try:
                if (
                    confidence >= rule_data["confidence_threshold"]
                    and RuleEngineService._evaluate_conditions(
                        rule_data["conditions"], submission_data
                    )
                ):
                    rule = AutoApprovalRule.objects.get(pk=rule_data["id"])
                    logger.debug(
                        "rule_engine.matched rule_id=%s action=%s",
                        rule.pk, rule_data["action"],
                    )
                    return rule, rule_data["action"]
            except Exception:
                logger.exception(
                    "rule_engine.evaluation_error rule_id=%s", rule_data.get("id")
                )
                continue

        return None, None

    @staticmethod
    def _build_evaluation_context(
        submission: SuspiciousSubmission,
        confidence: float,
    ) -> dict[str, Any]:
        return {
            "confidence":       confidence,
            "risk_score":       submission.risk_score or 0.0,
            "risk_level":       submission.risk_level,
            "submission_type":  submission.submission_type,
            "flag_reason":      submission.flag_reason,
            "scan_label_count": len(submission.scan_metadata.get("labels", [])),
        }

    @staticmethod
    def _evaluate_conditions(
        conditions: list[dict],
        context: dict[str, Any],
    ) -> bool:
        """All conditions must match (AND logic)."""
        if not conditions:
            return False   # empty conditions → never fire

        for condition in conditions:
            try:
                if not RuleEngineService._eval_single(condition, context):
                    return False
            except Exception:
                return False
        return True

    @staticmethod
    def _eval_single(condition: dict, context: dict) -> bool:
        import re as _re
        field    = condition.get("field", "")
        operator = condition.get("operator", "eq")
        value    = condition.get("value")
        actual   = context.get(field)

        if actual is None:
            return False

        op_map = {
            "eq":          lambda a, v: a == v,
            "neq":         lambda a, v: a != v,
            "contains":    lambda a, v: str(v).lower() in str(a).lower(),
            "not_contains":lambda a, v: str(v).lower() not in str(a).lower(),
            "regex":       lambda a, v: bool(_re.search(str(v), str(a))),
            "gt":          lambda a, v: float(a) > float(v),
            "lt":          lambda a, v: float(a) < float(v),
            "gte":         lambda a, v: float(a) >= float(v),
            "lte":         lambda a, v: float(a) <= float(v),
            "in":          lambda a, v: a in (v if isinstance(v, list) else [v]),
            "not_in":      lambda a, v: a not in (v if isinstance(v, list) else [v]),
        }
        fn = op_map.get(operator)
        return fn(actual, value) if fn else False


# =============================================================================
# SubmissionService
# =============================================================================

class SubmissionService:
    """CRUD and state-transition helpers for SuspiciousSubmission."""

    @staticmethod
    @transaction.atomic
    def human_approve(
        *,
        submission: SuspiciousSubmission,
        reviewer,
        note: str = "",
    ) -> SuspiciousSubmission:
        submission.reviewed_by   = reviewer
        submission.reviewed_at   = timezone.now()
        submission.reviewer_note = note
        submission.status        = ModerationStatus.HUMAN_APPROVED
        submission.final_status  = ModerationStatus.HUMAN_APPROVED
        submission.save()
        logger.info(
            "submission.human_approved pk=%s reviewer=%s",
            submission.pk, reviewer.pk,
        )
        return submission

    @staticmethod
    @transaction.atomic
    def human_reject(
        *,
        submission: SuspiciousSubmission,
        reviewer,
        note: str = "",
    ) -> SuspiciousSubmission:
        submission.reviewed_by   = reviewer
        submission.reviewed_at   = timezone.now()
        submission.reviewer_note = note
        submission.status        = ModerationStatus.HUMAN_REJECTED
        submission.final_status  = ModerationStatus.HUMAN_REJECTED
        submission.save()
        logger.info(
            "submission.human_rejected pk=%s reviewer=%s",
            submission.pk, reviewer.pk,
        )
        return submission

    @staticmethod
    @transaction.atomic
    def escalate(
        *,
        submission: SuspiciousSubmission,
        escalated_to,
        note: str = "",
    ) -> SuspiciousSubmission:
        submission.escalated_to  = escalated_to
        submission.reviewer_note = note
        submission.status        = ModerationStatus.ESCALATED
        submission.save(update_fields=[
            "escalated_to", "reviewer_note", "status", "updated_at"
        ])
        logger.warning(
            "submission.escalated pk=%s escalated_to=%s",
            submission.pk, escalated_to.pk,
        )
        return submission

    @staticmethod
    def get_or_404(pk: str) -> SuspiciousSubmission:
        try:
            return SuspiciousSubmission.objects.select_full().get(pk=pk)
        except SuspiciousSubmission.DoesNotExist:
            raise SubmissionNotFoundError()


# =============================================================================
# BotService
# =============================================================================

class BotService:
    """TaskBot lifecycle management."""

    @staticmethod
    @transaction.atomic
    def start_bot(bot: TaskBot) -> TaskBot:
        if bot.status == BotStatus.RUNNING:
            raise BotAlreadyRunningError()
        bot.status         = BotStatus.RUNNING
        bot.last_heartbeat = timezone.now()
        bot.retry_count    = 0
        bot.last_error     = ""
        bot.save(update_fields=["status", "last_heartbeat", "retry_count", "last_error", "updated_at"])
        _safe_cache_set(
            CACHE_KEY_BOT_STATUS.format(bot_id=bot.pk),
            BotStatus.RUNNING,
            BOT_HEARTBEAT_INTERVAL_SEC * 4,
        )
        logger.info("bot.started pk=%s name=%r", bot.pk, bot.name)
        return bot

    @staticmethod
    @transaction.atomic
    def stop_bot(bot: TaskBot) -> TaskBot:
        bot.status = BotStatus.IDLE
        bot.save(update_fields=["status", "updated_at"])
        cache.delete(CACHE_KEY_BOT_STATUS.format(bot_id=bot.pk))
        logger.info("bot.stopped pk=%s", bot.pk)
        return bot

    @staticmethod
    def heartbeat(bot: TaskBot) -> None:
        """Update last_heartbeat timestamp (non-atomic, best-effort)."""
        TaskBot.objects.filter(pk=bot.pk).update(last_heartbeat=timezone.now())
        _safe_cache_set(
            CACHE_KEY_BOT_STATUS.format(bot_id=bot.pk),
            bot.status,
            BOT_HEARTBEAT_INTERVAL_SEC * 4,
        )

    @staticmethod
    @transaction.atomic
    def record_error(bot: TaskBot, error: str) -> TaskBot:
        from .constants import MAX_BOT_RETRIES
        bot.last_error   = error[:500]
        bot.retry_count  = (bot.retry_count or 0) + 1
        bot.bump_stat("total_errors")
        if bot.retry_count >= MAX_BOT_RETRIES:
            bot.status = BotStatus.ERROR
        bot.save(update_fields=[
            "last_error", "retry_count", "total_errors", "status", "updated_at"
        ])
        return bot

    @staticmethod
    def process_pending_batch(bot: TaskBot, batch_size: int = 50) -> int:
        """
        Process a batch of PENDING submissions for the bot's submission_type.
        Returns the number of successfully processed submissions.
        """
        submissions = (
            SuspiciousSubmission.objects
            .pending()
            .for_type(bot.submission_type)
            .order_by("created_at")[:batch_size]
        )

        processed = 0
        for sub in submissions:
            try:
                ModerationService.process_submission(
                    content_type=sub.content_type,
                    content_id=sub.content_id,
                    submission_type=sub.submission_type,
                    submitted_by=sub.submitted_by,
                )
                processed += 1
                BotService.heartbeat(bot)
            except Exception as exc:
                logger.exception(
                    "bot.process_error bot_id=%s submission_id=%s",
                    bot.pk, sub.pk,
                )
                BotService.record_error(bot, str(exc))

        # Update stats
        TaskBot.objects.filter(pk=bot.pk).update(
            total_processed=models.F("total_processed") + processed
        )
        return processed


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _safe_cache_get(key: str) -> Any:
    try:
        return cache.get(key)
    except Exception:
        logger.warning("auto_mod.cache_get_failed key=%s", key)
        return None


def _safe_cache_set(key: str, value: Any, timeout: int) -> None:
    try:
        cache.set(key, value, timeout)
    except Exception:
        logger.warning("auto_mod.cache_set_failed key=%s", key)
