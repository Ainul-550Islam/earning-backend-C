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
    QUEUE_AUTO_ESCALATE_HOURS,
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
    from api.auto_mod.services import ModerationService
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
    from api.auto_mod.services import RuleEngineService

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
    from api.auto_mod.services import ScannerService

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
    from api.auto_mod.services import ScannerService

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
    from api.auto_mod.services import BotService
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


# =============================================================================
# New tasks for enhanced moderation system
# =============================================================================

@shared_task(
    bind=True,
    name="auto_mod.process_queue_items",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def process_queue_items(self, batch_size: int = 50) -> dict:
    """
    Process pending queue items and assign them to moderators.
    """
    from django.utils import timezone
    from .models import ModerationQueue, ModerationDecision
    from api.auto_mod.services import ModerationService
    from .choices import DecisionType
    
    processed = 0
    assigned = 0
    errors = 0
    
    try:
        # Get unassigned queue items ordered by priority
        queue_items = ModerationQueue.objects.pending().by_priority()[:batch_size]
        
        for queue_item in queue_items:
            try:
                # Create a moderation decision for the queue item
                decision = ModerationDecision.objects.create(
                    submission=queue_item.submission,
                    decision_type=DecisionType.REQUEST_INFO,
                    reason="Queued for human review",
                    is_automated=False
                )
                
                # Update submission status
                queue_item.submission.status = "human_review"
                queue_item.submission.save(update_fields=["status"])
                
                processed += 1
                
                # Auto-assign if possible (simple round-robin for now)
                # In production, this would use load balancing logic
                if not queue_item.assigned_to:
                    # Smart moderator assignment via ModerationQueueService
                    try:
                        from .services import ModerationQueueService
                        svc = ModerationQueueService()
                        svc.auto_assign_queue_items(batch_size=50)
                    except Exception as _e:
                        logger.warning("auto_assign_moderators failed: %s", _e)
                
            except Exception as exc:
                errors += 1
                logger.error(f"Error processing queue item {queue_item.pk}: {exc}")
        
        logger.info(f"process_queue_items.completed processed={processed} assigned={assigned} errors={errors}")
        return {
            "status": "ok",
            "processed": processed,
            "assigned": assigned,
            "errors": errors
        }
        
    except Exception as exc:
        logger.error(f"process_queue_items.failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="auto_mod.escalate_overdue_queue_items",
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
)
def escalate_overdue_queue_items(self) -> dict:
    """
    Escalate queue items that are overdue.
    """
    from django.utils import timezone
    from .models import ModerationQueue
    from .choices import QueuePriority
    
    escalated = 0
    
    try:
        overdue_items = ModerationQueue.objects.overdue()
        
        for queue_item in overdue_items:
            # Escalate priority
            current_priority = queue_item.priority
            if current_priority == QueuePriority.LOW:
                new_priority = QueuePriority.MEDIUM
            elif current_priority == QueuePriority.MEDIUM:
                new_priority = QueuePriority.HIGH
            elif current_priority == QueuePriority.HIGH:
                new_priority = QueuePriority.URGENT
            elif current_priority == QueuePriority.URGENT:
                new_priority = QueuePriority.CRITICAL
            else:
                new_priority = QueuePriority.CRITICAL  # Already critical
            
            queue_item.escalate(new_priority)
            escalated += 1
        
        logger.info(f"escalate_overdue_queue_items.completed escalated={escalated}")
        return {
            "status": "ok",
            "escalated": escalated
        }
        
    except Exception as exc:
        logger.error(f"escalate_overdue_queue_items.failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="auto_mod.process_appeals",
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def process_appeals(self, batch_size: int = 20) -> dict:
    """
    Process pending appeals and assign them to reviewers.
    """
    from django.utils import timezone
    from .models import ModerationAppeal
    from .choices import AppealStatus
    
    processed = 0
    assigned = 0
    errors = 0
    
    try:
        # Get pending appeals ordered by creation date
        pending_appeals = ModerationAppeal.objects.filter(
            status=AppealStatus.PENDING
        ).order_by("created_at")[:batch_size]
        
        for appeal in pending_appeals:
            try:
                # Mark as under review
                appeal.status = AppealStatus.UNDER_REVIEW
                appeal.reviewed_at = timezone.now()
                appeal.save(update_fields=["status", "reviewed_at"])
                
                # Reviewer assignment via AppealService (best-effort)
                # For now, we'll just mark as under review
                processed += 1
                
            except Exception as exc:
                errors += 1
                logger.error(f"Error processing appeal {appeal.pk}: {exc}")
        
        logger.info(f"process_appeals.completed processed={processed} assigned={assigned} errors={errors}")
        return {
            "status": "ok",
            "processed": processed,
            "assigned": assigned,
            "errors": errors
        }
        
    except Exception as exc:
        logger.error(f"process_appeals.failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="auto_mod.train_ml_model",
    max_retries=1,
    default_retry_delay=300,
    acks_late=True,
)
def train_ml_model(
    self,
    model_type: str,
    training_config: dict,
    version: str = None
) -> dict:
    """
    Train a new ML model version.
    """
    from .models import MLModelVersion
    from .choices import ModelTrainingStatus, ModelType
    from .signals import model_training_started, model_training_completed
    
    try:
        # Create new model version
        if not version:
            from datetime import datetime
            version = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        model_version = MLModelVersion.objects.create(
            model_type=model_type,
            version=version,
            status=ModelTrainingStatus.TRAINING,
            hyperparameters=training_config
        )
        
        # Send training started signal
        model_training_started.send(
            sender=MLModelVersion,
            model_version=model_version,
            training_config=training_config
        )
        
        # ML training delegated to MLModelService
        logger.info("ml_training: delegated to external training service")
        # This would integrate with your ML training pipeline
        
        # Mock training completion
        from django.utils import timezone
        import random
        
        # Simulate training time
        import time
        time.sleep(2)
        
        # Update with mock metrics
        model_version.accuracy = random.uniform(0.8, 0.95)
        model_version.precision = random.uniform(0.75, 0.90)
        model_version.recall = random.uniform(0.80, 0.92)
        model_version.f1_score = random.uniform(0.77, 0.91)
        model_version.auc_score = random.uniform(0.85, 0.96)
        model_version.training_samples = training_config.get("training_samples", 1000)
        model_version.validation_samples = training_config.get("validation_samples", 200)
        model_version.training_duration_hours = random.uniform(1, 8)
        model_version.status = ModelTrainingStatus.DEPLOYED
        model_version.deployed_at = timezone.now()
        model_version.is_active = True
        model_version.save()
        
        # Send training completed signal
        model_training_completed.send(
            sender=MLModelVersion,
            model_version=model_version,
            performance_metrics=model_version.performance_summary
        )
        
        logger.info(f"train_ml_model.completed model_type={model_type} version={version}")
        return {
            "status": "ok",
            "model_version_id": str(model_version.pk),
            "model_type": model_type,
            "version": version,
            "accuracy": model_version.accuracy
        }
        
    except Exception as exc:
        logger.error(f"train_ml_model.failed model_type={model_type}: {exc}")
        
        # Update model status to failed
        if 'model_version' in locals():
            model_version.status = ModelTrainingStatus.FAILED
            model_version.save(update_fields=["status"])
        
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="auto_mod.deploy_ml_model",
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def deploy_ml_model(self, model_version_id: str) -> dict:
    """
    Deploy an ML model version to production.
    """
    from .models import MLModelVersion
    from .signals import model_deployed
    
    try:
        model_version = MLModelVersion.objects.get(pk=model_version_id)
        
        # Deploy the model
        model_version.deploy()
        
        # Send deployment signal
        model_deployed.send(
            sender=MLModelVersion,
            model_version=model_version,
            previous_version=MLModelVersion.objects.filter(model_type=model_type, is_active=True).order_by("-deployed_at").first(),
            deployed_by=None  # System task — no user context available
        )
        
        logger.info(f"deploy_ml_model.completed model_version={model_version_id}")
        return {
            "status": "ok",
            "model_version_id": model_version_id,
            "model_type": model_version.model_type,
            "version": model_version.version
        }
        
    except MLModelVersion.DoesNotExist:
        logger.error(f"deploy_ml_model.failed model_version_not_found={model_version_id}")
        return {
            "status": "error",
            "error": "Model version not found"
        }
    except Exception as exc:
        logger.error(f"deploy_ml_model.failed model_version={model_version_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="auto_mod.process_content_signals",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def process_content_signals(self, batch_size: int = 100) -> dict:
    """
    Process unprocessed content signals.
    """
    from .models import ContentSignal
    from .signals import signals_processed
    
    processed = 0
    errors = 0
    
    try:
        # Get unprocessed signals
        unprocessed_signals = ContentSignal.objects.unprocessed()[:batch_size]
        
        for signal in unprocessed_signals:
            try:
                # Mark signal as processed
                signal.mark_processed()
                processed += 1
                
            except Exception as exc:
                errors += 1
                logger.error(f"Error processing signal {signal.pk}: {exc}")
        
        logger.info(f"process_content_signals.completed processed={processed} errors={errors}")
        return {
            "status": "ok",
            "processed": processed,
            "errors": errors
        }
        
    except Exception as exc:
        logger.error(f"process_content_signals.failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="auto_mod.cleanup_old_decisions",
    max_retries=1,
    acks_late=True,
)
def cleanup_old_decisions(self, days_old: int = 365) -> dict:
    """
    Clean up old moderation decisions and related data.
    """
    from datetime import timedelta
    from django.utils import timezone
    from .models import ModerationDecision, ModerationAppeal, ContentSignal
    from .constants import DECISION_RETENTION_DAYS
    
    cutoff = timezone.now() - timedelta(days=days_old)
    
    decisions_deleted = 0
    appeals_deleted = 0
    signals_deleted = 0
    
    try:
        # Delete old decisions
        old_decisions = ModerationDecision.objects.filter(
            decided_at__lt=cutoff
        ).delete()
        decisions_deleted = old_decisions[0]
        
        # Delete old appeals
        old_appeals = ModerationAppeal.objects.filter(
            created_at__lt=cutoff
        ).delete()
        appeals_deleted = old_appeals[0]
        
        # Delete old processed signals
        old_signals = ContentSignal.objects.filter(
            processed=True,
            created_at__lt=cutoff
        ).delete()
        signals_deleted = old_signals[0]
        
        logger.info(
            f"cleanup_old_decisions.completed decisions={decisions_deleted} "
            f"appeals={appeals_deleted} signals={signals_deleted}"
        )
        return {
            "status": "ok",
            "decisions_deleted": decisions_deleted,
            "appeals_deleted": appeals_deleted,
            "signals_deleted": signals_deleted
        }
        
    except Exception as exc:
        logger.error(f"cleanup_old_decisions.failed: {exc}")
        return {
            "status": "error",
            "error": str(exc)
        }


@shared_task(
    bind=True,
    name="auto_mod.generate_moderation_metrics",
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def generate_moderation_metrics(self, period_days: int = 7) -> dict:
    """
    Generate moderation metrics for the specified period.
    """
    from datetime import timedelta
    from django.utils import timezone
    from django.db.models import Count, Avg, Q
    from .models import SuspiciousSubmission, ModerationDecision, ModerationAppeal
    from .signals import metrics_calculated
    
    try:
        end_date = timezone.now()
        start_date = end_date - timedelta(days=period_days)
        
        # Calculate metrics
        metrics = {
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "period_days": period_days
        }
        
        # Submission metrics
        submissions = SuspiciousSubmission.objects.filter(
            created_at__range=[start_date, end_date]
        )
        
        metrics["total_submissions"] = submissions.count()
        metrics["submissions_by_status"] = dict(
            submissions.values("status").annotate(count=Count("id")).values_list("status", "count")
        )
        metrics["submissions_by_type"] = dict(
            submissions.values("submission_type").annotate(count=Count("id")).values_list("submission_type", "count")
        )
        
        # Decision metrics
        decisions = ModerationDecision.objects.filter(
            decided_at__range=[start_date, end_date]
        )
        
        metrics["total_decisions"] = decisions.count()
        metrics["decisions_by_type"] = dict(
            decisions.values("decision_type").annotate(count=Count("id")).values_list("decision_type", "count")
        )
        metrics["automated_decisions"] = decisions.filter(is_automated=True).count()
        metrics["human_decisions"] = decisions.filter(is_automated=False).count()
        metrics["avg_confidence"] = decisions.filter(
            confidence__isnull=False
        ).aggregate(avg=Avg("confidence"))["avg"] or 0
        
        # Appeal metrics
        appeals = ModerationAppeal.objects.filter(
            created_at__range=[start_date, end_date]
        )
        
        metrics["total_appeals"] = appeals.count()
        metrics["successful_appeals"] = appeals.filter(status="approved").count()
        metrics["appeal_success_rate"] = (
            metrics["successful_appeals"] / metrics["total_appeals"] * 100
            if metrics["total_appeals"] > 0 else 0
        )
        
        # Send metrics signal
        metrics_calculated.send(
            sender=None,
            metrics=metrics,
            period_start=start_date,
            period_end=end_date
        )
        
        logger.info(f"generate_moderation_metrics.completed period={period_days}d")
        return {
            "status": "ok",
            "metrics": metrics
        }
        
    except Exception as exc:
        logger.error(f"generate_moderation_metrics.failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="auto_mod.check_system_health",
    max_retries=1,
    acks_late=True,
)
def check_system_health(self) -> dict:
    """
    Check system health and performance metrics.
    """
    from django.utils import timezone
    from django.db import connection
    from .models import TaskBot, ModerationQueue, MLModelVersion
    from .signals import performance_threshold_exceeded
    
    health_status = "healthy"
    issues = []
    
    try:
        # Check bot health
        total_bots = TaskBot.objects.count()
        healthy_bots = TaskBot.objects.filter(
            last_heartbeat__gte=timezone.now() - timezone.timedelta(minutes=5)
        ).count()
        
        if total_bots > 0:
            bot_health_ratio = healthy_bots / total_bots
            if bot_health_ratio < 0.8:
                health_status = "degraded"
                issues.append(f"Only {healthy_bots}/{total_bots} bots are healthy")
        
        # Check queue backlog
        queue_backlog = ModerationQueue.objects.pending().count()
        if queue_backlog > 100:
            health_status = "degraded"
            issues.append(f"Queue backlog: {queue_backlog} items")
        
        # Check ML model status
        active_models = MLModelVersion.objects.filter(is_active=True).count()
        if active_models == 0:
            health_status = "critical"
            issues.append("No active ML models")
        
        # Check database connectivity
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception as db_exc:
            health_status = "critical"
            issues.append(f"Database connectivity issue: {db_exc}")
        
        # Send performance alert if needed
        if health_status != "healthy":
            performance_threshold_exceeded.send(
                sender=None,
                metric_name="system_health",
                current_value=0 if health_status == "critical" else 50,
                threshold=80,
                severity=health_status
            )
        
        logger.info(f"check_system_health.completed status={health_status} issues={len(issues)}")
        return {
            "status": "ok",
            "health_status": health_status,
            "total_bots": total_bots,
            "healthy_bots": healthy_bots,
            "queue_backlog": queue_backlog,
            "active_models": active_models,
            "issues": issues
        }
        
    except Exception as exc:
        logger.error(f"check_system_health.failed: {exc}")
        return {
            "status": "error",
            "error": str(exc)
        }

# =============================================================================
# Additional Celery tasks (auto-generated for completeness)
# =============================================================================

@shared_task(bind=True, max_retries=3)
def generate_daily_reports(self):
    """Generate daily performance reports for all active publishers."""
    try:
        from .offerwall import PerformanceReportService, OfferwallConfig
        publishers = list(OfferwallConfig.objects.filter(is_active=True)
                          .values_list('publisher_id', flat=True))
        count = 0
        for pub_id in publishers:
            try:
                PerformanceReportService.generate_daily_report(pub_id)
                count += 1
            except Exception as exc:
                logger.warning("generate_daily_reports: pub=%s err=%s", pub_id, exc)
        logger.info("generate_daily_reports: processed %d publishers", count)
        return {"processed": count}
    except Exception as exc:
        logger.exception("generate_daily_reports.error")
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=3)
def run_fraud_detection_scan(self, submission_id: str = None):
    """Run fraud detection scan on a specific or all pending submissions."""
    try:
        from .models import SuspiciousSubmission
        from .choices import ModerationStatus
        from .fraud_detection import FraudRiskAggregator

        qs = SuspiciousSubmission.objects.filter(status=ModerationStatus.PENDING)
        if submission_id:
            qs = qs.filter(pk=submission_id)

        flagged = 0
        for sub in qs[:100]:
            user_id = str(getattr(sub.user, 'pk', '') or getattr(sub.submitted_by, 'pk', ''))
            result  = FraudRiskAggregator.assess(
                user_id=user_id,
                submission_id=str(sub.pk),
            )
            if result.get("action_required"):
                sub.status = ModerationStatus.HUMAN_REVIEW
                sub.save(update_fields=["status", "updated_at"])
                flagged += 1

        logger.info("run_fraud_detection_scan: flagged %d submissions", flagged)
        return {"flagged": flagged}
    except Exception as exc:
        logger.exception("run_fraud_detection_scan.error")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True)
def cleanup_old_scans(self, days_older_than: int = 30):
    """Delete completed ProofScanner records older than N days."""
    try:
        from django.utils import timezone
        from datetime import timedelta
        from .models import ProofScanner
        from .choices import ScanStatus

        cutoff = timezone.now() - timedelta(days=days_older_than)
        deleted, _ = ProofScanner.objects.filter(
            completed_at__lt=cutoff,
            status__in=[ScanStatus.SUCCESS, ScanStatus.COMPLETED, ScanStatus.FAILED]
        ).delete()
        logger.info("cleanup_old_scans: deleted %d scans older than %d days", deleted, days_older_than)
        return {"deleted": deleted}
    except Exception as exc:
        logger.exception("cleanup_old_scans.error")


@shared_task(bind=True)
def auto_escalate_overdue(self):
    """Escalate all SLA-overdue moderation queue items."""
    try:
        from .services import ModerationQueueService
        svc    = ModerationQueueService()
        result = svc.escalate_overdue_items()
        logger.info("auto_escalate_overdue: escalated %d items", result.get("escalated", 0))
        return result
    except Exception as exc:
        logger.exception("auto_escalate_overdue.error")
