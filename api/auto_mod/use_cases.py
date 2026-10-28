# =============================================================================
# auto_mod/use_cases.py
# =============================================================================

"""
Use cases for auto moderation system following Domain-Driven Design patterns.
Provides business logic orchestration without exposing implementation details.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache

from .models import (
    SuspiciousSubmission, ModerationDecision, ModerationAppeal,
    ModerationQueue, TaskBot, AutoApprovalRule, MLModelVersion
)
from .selectors import SelectorFactory
from .services import ModerationService, ScannerService
from .constants import (
    AUTO_APPROVE_THRESHOLD, AUTO_REJECT_THRESHOLD,
    HUMAN_REVIEW_LOWER, HUMAN_REVIEW_UPPER
)
from .exceptions import (
    ModerationError, ValidationError, ServiceUnavailableError
)

logger = logging.getLogger(__name__)


class BaseUseCase:
    """Base class for all use cases."""
    
    def __init__(self):
        self.selectors = SelectorFactory()
        self.moderation_service = ModerationService()
        self.scanner_service = ScannerService()
    
    def execute(self, *args, **kwargs) -> Any:
        """Execute the use case."""
        raise NotImplementedError("Subclasses must implement execute method")


class ProcessSubmissionUseCase(BaseUseCase):
    """
    Use case for processing a new suspicious submission.
    Handles the complete moderation pipeline.
    """
    
    def execute(self, submission_id: str, force_rescan: bool = False) -> Dict[str, Any]:
        """
        Process a submission through the moderation pipeline.
        
        Args:
            submission_id: ID of the submission to process
            force_rescan: Whether to force re-scanning
            
        Returns:
            Processing result with decision information
        """
        try:
            # Get submission
            submission = self.selectors.submissions().by_id(submission_id).first()
            if not submission:
                raise ValidationError(f"Submission {submission_id} not found")
            
            # Check if already processed
            if not force_rescan and submission.status != 'pending':
                return {
                    'submission_id': submission_id,
                    'status': submission.status,
                    'message': 'Submission already processed',
                    'decision_id': str(submission.decisions.first().id) if submission.decisions.exists() else None
                }
            
            # Step 1: Scan submission
            scan_result = self._scan_submission(submission)
            
            # Step 2: Apply auto-approval rules
            rule_result = self._apply_auto_approval_rules(submission, scan_result)
            
            # Step 3: Make moderation decision
            decision = self._make_moderation_decision(submission, scan_result, rule_result)
            
            # Step 4: Queue for human review if needed
            if decision.decision_type == 'escalate':
                self._queue_for_review(submission, decision)
            
            return {
                'submission_id': submission_id,
                'status': submission.status,
                'decision_type': decision.decision_type,
                'decision_id': str(decision.id),
                'confidence': decision.confidence,
                'scan_result': scan_result,
                'rule_result': rule_result,
                'queued_for_review': decision.decision_type == 'escalate'
            }
            
        except Exception as exc:
            logger.error(f"Process submission failed: {exc}")
            raise ModerationError(f"Failed to process submission {submission_id}: {exc}")
    
    def _scan_submission(self, submission: SuspiciousSubmission) -> Dict[str, Any]:
        """Scan submission for content analysis."""
        try:
            return self.scanner_service.scan_submission(submission)
        except Exception as exc:
            logger.error(f"Scanning failed for submission {submission.id}: {exc}")
            raise ServiceUnavailableError(f"Scanning service unavailable: {exc}")
    
    def _apply_auto_approval_rules(self, submission: SuspiciousSubmission, 
                                 scan_result: Dict[str, Any]) -> Dict[str, Any]:
        """Apply auto-approval rules to submission."""
        try:
            from .services import RuleEngineService
            rule_engine = RuleEngineService()
            return rule_engine.evaluate_rules(submission, scan_result)
        except Exception as exc:
            logger.error(f"Rule evaluation failed: {exc}")
            return {'matched_rules': [], 'should_approve': False, 'should_reject': False}
    
    def _make_moderation_decision(self, submission: SuspiciousSubmission,
                                scan_result: Dict[str, Any],
                                rule_result: Dict[str, Any]) -> ModerationDecision:
        """Make final moderation decision."""
        try:
            return self.moderation_service.make_decision(
                submission=submission,
                scan_result=scan_result,
                rule_result=rule_result
            )
        except Exception as exc:
            logger.error(f"Decision making failed: {exc}")
            raise ModerationError(f"Failed to make decision: {exc}")
    
    def _queue_for_review(self, submission: SuspiciousSubmission, 
                         decision: ModerationDecision) -> None:
        """Queue submission for human review."""
        try:
            from .services import QueueService
            queue_service = QueueService()
            queue_service.add_to_queue(submission, decision)
        except Exception as exc:
            logger.error(f"Queueing failed: {exc}")
            # Don't fail the entire process if queueing fails


class ReviewSubmissionUseCase(BaseUseCase):
    """
    Use case for human review of submissions.
    """
    
    def execute(self, submission_id: str, reviewer_id: str, 
                decision_type: str, reason: str = "") -> Dict[str, Any]:
        """
        Review and decide on a submission.
        
        Args:
            submission_id: ID of submission to review
            reviewer_id: ID of reviewer
            decision_type: Type of decision (approve/reject/escalate)
            reason: Reason for decision
            
        Returns:
            Review result
        """
        try:
            # Get submission
            submission = self.selectors.submissions().by_id(submission_id).first()
            if not submission:
                raise ValidationError(f"Submission {submission_id} not found")
            
            # Check if submission is pending review
            if submission.status != 'pending':
                raise ValidationError(f"Submission {submission_id} is not pending review")
            
            # Create human decision
            decision = self.moderation_service.create_human_decision(
                submission=submission,
                reviewer_id=reviewer_id,
                decision_type=decision_type,
                reason=reason
            )
            
            # Update queue status
            self._update_queue_status(submission, decision)
            
            return {
                'submission_id': submission_id,
                'decision_id': str(decision.id),
                'decision_type': decision.decision_type,
                'reviewer_id': reviewer_id,
                'status': submission.status,
                'reviewed_at': decision.decided_at.isoformat()
            }
            
        except Exception as exc:
            logger.error(f"Review submission failed: {exc}")
            raise ModerationError(f"Failed to review submission {submission_id}: {exc}")
    
    def _update_queue_status(self, submission: SuspiciousSubmission, 
                           decision: ModerationDecision) -> None:
        """Update queue status after review."""
        try:
            queue_item = self.selectors.queue().by_submission(str(submission.id)).first()
            if queue_item:
                queue_item.status = 'completed'
                queue_item.decision = decision
                queue_item.save()
        except Exception as exc:
            logger.error(f"Queue status update failed: {exc}")


class AppealDecisionUseCase(BaseUseCase):
    """
    Use case for handling appeals against moderation decisions.
    """
    
    def execute(self, decision_id: str, appellant_id: str, appeal_type: str,
                reason: str, evidence: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create and process an appeal.
        
        Args:
            decision_id: ID of decision being appealed
            appellant_id: ID of user making appeal
            appeal_type: Type of appeal
            reason: Reason for appeal
            evidence: Supporting evidence
            
        Returns:
            Appeal result
        """
        try:
            # Get original decision
            decision = self.selectors.decisions().by_id(decision_id).first()
            if not decision:
                raise ValidationError(f"Decision {decision_id} not found")
            
            # Check if appeal already exists
            existing_appeal = self.selectors.appeals().by_original_decision(decision_id).first()
            if existing_appeal and existing_appeal.status != 'rejected':
                raise ValidationError(f"Appeal already exists for decision {decision_id}")
            
            # Create appeal
            appeal = self._create_appeal(decision, appellant_id, appeal_type, reason, evidence)
            
            # Process appeal
            appeal_result = self._process_appeal(appeal)
            
            return {
                'appeal_id': str(appeal.id),
                'decision_id': decision_id,
                'status': appeal.status,
                'appeal_type': appeal_type,
                'processed_at': appeal_result.get('processed_at'),
                'outcome': appeal_result.get('outcome')
            }
            
        except Exception as exc:
            logger.error(f"Appeal processing failed: {exc}")
            raise ModerationError(f"Failed to process appeal: {exc}")
    
    def _create_appeal(self, decision: ModerationDecision, appellant_id: str,
                       appeal_type: str, reason: str, evidence: Dict[str, Any]) -> ModerationAppeal:
        """Create appeal record."""
        from .models import ModerationAppeal
        
        appeal = ModerationAppeal.objects.create(
            original_decision=decision,
            user_id=appellant_id,
            appeal_type=appeal_type,
            reason=reason,
            evidence=evidence or {},
            status='pending'
        )
        
        return appeal
    
    def _process_appeal(self, appeal: ModerationAppeal) -> Dict[str, Any]:
        """Process the appeal."""
        # Simple auto-processing for now
        # In production, this would involve complex logic
        
        appeal.status = 'approved'  # Auto-approve for demo
        appeal.reviewed_at = timezone.now()
        appeal.save()
        
        return {
            'processed_at': appeal.reviewed_at.isoformat(),
            'outcome': 'approved'
        }


class ManageAutoApprovalRulesUseCase(BaseUseCase):
    """
    Use case for managing auto-approval rules.
    """
    
    def create_rule(self, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new auto-approval rule."""
        try:
            from .models import AutoApprovalRule
            
            rule = AutoApprovalRule.objects.create(**rule_data)
            
            return {
                'rule_id': str(rule.id),
                'name': rule.name,
                'rule_type': rule.rule_type,
                'is_active': rule.is_active,
                'created_at': rule.created_at.isoformat()
            }
            
        except Exception as exc:
            logger.error(f"Rule creation failed: {exc}")
            raise ModerationError(f"Failed to create rule: {exc}")
    
    def update_rule(self, rule_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing auto-approval rule."""
        try:
            rule = self.selectors.rules().by_id(rule_id).first()
            if not rule:
                raise ValidationError(f"Rule {rule_id} not found")
            
            for key, value in update_data.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)
            
            rule.save()
            
            return {
                'rule_id': str(rule.id),
                'updated_at': rule.updated_at.isoformat()
            }
            
        except Exception as exc:
            logger.error(f"Rule update failed: {exc}")
            raise ModerationError(f"Failed to update rule: {exc}")
    
    def deactivate_rule(self, rule_id: str) -> Dict[str, Any]:
        """Deactivate an auto-approval rule."""
        return self.update_rule(rule_id, {'is_active': False})


class ManageTaskBotsUseCase(BaseUseCase):
    """
    Use case for managing task bots.
    """
    
    def create_bot(self, bot_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new task bot."""
        try:
            from .models import TaskBot
            
            bot = TaskBot.objects.create(**bot_data)
            
            return {
                'bot_id': str(bot.id),
                'name': bot.name,
                'bot_type': bot.bot_type,
                'status': bot.status,
                'created_at': bot.created_at.isoformat()
            }
            
        except Exception as exc:
            logger.error(f"Bot creation failed: {exc}")
            raise ModerationError(f"Failed to create bot: {exc}")
    
    def start_bot(self, bot_id: str) -> Dict[str, Any]:
        """Start a task bot."""
        try:
            bot = self.selectors.bots().by_id(bot_id).first()
            if not bot:
                raise ValidationError(f"Bot {bot_id} not found")
            
            bot.status = 'running'
            bot.save()
            
            # Start bot processing (would be implemented)
            self._start_bot_processing(bot)
            
            return {
                'bot_id': str(bot.id),
                'status': bot.status,
                'started_at': timezone.now().isoformat()
            }
            
        except Exception as exc:
            logger.error(f"Bot start failed: {exc}")
            raise ModerationError(f"Failed to start bot: {exc}")
    
    def stop_bot(self, bot_id: str) -> Dict[str, Any]:
        """Stop a task bot."""
        try:
            bot = self.selectors.bots().by_id(bot_id).first()
            if not bot:
                raise ValidationError(f"Bot {bot_id} not found")
            
            bot.status = 'stopped'
            bot.save()
            
            # Stop bot processing (would be implemented)
            self._stop_bot_processing(bot)
            
            return {
                'bot_id': str(bot.id),
                'status': bot.status,
                'stopped_at': timezone.now().isoformat()
            }
            
        except Exception as exc:
            logger.error(f"Bot stop failed: {exc}")
            raise ModerationError(f"Failed to stop bot: {exc}")
    
    def _start_bot_processing(self, bot: TaskBot) -> None:
        """Start bot processing (placeholder)."""
        # Implementation would go here
        pass
    
    def _stop_bot_processing(self, bot: TaskBot) -> None:
        """Stop bot processing (placeholder)."""
        # Implementation would go here
        pass


class GetModerationStatsUseCase(BaseUseCase):
    """
    Use case for getting moderation statistics.
    """
    
    def execute(self, days: int = 30, user_id: str = None) -> Dict[str, Any]:
        """
        Get moderation statistics.
        
        Args:
            days: Number of days to analyze
            user_id: Optional user filter
            
        Returns:
            Statistics dictionary
        """
        try:
            start_date = timezone.now() - timedelta(days=days)
            
            # Get submission stats
            submission_stats = self._get_submission_stats(start_date, user_id)
            
            # Get decision stats
            decision_stats = self._get_decision_stats(start_date, user_id)
            
            # Get appeal stats
            appeal_stats = self._get_appeal_stats(start_date, user_id)
            
            # Get bot performance stats
            bot_stats = self._get_bot_stats(start_date)
            
            return {
                'period_days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat(),
                'submissions': submission_stats,
                'decisions': decision_stats,
                'appeals': appeal_stats,
                'bots': bot_stats
            }
            
        except Exception as exc:
            logger.error(f"Stats generation failed: {exc}")
            raise ModerationError(f"Failed to generate stats: {exc}")
    
    def _get_submission_stats(self, start_date: datetime, user_id: str = None) -> Dict[str, Any]:
        """Get submission statistics."""
        selector = self.selectors.submissions().by_date_range(start_date=start_date)
        
        if user_id:
            selector = selector.by_user(user_id)
        
        total = selector.count()
        pending = selector.pending_review().count()
        approved = selector.approved().count()
        rejected = selector.rejected().count()
        escalated = selector.escalated().count()
        
        return {
            'total': total,
            'pending': pending,
            'approved': approved,
            'rejected': rejected,
            'escalated': escalated,
            'approval_rate': (approved / total * 100) if total > 0 else 0,
            'rejection_rate': (rejected / total * 100) if total > 0 else 0
        }
    
    def _get_decision_stats(self, start_date: datetime, user_id: str = None) -> Dict[str, Any]:
        """Get decision statistics."""
        selector = self.selectors.decisions().by_date_range(start_date=start_date)
        
        if user_id:
            selector = selector.by_decider(user_id)
        
        total = selector.count()
        automated = selector.automated().count()
        manual = selector.manual().count()
        high_confidence = selector.high_confidence().count()
        
        return {
            'total': total,
            'automated': automated,
            'manual': manual,
            'high_confidence': high_confidence,
            'automation_rate': (automated / total * 100) if total > 0 else 0
        }
    
    def _get_appeal_stats(self, start_date: datetime, user_id: str = None) -> Dict[str, Any]:
        """Get appeal statistics."""
        selector = self.selectors.appeals().by_date_range(start_date=start_date)
        
        if user_id:
            selector = selector.by_user(user_id)
        
        total = selector.count()
        pending = selector.pending_review().count()
        approved = selector.approved().count()
        rejected = selector.rejected().count()
        
        return {
            'total': total,
            'pending': pending,
            'approved': approved,
            'rejected': rejected,
            'success_rate': (approved / total * 100) if total > 0 else 0
        }
    
    def _get_bot_stats(self, start_date: datetime) -> Dict[str, Any]:
        """Get bot statistics."""
        bots = self.selectors.bots().all()
        
        total_bots = len(bots)
        running_bots = len([b for b in bots if b.status == 'running'])
        idle_bots = len([b for b in bots if b.status == 'idle'])
        error_bots = len([b for b in bots if b.status == 'error'])
        
        return {
            'total': total_bots,
            'running': running_bots,
            'idle': idle_bots,
            'error': error_bots,
            'active_rate': (running_bots / total_bots * 100) if total_bots > 0 else 0
        }


# Use case factory
class UseCaseFactory:
    """Factory for creating use case instances."""
    
    @staticmethod
    def process_submission() -> ProcessSubmissionUseCase:
        """Create process submission use case."""
        return ProcessSubmissionUseCase()
    
    @staticmethod
    def review_submission() -> ReviewSubmissionUseCase:
        """Create review submission use case."""
        return ReviewSubmissionUseCase()
    
    @staticmethod
    def appeal_decision() -> AppealDecisionUseCase:
        """Create appeal decision use case."""
        return AppealDecisionUseCase()
    
    @staticmethod
    def manage_rules() -> ManageAutoApprovalRulesUseCase:
        """Create manage rules use case."""
        return ManageAutoApprovalRulesUseCase()
    
    @staticmethod
    def manage_bots() -> ManageTaskBotsUseCase:
        """Create manage bots use case."""
        return ManageTaskBotsUseCase()
    
    @staticmethod
    def get_stats() -> GetModerationStatsUseCase:
        """Create get stats use case."""
        return GetModerationStatsUseCase()


# Convenience functions
def process_submission(submission_id: str, force_rescan: bool = False) -> Dict[str, Any]:
    """Process a submission."""
    use_case = UseCaseFactory.process_submission()
    return use_case.execute(submission_id, force_rescan)


def review_submission(submission_id: str, reviewer_id: str, 
                   decision_type: str, reason: str = "") -> Dict[str, Any]:
    """Review a submission."""
    use_case = UseCaseFactory.review_submission()
    return use_case.execute(submission_id, reviewer_id, decision_type, reason)


def appeal_decision(decision_id: str, appellant_id: str, appeal_type: str,
                  reason: str, evidence: Dict[str, Any] = None) -> Dict[str, Any]:
    """Appeal a decision."""
    use_case = UseCaseFactory.appeal_decision()
    return use_case.execute(decision_id, appellant_id, appeal_type, reason, evidence)


def get_moderation_stats(days: int = 30, user_id: str = None) -> Dict[str, Any]:
    """Get moderation statistics."""
    use_case = UseCaseFactory.get_stats()
    return use_case.execute(days, user_id)


# Initialize logging
logger.info("Use cases module initialized with business logic orchestration")
