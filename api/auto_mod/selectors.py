# =============================================================================
# auto_mod/selectors.py
# =============================================================================

"""
Domain selectors for auto moderation system.
Provides query building and data selection capabilities following Domain-Driven Design patterns.
"""

import logging
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import models
from django.core.cache import cache

from .models import (
    SuspiciousSubmission, ModerationDecision, ModerationAppeal,
    ModerationQueue, TaskBot, AutoApprovalRule, MLModelVersion,
    ContentSignal, ProofScanner
)
from .choices import ModerationStatus, AppealStatus, BotStatus, QueuePriority

logger = logging.getLogger(__name__)


class BaseSelector:
    """Base class for all domain selectors."""
    
    model_class = None
    default_select_related = []
    default_prefetch_related = []
    
    def __init__(self):
        self.queryset = self.model_class.objects.all()
        self._applied_filters = {}
        self._applied_ordering = []
    
    def get_queryset(self) -> models.QuerySet:
        """Get the current queryset with default optimizations."""
        if self.default_select_related:
            self.queryset = self.queryset.select_related(*self.default_select_related)
        
        if self.default_prefetch_related:
            self.queryset = self.queryset.prefetch_related(*self.default_prefetch_related)
        
        return self.queryset
    
    def filter_by(self, **kwargs) -> 'BaseSelector':
        """Apply filters to the queryset."""
        self.queryset = self.queryset.filter(**kwargs)
        self._applied_filters.update(kwargs)
        return self
    
    def exclude_by(self, **kwargs) -> 'BaseSelector':
        """Apply exclusions to the queryset."""
        self.queryset = self.queryset.exclude(**kwargs)
        return self
    
    def order_by(self, *fields) -> 'BaseSelector':
        """Apply ordering to the queryset."""
        self.queryset = self.queryset.order_by(*fields)
        self._applied_ordering.extend(fields)
        return self
    
    def limit(self, count: int) -> 'BaseSelector':
        """Limit the number of results."""
        self.queryset = self.queryset[:count]
        return self
    
    def first(self) -> Optional[Any]:
        """Get the first result."""
        return self.get_queryset().first()
    
    def all(self) -> List[Any]:
        """Get all results."""
        return list(self.get_queryset())
    
    def count(self) -> int:
        """Get the count of results."""
        return self.get_queryset().count()
    
    def exists(self) -> bool:
        """Check if any results exist."""
        return self.get_queryset().exists()


class SuspiciousSubmissionSelector(BaseSelector):
    """Selector for SuspiciousSubmission queries."""
    
    model_class = SuspiciousSubmission
    default_select_related = ['user']
    default_prefetch_related = ['decisions', 'signals']
    
    def by_status(self, status: Union[ModerationStatus, str, List]) -> 'SuspiciousSubmissionSelector':
        """Filter by moderation status."""
        if isinstance(status, list):
            self.queryset = self.queryset.filter(status__in=status)
        else:
            self.queryset = self.queryset.filter(status=status)
        return self
    
    def by_submission_type(self, submission_type: str) -> 'SuspiciousSubmissionSelector':
        """Filter by submission type."""
        self.queryset = self.queryset.filter(submission_type=submission_type)
        return self
    
    def by_user(self, user_id: Union[str, int]) -> 'SuspiciousSubmissionSelector':
        """Filter by user."""
        self.queryset = self.queryset.filter(user_id=user_id)
        return self
    
    def by_risk_score_range(self, min_score: float = None, max_score: float = None) -> 'SuspiciousSubmissionSelector':
        """Filter by risk score range."""
        if min_score is not None:
            self.queryset = self.queryset.filter(risk_score__gte=min_score)
        if max_score is not None:
            self.queryset = self.queryset.filter(risk_score__lte=max_score)
        return self
    
    def by_ai_confidence_range(self, min_confidence: float = None, max_confidence: float = None) -> 'SuspiciousSubmissionSelector':
        """Filter by AI confidence range."""
        if min_confidence is not None:
            self.queryset = self.queryset.filter(ai_confidence__gte=min_confidence)
        if max_confidence is not None:
            self.queryset = self.queryset.filter(ai_confidence__lte=max_confidence)
        return self
    
    def by_flag_reason(self, flag_reason: str) -> 'SuspiciousSubmissionSelector':
        """Filter by flag reason."""
        self.queryset = self.queryset.filter(flag_reason=flag_reason)
        return self
    
    def by_date_range(self, start_date: datetime = None, end_date: datetime = None) -> 'SuspiciousSubmissionSelector':
        """Filter by creation date range."""
        if start_date:
            self.queryset = self.queryset.filter(created_at__gte=start_date)
        if end_date:
            self.queryset = self.queryset.filter(created_at__lte=end_date)
        return self
    
    def by_recent(self, days: int = 7) -> 'SuspiciousSubmissionSelector':
        """Filter by recent submissions (last N days)."""
        start_date = timezone.now() - timedelta(days=days)
        return self.by_date_range(start_date=start_date)
    
    def with_decisions(self) -> 'SuspiciousSubmissionSelector':
        """Filter submissions that have decisions."""
        self.queryset = self.queryset.filter(decisions__isnull=False).distinct()
        return self
    
    def without_decisions(self) -> 'SuspiciousSubmissionSelector':
        """Filter submissions without decisions."""
        self.queryset = self.queryset.filter(decisions__isnull=True)
        return self
    
    def with_appeals(self) -> 'SuspiciousSubmissionSelector':
        """Filter submissions that have appeals."""
        self.queryset = self.queryset.filter(decisions__appeals__isnull=False).distinct()
        return self
    
    def high_risk(self, min_score: float = 7.0) -> 'SuspiciousSubmissionSelector':
        """Filter high risk submissions."""
        return self.by_risk_score_range(min_score=min_score)
    
    def low_confidence(self, max_confidence: float = 0.5) -> 'SuspiciousSubmissionSelector':
        """Filter low confidence submissions."""
        return self.by_ai_confidence_range(max_confidence=max_confidence)
    
    def pending_review(self) -> 'SuspiciousSubmissionSelector':
        """Filter submissions pending review."""
        return self.by_status(ModerationStatus.PENDING)
    
    def approved(self) -> 'SuspiciousSubmissionSelector':
        """Filter approved submissions."""
        return self.by_status(ModerationStatus.APPROVED)
    
    def rejected(self) -> 'SuspiciousSubmissionSelector':
        """Filter rejected submissions."""
        return self.by_status(ModerationStatus.REJECTED)
    
    def escalated(self) -> 'SuspiciousSubmissionSelector':
        """Filter escalated submissions."""
        return self.by_status(ModerationStatus.ESCALATED)


class ModerationDecisionSelector(BaseSelector):
    """Selector for ModerationDecision queries."""
    
    model_class = ModerationDecision
    default_select_related = ['submission', 'decided_by', 'applied_rule']
    default_prefetch_related = ['appeals']
    
    def by_submission(self, submission_id: str) -> 'ModerationDecisionSelector':
        """Filter by submission."""
        self.queryset = self.queryset.filter(submission_id=submission_id)
        return self
    
    def by_decider(self, decider_id: Union[str, int]) -> 'ModerationDecisionSelector':
        """Filter by who made the decision."""
        self.queryset = self.queryset.filter(decider_id=decider_id)
        return self
    
    def by_decision_type(self, decision_type: str) -> 'ModerationDecisionSelector':
        """Filter by decision type."""
        self.queryset = self.queryset.filter(decision_type=decision_type)
        return self
    
    def by_automated(self, is_automated: bool) -> 'ModerationDecisionSelector':
        """Filter by automated vs manual decisions."""
        self.queryset = self.queryset.filter(is_automated=is_automated)
        return self
    
    def by_confidence_range(self, min_confidence: float = None, max_confidence: float = None) -> 'ModerationDecisionSelector':
        """Filter by confidence range."""
        if min_confidence is not None:
            self.queryset = self.queryset.filter(confidence__gte=min_confidence)
        if max_confidence is not None:
            self.queryset = self.queryset.filter(confidence__lte=max_confidence)
        return self
    
    def by_date_range(self, start_date: datetime = None, end_date: datetime = None) -> 'ModerationDecisionSelector':
        """Filter by decision date range."""
        if start_date:
            self.queryset = self.queryset.filter(decided_at__gte=start_date)
        if end_date:
            self.queryset = self.queryset.filter(decided_at__lte=end_date)
        return self
    
    def by_recent(self, days: int = 7) -> 'ModerationDecisionSelector':
        """Filter recent decisions (last N days)."""
        start_date = timezone.now() - timedelta(days=days)
        return self.by_date_range(start_date=start_date)
    
    def with_appeals(self) -> 'ModerationDecisionSelector':
        """Filter decisions that have appeals."""
        self.queryset = self.queryset.filter(appeals__isnull=False).distinct()
        return self
    
    def without_appeals(self) -> 'ModerationDecisionSelector':
        """Filter decisions without appeals."""
        self.queryset = self.queryset.filter(appeals__isnull=True)
        return self
    
    def automated(self) -> 'ModerationDecisionSelector':
        """Filter automated decisions."""
        return self.by_automated(True)
    
    def manual(self) -> 'ModerationDecisionSelector':
        """Filter manual decisions."""
        return self.by_automated(False)
    
    def high_confidence(self, min_confidence: float = 0.8) -> 'ModerationDecisionSelector':
        """Filter high confidence decisions."""
        return self.by_confidence_range(min_confidence=min_confidence)
    
    def low_confidence(self, max_confidence: float = 0.5) -> 'ModerationDecisionSelector':
        """Filter low confidence decisions."""
        return self.by_confidence_range(max_confidence=max_confidence)


class ModerationAppealSelector(BaseSelector):
    """Selector for ModerationAppeal queries."""
    
    model_class = ModerationAppeal
    default_select_related = ['user', 'original_decision', 'submission', 'reviewed_by']
    
    def by_status(self, status: Union[AppealStatus, str, List]) -> 'ModerationAppealSelector':
        """Filter by appeal status."""
        if isinstance(status, list):
            self.queryset = self.queryset.filter(status__in=status)
        else:
            self.queryset = self.queryset.filter(status=status)
        return self
    
    def by_user(self, user_id: Union[str, int]) -> 'ModerationAppealSelector':
        """Filter by user who made the appeal."""
        self.queryset = self.queryset.filter(user_id=user_id)
        return self
    
    def by_original_decision(self, decision_id: str) -> 'ModerationAppealSelector':
        """Filter by original decision being appealed."""
        self.queryset = self.queryset.filter(original_decision_id=decision_id)
        return self
    
    def by_reviewer(self, reviewer_id: Union[str, int]) -> 'ModerationAppealSelector':
        """Filter by reviewer."""
        self.queryset = self.queryset.filter(reviewer_id=reviewer_id)
        return self
    
    def by_appeal_type(self, appeal_type: str) -> 'ModerationAppealSelector':
        """Filter by appeal type."""
        self.queryset = self.queryset.filter(appeal_type=appeal_type)
        return self
    
    def by_date_range(self, start_date: datetime = None, end_date: datetime = None) -> 'ModerationAppealSelector':
        """Filter by appeal date range."""
        if start_date:
            self.queryset = self.queryset.filter(created_at__gte=start_date)
        if end_date:
            self.queryset = self.queryset.filter(created_at__lte=end_date)
        return self
    
    def by_recent(self, days: int = 7) -> 'ModerationAppealSelector':
        """Filter recent appeals (last N days)."""
        start_date = timezone.now() - timedelta(days=days)
        return self.by_date_range(start_date=start_date)
    
    def pending_review(self) -> 'ModerationAppealSelector':
        """Filter appeals pending review."""
        return self.by_status(AppealStatus.PENDING)
    
    def approved(self) -> 'ModerationAppealSelector':
        """Filter approved appeals."""
        return self.by_status(AppealStatus.APPROVED)
    
    def rejected(self) -> 'ModerationAppealSelector':
        """Filter rejected appeals."""
        return self.by_status(AppealStatus.REJECTED)
    
    def escalated(self) -> 'ModerationAppealSelector':
        """Filter escalated appeals."""
        return self.by_status(AppealStatus.ESCALATED)


class ModerationQueueSelector(BaseSelector):
    """Selector for ModerationQueue queries."""
    
    model_class = ModerationQueue
    default_select_related = ['submission', 'assigned_to', 'assigned_by']
    
    def by_status(self, status: str) -> 'ModerationQueueSelector':
        """Filter by queue status."""
        self.queryset = self.queryset.filter(status=status)
        return self
    
    def by_priority(self, priority: Union[QueuePriority, str, List]) -> 'ModerationQueueSelector':
        """Filter by priority."""
        if isinstance(priority, list):
            self.queryset = self.queryset.filter(priority__in=priority)
        else:
            self.queryset = self.queryset.filter(priority=priority)
        return self
    
    def by_assigned_to(self, assignee_id: Union[str, int]) -> 'ModerationQueueSelector':
        """Filter by assigned moderator."""
        self.queryset = self.queryset.filter(assigned_to_id=assignee_id)
        return self
    
    def by_unassigned(self) -> 'ModerationQueueSelector':
        """Filter unassigned queue items."""
        self.queryset = self.queryset.filter(assigned_to__isnull=True)
        return self
    
    def by_escalation_level(self, level: int) -> 'ModerationQueueSelector':
        """Filter by escalation level."""
        self.queryset = self.queryset.filter(escalation_level=level)
        return self
    
    def by_overdue(self, overdue: bool = True) -> 'ModerationQueueSelector':
        """Filter overdue items."""
        if overdue:
            self.queryset = self.queryset.filter(due_date__lt=timezone.now())
        else:
            self.queryset = self.queryset.filter(
                models.Q(due_date__gte=timezone.now()) | models.Q(due_date__isnull=True)
            )
        return self
    
    def high_priority(self) -> 'ModerationQueueSelector':
        """Filter high priority items."""
        return self.by_priority([QueuePriority.HIGH, QueuePriority.CRITICAL])
    
    def critical_priority(self) -> 'ModerationQueueSelector':
        """Filter critical priority items."""
        return self.by_priority(QueuePriority.CRITICAL)
    
    def unassigned(self) -> 'ModerationQueueSelector':
        """Filter unassigned items."""
        return self.by_unassigned()
    
    def overdue(self) -> 'ModerationQueueSelector':
        """Filter overdue items."""
        return self.by_overdue(True)


class TaskBotSelector(BaseSelector):
    """Selector for TaskBot queries."""
    
    model_class = TaskBot
    default_select_related = ['created_by', 'updated_by']
    
    def by_status(self, status: Union[BotStatus, str, List]) -> 'TaskBotSelector':
        """Filter by bot status."""
        if isinstance(status, list):
            self.queryset = self.queryset.filter(status__in=status)
        else:
            self.queryset = self.queryset.filter(status=status)
        return self
    
    def by_bot_type(self, bot_type: str) -> 'TaskBotSelector':
        """Filter by bot type."""
        self.queryset = self.queryset.filter(bot_type=bot_type)
        return self
    
    def by_active(self, is_active: bool = True) -> 'TaskBotSelector':
        """Filter by active status."""
        self.queryset = self.queryset.filter(is_active=is_active)
        return self
    
    def by_performance_score_range(self, min_score: float = None, max_score: float = None) -> 'TaskBotSelector':
        """Filter by performance score range."""
        if min_score is not None:
            self.queryset = self.queryset.filter(performance_score__gte=min_score)
        if max_score is not None:
            self.queryset = self.queryset.filter(performance_score__lte=max_score)
        return self
    
    def running(self) -> 'TaskBotSelector':
        """Filter running bots."""
        return self.by_status(BotStatus.RUNNING)
    
    def idle(self) -> 'TaskBotSelector':
        """Filter idle bots."""
        return self.by_status(BotStatus.IDLE)
    
    def error(self) -> 'TaskBotSelector':
        """Filter bots with errors."""
        return self.by_status(BotStatus.ERROR)
    
    def active(self) -> 'TaskBotSelector':
        """Filter active bots."""
        return self.by_active(True)
    
    def high_performance(self, min_score: float = 0.8) -> 'TaskBotSelector':
        """Filter high performance bots."""
        return self.by_performance_score_range(min_score=min_score)


class AutoApprovalRuleSelector(BaseSelector):
    """Selector for AutoApprovalRule queries."""
    
    model_class = AutoApprovalRule
    default_select_related = ['created_by', 'updated_by']
    
    def by_active(self, is_active: bool = True) -> 'AutoApprovalRuleSelector':
        """Filter by active status."""
        self.queryset = self.queryset.filter(is_active=is_active)
        return self
    
    def by_rule_type(self, rule_type: str) -> 'AutoApprovalRuleSelector':
        """Filter by rule type."""
        self.queryset = self.queryset.filter(rule_type=rule_type)
        return self
    
    def by_confidence_threshold_range(self, min_threshold: float = None, max_threshold: float = None) -> 'AutoApprovalRuleSelector':
        """Filter by confidence threshold range."""
        if min_threshold is not None:
            self.queryset = self.queryset.filter(confidence_threshold__gte=min_threshold)
        if max_threshold is not None:
            self.queryset = self.queryset.filter(confidence_threshold__lte=max_threshold)
        return self
    
    def by_submission_type(self, submission_type: str) -> 'AutoApprovalRuleSelector':
        """Filter by submission type."""
        self.queryset = self.queryset.filter(submission_type=submission_type)
        return self
    
    def active(self) -> 'AutoApprovalRuleSelector':
        """Filter active rules."""
        return self.by_active(True)
    
    def high_threshold(self, min_threshold: float = 0.8) -> 'AutoApprovalRuleSelector':
        """Filter rules with high confidence threshold."""
        return self.by_confidence_threshold_range(min_threshold=min_threshold)


class MLModelVersionSelector(BaseSelector):
    """Selector for MLModelVersion queries."""
    
    model_class = MLModelVersion
    default_select_related = ['created_by']
    
    def by_model_type(self, model_type: str) -> 'MLModelVersionSelector':
        """Filter by model type."""
        self.queryset = self.queryset.filter(model_type=model_type)
        return self
    
    def by_status(self, status: str) -> 'MLModelVersionSelector':
        """Filter by model status."""
        self.queryset = self.queryset.filter(status=status)
        return self
    
    def by_accuracy_range(self, min_accuracy: float = None, max_accuracy: float = None) -> 'MLModelVersionSelector':
        """Filter by accuracy range."""
        if min_accuracy is not None:
            self.queryset = self.queryset.filter(accuracy__gte=min_accuracy)
        if max_accuracy is not None:
            self.queryset = self.queryset.filter(accuracy__lte=max_accuracy)
        return self
    
    def by_is_production(self, is_production: bool = True) -> 'MLModelVersionSelector':
        """Filter by production status."""
        self.queryset = self.queryset.filter(is_production=is_production)
        return self
    
    def production(self) -> 'MLModelVersionSelector':
        """Filter production models."""
        return self.by_is_production(True)
    
    def high_accuracy(self, min_accuracy: float = 0.8) -> 'MLModelVersionSelector':
        """Filter high accuracy models."""
        return self.by_accuracy_range(min_accuracy=min_accuracy)


class ContentSignalSelector(BaseSelector):
    """Selector for ContentSignal queries."""
    
    model_class = ContentSignal
    default_select_related = ['submission', 'detected_by']
    
    def by_signal_type(self, signal_type: str) -> 'ContentSignalSelector':
        """Filter by signal type."""
        self.queryset = self.queryset.filter(signal_type=signal_type)
        return self
    
    def by_severity(self, severity: str) -> 'ContentSignalSelector':
        """Filter by severity."""
        self.queryset = self.queryset.filter(severity=severity)
        return self
    
    def by_submission(self, submission_id: str) -> 'ContentSignalSelector':
        """Filter by submission."""
        self.queryset = self.queryset.filter(submission_id=submission_id)
        return self
    
    def by_confidence_range(self, min_confidence: float = None, max_confidence: float = None) -> 'ContentSignalSelector':
        """Filter by confidence range."""
        if min_confidence is not None:
            self.queryset = self.queryset.filter(confidence__gte=min_confidence)
        if max_confidence is not None:
            self.queryset = self.queryset.filter(confidence__lte=max_confidence)
        return self
    
    def high_severity(self) -> 'ContentSignalSelector':
        """Filter high severity signals."""
        return self.filter_by(severity='high')
    
    def high_confidence(self, min_confidence: float = 0.8) -> 'ContentSignalSelector':
        """Filter high confidence signals."""
        return self.by_confidence_range(min_confidence=min_confidence)


class ProofScannerSelector(BaseSelector):
    """Selector for ProofScanner queries."""
    
    model_class = ProofScanner
    default_select_related = ['created_by', 'updated_by']
    
    def by_scanner_type(self, scanner_type: str) -> 'ProofScannerSelector':
        """Filter by scanner type."""
        self.queryset = self.queryset.filter(scanner_type=scanner_type)
        return self
    
    def by_active(self, is_active: bool = True) -> 'ProofScannerSelector':
        """Filter by active status."""
        self.queryset = self.queryset.filter(is_active=is_active)
        return self
    
    def by_performance_score_range(self, min_score: float = None, max_score: float = None) -> 'ProofScannerSelector':
        """Filter by performance score range."""
        if min_score is not None:
            self.queryset = self.queryset.filter(performance_score__gte=min_score)
        if max_score is not None:
            self.queryset = self.queryset.filter(performance_score__lte=max_score)
        return self
    
    def active(self) -> 'ProofScannerSelector':
        """Filter active scanners."""
        return self.by_active(True)
    
    def high_performance(self, min_score: float = 0.8) -> 'ProofScannerSelector':
        """Filter high performance scanners."""
        return self.by_performance_score_range(min_score=min_score)


# Selector factory and utilities
class SelectorFactory:
    """Factory for creating selector instances."""
    
    _selectors = {
        'submissions': SuspiciousSubmissionSelector,
        'decisions': ModerationDecisionSelector,
        'appeals': ModerationAppealSelector,
        'queue': ModerationQueueSelector,
        'bots': TaskBotSelector,
        'rules': AutoApprovalRuleSelector,
        'models': MLModelVersionSelector,
        'signals': ContentSignalSelector,
        'scanners': ProofScannerSelector,
    }
    
    @classmethod
    def create(cls, selector_type: str) -> BaseSelector:
        """Create a selector instance."""
        if selector_type not in cls._selectors:
            raise ValueError(f"Unknown selector type: {selector_type}")
        
        return cls._selectors[selector_type]()
    
    @classmethod
    def submissions(cls) -> SuspiciousSubmissionSelector:
        """Create submissions selector."""
        return cls.create('submissions')
    
    @classmethod
    def decisions(cls) -> ModerationDecisionSelector:
        """Create decisions selector."""
        return cls.create('decisions')
    
    @classmethod
    def appeals(cls) -> ModerationAppealSelector:
        """Create appeals selector."""
        return cls.create('appeals')
    
    @classmethod
    def queue(cls) -> ModerationQueueSelector:
        """Create queue selector."""
        return cls.create('queue')
    
    @classmethod
    def bots(cls) -> TaskBotSelector:
        """Create bots selector."""
        return cls.create('bots')
    
    @classmethod
    def rules(cls) -> AutoApprovalRuleSelector:
        """Create rules selector."""
        return cls.create('rules')
    
    @classmethod
    def models(cls) -> MLModelVersionSelector:
        """Create models selector."""
        return cls.create('models')
    
    @classmethod
    def signals(cls) -> ContentSignalSelector:
        """Create signals selector."""
        return cls.create('signals')
    
    @classmethod
    def scanners(cls) -> ProofScannerSelector:
        """Create scanners selector."""
        return cls.create('scanners')


# Cached selectors for performance
class CachedSelector:
    """Wrapper for cached selector results."""
    
    def __init__(self, selector: BaseSelector, cache_timeout: int = 300):
        self.selector = selector
        self.cache_timeout = cache_timeout
    
    def _generate_cache_key(self, method_name: str, **kwargs) -> str:
        """Generate cache key for method call."""
        key_parts = [
            f"selector:{self.selector.model_class.__name__.lower()}",
            f"method:{method_name}",
        ]
        
        # Add filters to key
        for key, value in self.selector._applied_filters.items():
            key_parts.append(f"{key}:{value}")
        
        # Add ordering to key
        if self.selector._applied_ordering:
            key_parts.append(f"order:{','.join(self.selector._applied_ordering)}")
        
        # Add method arguments
        for key, value in kwargs.items():
            key_parts.append(f"{key}:{value}")
        
        return ':'.join(key_parts)
    
    def count(self, **kwargs) -> int:
        """Get cached count."""
        cache_key = self._generate_cache_key('count', **kwargs)
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            return cached_result
        
        result = self.selector.count()
        cache.set(cache_key, result, self.cache_timeout)
        return result
    
    def first(self, **kwargs) -> Optional[Any]:
        """Get cached first result."""
        cache_key = self._generate_cache_key('first', **kwargs)
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            return cached_result
        
        result = self.selector.first()
        cache.set(cache_key, result, self.cache_timeout)
        return result
    
    def all(self, **kwargs) -> List[Any]:
        """Get cached all results."""
        cache_key = self._generate_cache_key('all', **kwargs)
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            return cached_result
        
        result = self.selector.all()
        cache.set(cache_key, result, self.cache_timeout)
        return result


# Convenience functions
def get_submissions_selector() -> SuspiciousSubmissionSelector:
    """Get submissions selector."""
    return SelectorFactory.submissions()


def get_decisions_selector() -> ModerationDecisionSelector:
    """Get decisions selector."""
    return SelectorFactory.decisions()


def get_appeals_selector() -> ModerationAppealSelector:
    """Get appeals selector."""
    return SelectorFactory.appeals()


def get_queue_selector() -> ModerationQueueSelector:
    """Get queue selector."""
    return SelectorFactory.queue()


def get_bots_selector() -> TaskBotSelector:
    """Get bots selector."""
    return SelectorFactory.bots()


def get_rules_selector() -> AutoApprovalRuleSelector:
    """Get rules selector."""
    return SelectorFactory.rules()


def get_models_selector() -> MLModelVersionSelector:
    """Get models selector."""
    return SelectorFactory.models()


def get_signals_selector() -> ContentSignalSelector:
    """Get signals selector."""
    return SelectorFactory.signals()


def get_scanners_selector() -> ProofScannerSelector:
    """Get scanners selector."""
    return SelectorFactory.scanners()


def cached_selector(selector_type: str, cache_timeout: int = 300) -> CachedSelector:
    """Create a cached selector."""
    selector = SelectorFactory.create(selector_type)
    return CachedSelector(selector, cache_timeout)


# Query builder utilities
class QueryBuilder:
    """Builder for complex queries across multiple models."""
    
    def __init__(self):
        self.selectors = {}
        self.joins = []
        self.filters = {}
    
    def add_selector(self, name: str, selector: BaseSelector) -> 'QueryBuilder':
        """Add a selector to the builder."""
        self.selectors[name] = selector
        return self
    
    def join(self, from_selector: str, to_selector: str, field: str) -> 'QueryBuilder':
        """Add a join between selectors."""
        self.joins.append({
            'from': from_selector,
            'to': to_selector,
            'field': field
        })
        return self
    
    def filter(self, selector_name: str, **kwargs) -> 'QueryBuilder':
        """Add filters to a selector."""
        if selector_name not in self.filters:
            self.filters[selector_name] = {}
        self.filters[selector_name].update(kwargs)
        return self
    
    def build(self) -> Dict[str, Any]:
        """Build the query result."""
        results = {}
        
        for name, selector in self.selectors.items():
            # Apply filters
            if name in self.filters:
                selector.filter_by(**self.filters[name])
            
            # Get results
            results[name] = selector.all()
        
        # Apply joins (simplified implementation)
        for join in self.joins:
            from_results = results.get(join['from'], [])
            to_results = results.get(join['to'], [])
            
            # This would implement actual joining logic
            # For now, just return the individual results
        
        return results


# Initialize logging
logger.info("Selectors module initialized with domain selectors")
