# =============================================================================
# auto_mod/managers.py
# =============================================================================

from __future__ import annotations

from django.db import models
from django.db.models import Avg, Count, Q
from django.utils import timezone


# ---------------------------------------------------------------------------
# AutoApprovalRule
# ---------------------------------------------------------------------------

class AutoApprovalRuleQuerySet(models.QuerySet):

    def active(self) -> "AutoApprovalRuleQuerySet":
        return self.filter(is_active=True)

    def for_type(self, submission_type: str) -> "AutoApprovalRuleQuerySet":
        return self.filter(submission_type=submission_type)

    def by_priority(self) -> "AutoApprovalRuleQuerySet":
        return self.order_by("priority")

    def for_action(self, action: str) -> "AutoApprovalRuleQuerySet":
        return self.filter(action=action)

    def system_rules(self) -> "AutoApprovalRuleQuerySet":
        return self.filter(is_system=True)

    def user_rules(self) -> "AutoApprovalRuleQuerySet":
        return self.filter(is_system=False)

    def for_evaluation(self, submission_type: str) -> "AutoApprovalRuleQuerySet":
        """Return active rules for a type, ordered by priority."""
        return self.active().for_type(submission_type).by_priority()


class AutoApprovalRuleManager(models.Manager):
    def get_queryset(self) -> AutoApprovalRuleQuerySet:
        return AutoApprovalRuleQuerySet(self.model, using=self._db)

    def active(self) -> AutoApprovalRuleQuerySet:
        return self.get_queryset().active()

    def for_evaluation(self, submission_type: str) -> AutoApprovalRuleQuerySet:
        return self.get_queryset().for_evaluation(submission_type)


# ---------------------------------------------------------------------------
# SuspiciousSubmission
# ---------------------------------------------------------------------------

class SuspiciousSubmissionQuerySet(models.QuerySet):

    def pending(self) -> "SuspiciousSubmissionQuerySet":
        from .choices import ModerationStatus
        return self.filter(status=ModerationStatus.PENDING)

    def scanning(self) -> "SuspiciousSubmissionQuerySet":
        from .choices import ModerationStatus
        return self.filter(status=ModerationStatus.SCANNING)

    def awaiting_review(self) -> "SuspiciousSubmissionQuerySet":
        from .choices import ModerationStatus
        return self.filter(status=ModerationStatus.HUMAN_REVIEW)

    def resolved(self) -> "SuspiciousSubmissionQuerySet":
        from .choices import ModerationStatus
        return self.filter(status__in=[
            ModerationStatus.AUTO_APPROVED,
            ModerationStatus.AUTO_REJECTED,
            ModerationStatus.HUMAN_APPROVED,
            ModerationStatus.HUMAN_REJECTED,
        ])

    def escalated(self) -> "SuspiciousSubmissionQuerySet":
        from .choices import ModerationStatus
        return self.filter(status=ModerationStatus.ESCALATED)

    def high_risk(self) -> "SuspiciousSubmissionQuerySet":
        from .choices import RiskLevel
        return self.filter(risk_level__in=[RiskLevel.HIGH, RiskLevel.CRITICAL])

    def for_user(self, user) -> "SuspiciousSubmissionQuerySet":
        return self.filter(submitted_by=user)

    def for_type(self, submission_type: str) -> "SuspiciousSubmissionQuerySet":
        return self.filter(submission_type=submission_type)

    def for_content(
        self, content_type: str, content_id: str
    ) -> "SuspiciousSubmissionQuerySet":
        return self.filter(content_type=content_type, content_id=content_id)

    def unreviewed(self) -> "SuspiciousSubmissionQuerySet":
        return self.filter(reviewed_by__isnull=True)

    def in_date_range(self, start, end) -> "SuspiciousSubmissionQuerySet":
        return self.filter(created_at__date__gte=start, created_at__date__lte=end)

    def select_full(self) -> "SuspiciousSubmissionQuerySet":
        return self.select_related(
            "submitted_by", "reviewed_by",
            "escalated_to", "matched_rule",
        ).prefetch_related("scans")

    def risk_stats(self) -> dict:
        from .choices import RiskLevel
        return self.aggregate(
            total=Count("id"),
            avg_confidence=Avg("ai_confidence"),
            avg_risk=Avg("risk_score"),
            high_risk_count=Count("id", filter=Q(
                risk_level__in=[RiskLevel.HIGH, RiskLevel.CRITICAL]
            )),
        )


class SuspiciousSubmissionManager(models.Manager):
    def get_queryset(self) -> SuspiciousSubmissionQuerySet:
        return SuspiciousSubmissionQuerySet(self.model, using=self._db)

    def pending(self) -> SuspiciousSubmissionQuerySet:
        return self.get_queryset().pending()

    def awaiting_review(self) -> SuspiciousSubmissionQuerySet:
        return self.get_queryset().awaiting_review()

    def high_risk(self) -> SuspiciousSubmissionQuerySet:
        return self.get_queryset().high_risk()


    def escalated(self) -> SuspiciousSubmissionQuerySet:
        return self.get_queryset().escalated()
    def human_review(self) -> SuspiciousSubmissionQuerySet:
        return self.get_queryset().human_review()
    def auto_approved(self) -> SuspiciousSubmissionQuerySet:
        return self.get_queryset().auto_approved()
    def auto_rejected(self) -> SuspiciousSubmissionQuerySet:
        return self.get_queryset().auto_rejected()

    def scanning(self) -> SuspiciousSubmissionQuerySet:
        return self.get_queryset().scanning()
    def resolved(self) -> SuspiciousSubmissionQuerySet:
        return self.get_queryset().resolved()
    def unreviewed(self) -> SuspiciousSubmissionQuerySet:
        return self.get_queryset().unreviewed()
    def select_full(self) -> SuspiciousSubmissionQuerySet:
        return self.get_queryset().select_full()
    def for_type(self, val) -> SuspiciousSubmissionQuerySet:
        return self.get_queryset().for_type(val)
    def for_user(self, val) -> SuspiciousSubmissionQuerySet:
        return self.get_queryset().for_user(val)
    def risk_stats(self) -> SuspiciousSubmissionQuerySet:
        return self.get_queryset().risk_stats()

# ---------------------------------------------------------------------------
# ProofScanner
# ---------------------------------------------------------------------------

class ProofScannerQuerySet(models.QuerySet):

    def for_submission(self, submission) -> "ProofScannerQuerySet":
        return self.filter(submission=submission)

    def flagged(self) -> "ProofScannerQuerySet":
        return self.filter(is_flagged=True)

    def clean(self) -> "ProofScannerQuerySet":
        return self.filter(is_flagged=False)

    def failed(self) -> "ProofScannerQuerySet":
        return self.exclude(error_message="")

    def for_scan_type(self, scan_type: str) -> "ProofScannerQuerySet":
        return self.filter(scan_type=scan_type)

    def completed(self) -> "ProofScannerQuerySet":
        return self.filter(confidence__isnull=False, error_message="")

    def aggregate_confidence(self) -> dict:
        return self.aggregate(avg=Avg("confidence"), count=Count("id"))


class ProofScannerManager(models.Manager):
    def get_queryset(self) -> ProofScannerQuerySet:
        return ProofScannerQuerySet(self.model, using=self._db)

    def flagged(self) -> ProofScannerQuerySet:
        return self.get_queryset().flagged()

    def for_submission(self, submission) -> ProofScannerQuerySet:
        return self.get_queryset().for_submission(submission)


# ---------------------------------------------------------------------------
# TaskBot
# ---------------------------------------------------------------------------

class TaskBotQuerySet(models.QuerySet):

    def active(self) -> "TaskBotQuerySet":
        from .choices import BotStatus
        return self.filter(status__in=[BotStatus.IDLE, BotStatus.RUNNING])

    def running(self) -> "TaskBotQuerySet":
        from .choices import BotStatus
        return self.filter(status=BotStatus.RUNNING)

    def idle(self) -> "TaskBotQuerySet":
        from .choices import BotStatus
        return self.filter(status=BotStatus.IDLE)

    def errored(self) -> "TaskBotQuerySet":
        from .choices import BotStatus
        return self.filter(status=BotStatus.ERROR)

    def for_type(self, submission_type: str) -> "TaskBotQuerySet":
        return self.filter(submission_type=submission_type)

    def stale(self, timeout_seconds: int = 90) -> "TaskBotQuerySet":
        """Bots that haven't sent a heartbeat within timeout_seconds."""
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(seconds=timeout_seconds)
        return self.filter(last_heartbeat__lt=cutoff) | self.filter(last_heartbeat__isnull=True)


class TaskBotManager(models.Manager):
    def get_queryset(self) -> TaskBotQuerySet:
        return TaskBotQuerySet(self.model, using=self._db)

    def running(self) -> TaskBotQuerySet:
        return self.get_queryset().running()

    def idle(self) -> TaskBotQuerySet:
        return self.get_queryset().idle()

    def for_type(self, submission_type: str) -> TaskBotQuerySet:
        return self.get_queryset().for_type(submission_type)


# ---------------------------------------------------------------------------
# ModerationQueue
# ---------------------------------------------------------------------------

class ModerationQueueQuerySet(models.QuerySet):

    def pending(self) -> "ModerationQueueQuerySet":
        """Return queue items that are not assigned."""
        return self.filter(assigned_to__isnull=True)

    def assigned(self) -> "ModerationQueueQuerySet":
        """Return queue items that are assigned to someone."""
        return self.filter(assigned_to__isnull=False)

    def overdue(self) -> "ModerationQueueQuerySet":
        """Return queue items that are past their due date."""
        from django.utils import timezone
        return self.filter(due_at__lt=timezone.now())

    def by_priority(self) -> "ModerationQueueQuerySet":
        """Return queue items ordered by priority (highest first)."""
        from .choices import QueuePriority
        priority_order = models.Case(
            *[models.When(priority=p, then=i) for i, p in enumerate([
                QueuePriority.CRITICAL, QueuePriority.URGENT, QueuePriority.HIGH,
                QueuePriority.MEDIUM, QueuePriority.LOW
            ])]
        )
        return self.annotate(priority_order=priority_order).order_by("priority_order", "queued_at")

    def should_escalate(self) -> "ModerationQueueQuerySet":
        """Return queue items that should be auto-escalated."""
        from django.utils import timezone
        return self.filter(auto_escalate_at__lt=timezone.now())

    def for_moderator(self, user) -> "ModerationQueueQuerySet":
        """Return queue items assigned to a specific moderator."""
        return self.filter(assigned_to=user)

    def unassigned_for_type(self, submission_type: str) -> "ModerationQueueQuerySet":
        """Return unassigned queue items for a specific submission type."""
        return self.pending().filter(submission__submission_type=submission_type)


class ModerationQueueManager(models.Manager):
    def get_queryset(self) -> ModerationQueueQuerySet:
        return ModerationQueueQuerySet(self.model, using=self._db)

    def pending(self) -> ModerationQueueQuerySet:
        return self.get_queryset().pending()

    def assigned(self) -> ModerationQueueQuerySet:
        return self.get_queryset().assigned()

    def overdue(self) -> ModerationQueueQuerySet:
        return self.get_queryset().overdue()

    def by_priority(self) -> ModerationQueueQuerySet:
        return self.get_queryset().by_priority()

    def should_escalate(self) -> ModerationQueueQuerySet:
        return self.get_queryset().should_escalate()

    def for_moderator(self, user) -> ModerationQueueQuerySet:
        return self.get_queryset().for_moderator(user)

    def unassigned_for_type(self, submission_type: str) -> ModerationQueueQuerySet:
        return self.get_queryset().unassigned_for_type(submission_type)


# ---------------------------------------------------------------------------
# ModerationDecision
# ---------------------------------------------------------------------------

class ModerationDecisionQuerySet(models.QuerySet):

    def automated(self) -> "ModerationDecisionQuerySet":
        """Return decisions made by AI/automation."""
        return self.filter(is_automated=True)

    def human(self) -> "ModerationDecisionQuerySet":
        """Return decisions made by humans."""
        return self.filter(is_automated=False)

    def by_type(self, decision_type: str) -> "ModerationDecisionQuerySet":
        """Return decisions of a specific type."""
        return self.filter(decision_type=decision_type)

    def recent(self, days: int = 7) -> "ModerationDecisionQuerySet":
        """Return decisions from the last N days."""
        from django.utils import timezone
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(decided_at__gte=cutoff)

    def by_decider(self, user) -> "ModerationDecisionQuerySet":
        """Return decisions made by a specific user."""
        return self.filter(decided_by=user)

    def for_submission(self, submission_id: str) -> "ModerationDecisionQuerySet":
        """Return decisions for a specific submission."""
        return self.filter(submission_id=submission_id)
    def get_queue_items_for_moderator(self, moderator):
        return self.get_queryset().filter(assigned_to=moderator, completed_at__isnull=True)

    def get_unassigned_items(self):
        return self.get_queryset().filter(assigned_to__isnull=True, completed_at__isnull=True)

    def get_overdue_items(self):
        from django.utils import timezone
        cutoff = timezone.now() - timezone.timedelta(hours=24)
        return self.get_queryset().filter(queued_at__lt=cutoff, completed_at__isnull=True)



class ModerationDecisionManager(models.Manager):
    def get_queryset(self) -> ModerationDecisionQuerySet:
        return ModerationDecisionQuerySet(self.model, using=self._db)

    def automated(self) -> ModerationDecisionQuerySet:
        return self.get_queryset().automated()

    def human(self) -> ModerationDecisionQuerySet:
        return self.get_queryset().human()

    def by_type(self, decision_type: str) -> ModerationDecisionQuerySet:
        return self.get_queryset().by_type(decision_type)

    def recent(self, days: int = 7) -> ModerationDecisionQuerySet:
        return self.get_queryset().recent(days)

    def by_decider(self, user) -> ModerationDecisionQuerySet:
        return self.get_queryset().by_decider(user)

    def for_submission(self, submission_id: str) -> ModerationDecisionQuerySet:
        return self.get_queryset().for_submission(submission_id)


# ---------------------------------------------------------------------------
# ModerationAppeal
# ---------------------------------------------------------------------------

class ModerationAppealQuerySet(models.QuerySet):

    def pending(self) -> "ModerationAppealQuerySet":
        """Return appeals waiting for review."""
        from .choices import AppealStatus
        return self.filter(status__in=[AppealStatus.PENDING, AppealStatus.UNDER_REVIEW])

    def resolved(self) -> "ModerationAppealQuerySet":
        """Return resolved appeals."""
        from .choices import AppealStatus
        return self.filter(status__in=[AppealStatus.APPROVED, AppealStatus.REJECTED, AppealStatus.CLOSED])

    def successful(self) -> "ModerationAppealQuerySet":
        """Return successful appeals."""
        from .choices import AppealStatus
        return self.filter(status=AppealStatus.APPROVED)

    def by_reviewer(self, user) -> "ModerationAppealQuerySet":
        """Return appeals reviewed by a specific user."""
        return self.filter(reviewed_by=user)

    def for_appellant(self, user) -> "ModerationAppealQuerySet":
        """Return appeals filed by a specific user."""
        return self.filter(user=user)

    def recent(self, days: int = 30) -> "ModerationAppealQuerySet":
        """Return appeals from the last N days."""
        from django.utils import timezone
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(created_at__gte=cutoff)


class ModerationAppealManager(models.Manager):
    def get_queryset(self) -> ModerationAppealQuerySet:
        return ModerationAppealQuerySet(self.model, using=self._db)

    def pending(self) -> ModerationAppealQuerySet:
        return self.get_queryset().pending()

    def resolved(self) -> ModerationAppealQuerySet:
        return self.get_queryset().resolved()

    def successful(self) -> ModerationAppealQuerySet:
        return self.get_queryset().successful()

    def by_reviewer(self, user) -> ModerationAppealQuerySet:
        return self.get_queryset().by_reviewer(user)

    def for_appellant(self, user) -> ModerationAppealQuerySet:
        return self.get_queryset().for_appellant(user)

    def recent(self, days: int = 30) -> ModerationAppealQuerySet:
        return self.get_queryset().recent(days)


# ---------------------------------------------------------------------------
# MLModelVersion
# ---------------------------------------------------------------------------

class MLModelVersionQuerySet(models.QuerySet):

    def active(self) -> "MLModelVersionQuerySet":
        """Return currently active model versions."""
        return self.filter(is_active=True)

    def deployed(self) -> "MLModelVersionQuerySet":
        """Return deployed model versions."""
        return self.exclude(deployed_at__isnull=True)

    def by_type(self, model_type: str) -> "MLModelVersionQuerySet":
        """Return models of a specific type."""
        return self.filter(model_type=model_type)

    def training(self) -> "MLModelVersionQuerySet":
        """Return models currently being trained."""
        from .choices import ModelTrainingStatus
        return self.filter(status=ModelTrainingStatus.TRAINING)

    def failed(self) -> "MLModelVersionQuerySet":
        """Return failed model versions."""
        from .choices import ModelTrainingStatus
        return self.filter(status=ModelTrainingStatus.FAILED)

    def by_accuracy(self, min_accuracy: float = 0.0) -> "MLModelVersionQuerySet":
        """Return models with accuracy >= min_accuracy."""
        return self.filter(accuracy__gte=min_accuracy)

    def recent(self, days: int = 30) -> "MLModelVersionQuerySet":
        """Return model versions from the last N days."""
        from django.utils import timezone
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(created_at__gte=cutoff)


class MLModelVersionManager(models.Manager):
    def get_queryset(self) -> MLModelVersionQuerySet:
        return MLModelVersionQuerySet(self.model, using=self._db)

    def active(self) -> MLModelVersionQuerySet:
        return self.get_queryset().active()

    def deployed(self) -> MLModelVersionQuerySet:
        return self.get_queryset().deployed()

    def by_type(self, model_type: str) -> MLModelVersionQuerySet:
        return self.get_queryset().by_type(model_type)

    def training(self) -> MLModelVersionQuerySet:
        return self.get_queryset().training()

    def failed(self) -> MLModelVersionQuerySet:
        return self.get_queryset().failed()

    def by_accuracy(self, min_accuracy: float = 0.0) -> MLModelVersionQuerySet:
        return self.get_queryset().by_accuracy(min_accuracy)

    def recent(self, days: int = 30) -> MLModelVersionQuerySet:
        return self.get_queryset().recent(days)

    def get_active_model(self, model_type: str) -> "MLModelVersion":
        """Get the currently active model for a specific type."""
        return self.active().by_type(model_type).first()


# ---------------------------------------------------------------------------
# ContentSignal
# ---------------------------------------------------------------------------

class ContentSignalQuerySet(models.QuerySet):

    def unprocessed(self) -> "ContentSignalQuerySet":
        """Return signals that haven't been processed yet."""
        return self.filter(processed=False)

    def processed(self) -> "ContentSignalQuerySet":
        """Return signals that have been processed."""
        return self.filter(processed=True)

    def positive(self) -> "ContentSignalQuerySet":
        """Return positive signals (indicating problematic content)."""
        return self.filter(is_positive=True)

    def negative(self) -> "ContentSignalQuerySet":
        """Return negative signals (indicating safe content)."""
        return self.filter(is_positive=False)

    def by_type(self, signal_type: str) -> "ContentSignalQuerySet":
        """Return signals of a specific type."""
        return self.filter(signal_type=signal_type)

    def by_severity(self, severity: str) -> "ContentSignalQuerySet":
        """Return signals of a specific severity level."""
        return self.filter(severity=severity)

    def high_impact(self, min_weight: float = 5.0) -> "ContentSignalQuerySet":
        """Return signals with high impact (weight >= min_weight)."""
        return self.filter(weight__gte=min_weight)

    def confident(self, min_confidence: float = 0.8) -> "ContentSignalQuerySet":
        """Return signals with high confidence."""
        return self.filter(confidence__gte=min_confidence)

    def for_submission(self, submission_id: str) -> "ContentSignalQuerySet":
        """Return signals for a specific submission."""
        return self.filter(submission_id=submission_id)

    def recent(self, hours: int = 24) -> "ContentSignalQuerySet":
        """Return signals from the last N hours."""
        from django.utils import timezone
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        return self.filter(created_at__gte=cutoff)


class ContentSignalManager(models.Manager):
    def get_queryset(self) -> ContentSignalQuerySet:
        return ContentSignalQuerySet(self.model, using=self._db)

    def unprocessed(self) -> ContentSignalQuerySet:
        return self.get_queryset().unprocessed()

    def processed(self) -> ContentSignalQuerySet:
        return self.get_queryset().processed()

    def positive(self) -> ContentSignalQuerySet:
        return self.get_queryset().positive()

    def negative(self) -> ContentSignalQuerySet:
        return self.get_queryset().negative()

    def by_type(self, signal_type: str) -> ContentSignalQuerySet:
        return self.get_queryset().by_type(signal_type)

    def by_severity(self, severity: str) -> ContentSignalQuerySet:
        return self.get_queryset().by_severity(severity)

    def high_impact(self, min_weight: float = 5.0) -> ContentSignalQuerySet:
        return self.get_queryset().high_impact(min_weight)

    def confident(self, min_confidence: float = 0.8) -> ContentSignalQuerySet:
        return self.get_queryset().confident(min_confidence)

    def for_submission(self, submission_id: str) -> ContentSignalQuerySet:
        return self.get_queryset().for_submission(submission_id)

    def recent(self, hours: int = 24) -> ContentSignalQuerySet:
        return self.get_queryset().recent(hours)
