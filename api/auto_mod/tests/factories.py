# =============================================================================
# auto_mod/tests/factories.py
# =============================================================================

import uuid
import factory
from django.contrib.auth import get_user_model
from django.utils import timezone
from factory.django import DjangoModelFactory

from ..choices import (
    BotStatus, FlagReason, ModerationStatus,
    RiskLevel, RuleAction, ScanType, SubmissionType,
)
from ..models import AutoApprovalRule, ProofScanner, SuspiciousSubmission, TaskBot

User = get_user_model()


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = factory.Sequence(lambda n: f"moduser_{n:04d}")
    email    = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "password")
    is_staff = False


class StaffUserFactory(UserFactory):
    is_staff = True


class AutoApprovalRuleFactory(DjangoModelFactory):
    class Meta:
        model = AutoApprovalRule

    name              = factory.Sequence(lambda n: f"Rule {n:04d}")
    description       = factory.Faker("sentence")
    submission_type   = SubmissionType.TASK_PROOF
    priority          = factory.Sequence(lambda n: (n % 99) + 1)
    conditions        = factory.LazyFunction(lambda: [
        {"field": "confidence", "operator": "gte", "value": 0.9}
    ])
    action            = RuleAction.APPROVE
    confidence_threshold = 0.90
    is_active         = True
    is_system         = False
    created_by        = factory.SubFactory(StaffUserFactory)
    metadata          = factory.LazyFunction(dict)

    class Params:
        reject     = factory.Trait(action=RuleAction.REJECT)
        escalate   = factory.Trait(action=RuleAction.ESCALATE)
        inactive   = factory.Trait(is_active=False)
        system     = factory.Trait(is_system=True)


class SuspiciousSubmissionFactory(DjangoModelFactory):
    class Meta:
        model = SuspiciousSubmission

    content_type    = "tasks.taskproof"
    content_id      = factory.LazyFunction(lambda: str(uuid.uuid4()))
    submission_type = SubmissionType.TASK_PROOF
    submitted_by    = factory.SubFactory(UserFactory)
    status          = ModerationStatus.PENDING
    ai_confidence   = None
    risk_score      = None
    risk_level      = RiskLevel.LOW
    flag_reason     = FlagReason.OTHER
    ai_explanation  = ""
    scan_metadata   = factory.LazyFunction(dict)

    class Params:
        high_risk = factory.Trait(
            risk_level=RiskLevel.HIGH,
            risk_score=0.85,
            ai_confidence=0.88,
            status=ModerationStatus.HUMAN_REVIEW,
        )
        auto_approved = factory.Trait(
            status=ModerationStatus.AUTO_APPROVED,
            ai_confidence=0.95,
            risk_score=0.05,
            risk_level=RiskLevel.LOW,
        )
        auto_rejected = factory.Trait(
            status=ModerationStatus.AUTO_REJECTED,
            ai_confidence=0.92,
            risk_score=0.90,
            risk_level=RiskLevel.HIGH,
            flag_reason=FlagReason.FAKE_PROOF,
        )
        scanning = factory.Trait(status=ModerationStatus.SCANNING)


class ProofScannerFactory(DjangoModelFactory):
    class Meta:
        model = ProofScanner

    submission    = factory.SubFactory(SuspiciousSubmissionFactory)
    scan_type     = ScanType.TEXT
    input_text    = factory.Faker("paragraph")
    confidence    = 0.85
    is_flagged    = False
    labels        = factory.LazyFunction(lambda: ["clean_text"])
    ocr_text      = ""
    raw_result    = factory.LazyFunction(dict)
    error_message = ""
    duration_ms   = 120
    model_version = "auto_mod_text_v1:heuristic-v1"

    class Params:
        flagged = factory.Trait(
            is_flagged=True,
            confidence=0.30,
            labels=["spam", "low_quality"],
        )
        image   = factory.Trait(
            scan_type=ScanType.IMAGE,
            file_url="https://example.com/proof.jpg",
            input_text="",
        )
        failed  = factory.Trait(
            confidence=None,
            is_flagged=None,
            error_message="Connection timed out",
        )


class TaskBotFactory(DjangoModelFactory):
    class Meta:
        model = TaskBot
        django_get_or_create = ("name",)

    name            = factory.Sequence(lambda n: f"bot_{n:04d}")
    description     = factory.Faker("sentence")
    submission_type = SubmissionType.TASK_PROOF
    status          = BotStatus.IDLE
    config          = factory.LazyFunction(lambda: {"max_batch_size": 50, "process_interval": 30})
    assigned_to     = factory.SubFactory(StaffUserFactory)

    class Params:
        running = factory.Trait(
            status=BotStatus.RUNNING,
            last_heartbeat=factory.LazyFunction(timezone.now),
        )
        error   = factory.Trait(
            status=BotStatus.ERROR,
            retry_count=3,
            last_error="Connection refused",
        )
