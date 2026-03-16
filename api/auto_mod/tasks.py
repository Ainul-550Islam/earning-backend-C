# =============================================================================
# auto_mod/tasks.py
# =============================================================================

from __future__ import annotations

import logging

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from .constants import (
    BOT_HEARTBEAT_INTERVAL_SEC,
    MAX_BOT_RETRIES,
    TASK_BOT_PROCESS,
    TASK_CLEANUP_OLD_SUBMISSIONS,
    TASK_EVALUATE_RULES,
    TASK_RETRAIN_MODEL,
    TASK_RUN_IMAGE_SCAN,
    TASK_RUN_TEXT_ANALYSIS,
    TASK_SCAN_SUBMISSION,
)

logger = logging.getLogger(__name__)


# =============================================================================
# scan_submission — main entry point
# =============================================================================

@shared_task(
    bind=True,
    name=TASK_SCAN_SUBMISSION,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def scan_submission(
    self,
    content_type: str,
    content_id: str,
    submission_type: str,
    user_id: str | None = None,
    text_content: str = "",
    file_urls: list[str] | None = None,
    metadata: dict | None = None,
) -> dict:
    """
    Full moderation pipeline for a single submission.
    Delegated entirely to ModerationService.process_submission().
    """
    from django.contrib.auth import get_user_model
    from .services import ModerationService
    from .exceptions import SubmissionAlreadyProcessedError

    User      = get_user_model()
    submitted_by = None
    if user_id:
        try:
            submitted_by = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            pass

    try:
        submission = ModerationService.process_submission(
            content_type=content_type,
            content_id=content_id,
            submission_type=submission_type,
            submitted_by=submitted_by,
            text_content=text_content or "",
            file_urls=file_urls or [],
            metadata=metadata or {},
        )
        logger.info(
            "scan_submission.done content_id=%s status=%s",
            content_id, submission.status,
        )
        return {"status": "ok", "submission_id": str(submission.pk), "decision": submission.status}
    except SubmissionAlreadyProcessedError:
        logger.info("scan_submission.already_processed content_id=%s", content_id)
        return {"status": "skipped", "reason": "already_processed"}
    except Exception as exc:
        logger.exception("scan_submission.error content_id=%s attempt=%d", content_id, self.request.retries)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"status": "error", "reason": "max_retries_exceeded"}


# =============================================================================
# evaluate_rules — standalone rule re-evaluation
# =============================================================================

@shared_task(
    bind=True,
    name=TASK_EVALUATE_RULES,
    max_retries=2,
    default_retry_delay=15,
    acks_late=True,
)
def evaluate_rules(self, submission_id: str) -> dict:
    """Re-evaluate all active rules against an existing submission."""
    from .models import SuspiciousSubmission
    from .services import RuleEngineService

    try:
        submission = SuspiciousSubmission.objects.select_related("matched_rule").get(pk=submission_id)
    except SuspiciousSubmission.DoesNotExist:
        return {"status": "error", "reason": "submission_not_found"}

    try:
        rule, action = RuleEngineService.evaluate(
            submission=submission,
            submission_type=submission.submission_type,
            confidence=submission.ai_confidence or 0.0,
        )
        if rule:
            submission.matched_rule = rule
            submission.save(update_fields=["matched_rule", "updated_at"])

        return {
            "status":  "ok",
            "matched": rule is not None,
            "action":  action,
        }
    except Exception as exc:
        logger.exception("evaluate_rules.error submission_id=%s", submission_id)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"status": "error", "reason": str(exc)}


# =============================================================================
# run_image_scan
# =============================================================================

@shared_task(
    bind=True,
    name=TASK_RUN_IMAGE_SCAN,
    max_retries=2,
    default_retry_delay=20,
    acks_late=True,
    time_limit=60,
)
def run_image_scan(self, submission_id: str, file_url: str) -> dict:
    """Run image scan for a single file URL."""
    from .models import SuspiciousSubmission
    from .services import ScannerService

    try:
        submission = SuspiciousSubmission.objects.get(pk=submission_id)
    except SuspiciousSubmission.DoesNotExist:
        return {"status": "error", "reason": "not_found"}

    try:
        scan = ScannerService._run_image_scan(submission, file_url)
        return {
            "status":     "ok",
            "scan_id":    str(scan.pk),
            "is_flagged": scan.is_flagged,
            "confidence": scan.confidence,
        }
    except Exception as exc:
        logger.exception("run_image_scan.error submission_id=%s", submission_id)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"status": "error", "reason": str(exc)}


# =============================================================================
# run_text_analysis
# =============================================================================

@shared_task(
    bind=True,
    name=TASK_RUN_TEXT_ANALYSIS,
    max_retries=2,
    default_retry_delay=10,
    acks_late=True,
)
def run_text_analysis(self, submission_id: str, text: str) -> dict:
    """Run text analysis for a submission."""
    from .models import SuspiciousSubmission
    from .services import ScannerService

    try:
        submission = SuspiciousSubmission.objects.get(pk=submission_id)
    except SuspiciousSubmission.DoesNotExist:
        return {"status": "error", "reason": "not_found"}

    try:
        scan = ScannerService._run_text_scan(submission, text)
        return {
            "status":     "ok",
            "scan_id":    str(scan.pk),
            "is_flagged": scan.is_flagged,
            "confidence": scan.confidence,
        }
    except Exception as exc:
        logger.exception("run_text_analysis.error submission_id=%s", submission_id)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"status": "error", "reason": str(exc)}


# =============================================================================
# bot_process_task
# =============================================================================

@shared_task(
    bind=True,
    name=TASK_BOT_PROCESS,
    max_retries=MAX_BOT_RETRIES,
    default_retry_delay=BOT_HEARTBEAT_INTERVAL_SEC,
    acks_late=True,
)
def bot_process_task(self, bot_id: str) -> dict:
    """
    Run a single processing cycle for a TaskBot.
    Continuously re-enqueues itself while there are pending submissions.
    """
    from .models import TaskBot
    from .services import BotService
    from .choices import BotStatus

    try:
        bot = TaskBot.objects.get(pk=bot_id)
    except TaskBot.DoesNotExist:
        return {"status": "error", "reason": "bot_not_found"}

    if bot.status != BotStatus.RUNNING:
        return {"status": "skipped", "reason": f"bot status={bot.status}"}

    try:
        batch_size = bot.config.get("max_batch_size", 50)
        processed  = BotService.process_pending_batch(bot, batch_size=batch_size)
        logger.info("bot.cycle_done bot_id=%s processed=%d", bot_id, processed)

        # Re-enqueue if there may be more work
        if processed >= batch_size:
            bot_process_task.apply_async(
                args=[bot_id],
                countdown=bot.config.get("process_interval", 10),
            )

        return {"status": "ok", "processed": processed}

    except Exception as exc:
        logger.exception("bot_process_task.error bot_id=%s", bot_id)
        BotService.record_error(bot, str(exc))
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"status": "error", "reason": "max_retries_exceeded"}


# =============================================================================
# retrain_model
# =============================================================================

@shared_task(
    bind=True,
    name=TASK_RETRAIN_MODEL,
    max_retries=1,
    acks_late=True,
    time_limit=3600,
)
def retrain_model(self, model_name: str, dry_run: bool = False) -> dict:
    """
    Trigger ML model retraining.
    In production this would export training data and submit a training job.
    """
    logger.info("retrain_model.start model=%s dry_run=%s", model_name, dry_run)
    try:
        if dry_run:
            return {"status": "ok", "model": model_name, "dry_run": True, "samples": 0}

        # Placeholder: integrate with your ML training pipeline
        # e.g. export labelled SuspiciousSubmission records to S3
        # and trigger a SageMaker / Vertex AI training job
        from .models import SuspiciousSubmission
        labelled_count = SuspiciousSubmission.objects.resolved().count()
        logger.info("retrain_model.data_export model=%s samples=%d", model_name, labelled_count)

        return {"status": "ok", "model": model_name, "samples": labelled_count}
    except Exception as exc:
        logger.exception("retrain_model.error model=%s", model_name)
        return {"status": "error", "reason": str(exc)}


# =============================================================================
# cleanup_old_submissions
# =============================================================================

@shared_task(
    bind=True,
    name=TASK_CLEANUP_OLD_SUBMISSIONS,
    max_retries=1,
    acks_late=True,
)
def cleanup_old_submissions(self, days_old: int = 90) -> dict:
    """
    Mark expired old resolved submissions and delete orphan scans.
    """
    from datetime import timedelta
    from django.utils import timezone
    from .models import SuspiciousSubmission, ProofScanner
    from .choices import ModerationStatus

    cutoff = timezone.now() - timedelta(days=days_old)

    # Mark old resolved submissions as expired
    expired = SuspiciousSubmission.objects.filter(
        status__in=[
            ModerationStatus.AUTO_APPROVED,
            ModerationStatus.AUTO_REJECTED,
            ModerationStatus.HUMAN_APPROVED,
            ModerationStatus.HUMAN_REJECTED,
        ],
        updated_at__lt=cutoff,
    ).update(status=ModerationStatus.EXPIRED)

    # Clean up scans for expired submissions
    orphan_scans = ProofScanner.objects.filter(
        submission__status=ModerationStatus.EXPIRED
    ).count()

    logger.info(
        "cleanup_old_submissions.done expired=%d orphan_scans=%d",
        expired, orphan_scans,
    )
    return {"status": "ok", "expired": expired, "orphan_scans": orphan_scans}
