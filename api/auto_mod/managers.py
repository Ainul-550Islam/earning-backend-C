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
