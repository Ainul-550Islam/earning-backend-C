"""
auto_mod services package — single owner per responsibility.

One job = one owner:
  ModerationService    → orchestrates full scan → decision pipeline
  ScannerService       → runs image/text ML scanners
  RuleEngineService    → evaluates AutoApprovalRules
  SubmissionService    → SuspiciousSubmission CRUD & state
  BotService           → TaskBot lifecycle + scan initiation
  AppealService        → appeal lifecycle
  AutoApprovalService  → rule management, risk scoring, auto-decisions
  ContentSignalService → content signal detection
  MLModelService       → ML model version management
  ModerationQueueService → queue assignment, escalation, metrics
"""

from .ModerationService import (
    ModerationService,
    ScannerService,
    RuleEngineService,
    SubmissionService,
)
from .BotService import BotService
from .AppealService import AppealService
from .AutoApprovalService import AutoApprovalService
from .ContentSignalService import ContentSignalService
from .MLModelService import MLModelService
from .ModerationQueueService import ModerationQueueService

__all__ = [
    "ModerationService", "ScannerService", "RuleEngineService", "SubmissionService",
    "BotService", "AppealService", "AutoApprovalService", "ContentSignalService",
    "MLModelService", "ModerationQueueService",
]
