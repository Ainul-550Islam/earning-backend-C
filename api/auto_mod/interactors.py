# =============================================================================
# auto_mod/interactors.py
# =============================================================================

"""
Interactors for auto moderation system following Clean Architecture patterns.
Provides business logic coordination between use cases and repositories.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction

from .use_cases import (
    ProcessSubmissionUseCase, ReviewSubmissionUseCase, AppealDecisionUseCase,
    ManageAutoApprovalRulesUseCase, ManageTaskBotsUseCase, GetModerationStatsUseCase
)
from .repositories import RepositoryFactory
from .models import SuspiciousSubmission, ModerationDecision, ModerationAppeal
from .exceptions import ModerationError, ValidationError
from .constants import AUTO_APPROVE_THRESHOLD, AUTO_REJECT_THRESHOLD

logger = logging.getLogger(__name__)


class BaseInteractor:
    """Base interactor with common functionality."""
    
    def __init__(self):
        self.repositories = RepositoryFactory()
        self.use_cases = self._initialize_use_cases()
    
    def _initialize_use_cases(self) -> Dict[str, Any]:
        """Initialize use cases."""
        return {
            'process_submission': ProcessSubmissionUseCase(),
            'review_submission': ReviewSubmissionUseCase(),
            'appeal_decision': AppealDecisionUseCase(),
            'manage_rules': ManageAutoApprovalRulesUseCase(),
            'manage_bots': ManageTaskBotsUseCase(),
            'get_stats': GetModerationStatsUseCase(),
        }


class SubmissionInteractor(BaseInteractor):
    """Interactor for submission-related operations."""
    
    def process_new_submission(self, submission_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a new suspicious submission.
        
        Args:
            submission_data: Submission data dictionary
            
        Returns:
            Processing result
        """
        try:
            # Create submission first
            submission = self.repositories.submissions().create(**submission_data)
            
            # Process through use case
            result = self.use_cases['process_submission'].execute(
                str(submission.id), force_rescan=False
            )
            
            return {
                'submission_id': str(submission.id),
                'status': result['status'],
                'decision_type': result.get('decision_type'),
                'confidence': result.get('confidence'),
                'queued_for_review': result.get('queued_for_review', False),
                'processed_at': timezone.now().isoformat()
            }
            
        except Exception as exc:
            logger.error(f"Process new submission failed: {exc}")
            raise ModerationError(f"Failed to process submission: {exc}")
    
    def rescan_submission(self, submission_id: str) -> Dict[str, Any]:
        """
        Force rescan of an existing submission.
        
        Args:
            submission_id: ID of submission to rescan
            
        Returns:
            Rescan result
        """
        try:
            result = self.use_cases['process_submission'].execute(
                submission_id, force_rescan=True
            )
            
            return {
                'submission_id': submission_id,
                'status': result['status'],
                'decision_type': result.get('decision_type'),
                'confidence': result.get('confidence'),
                'scan_result': result.get('scan_result'),
                'rescanned_at': timezone.now().isoformat()
            }
            
        except Exception as exc:
            logger.error(f"Rescan submission failed: {exc}")
            raise ModerationError(f"Failed to rescan submission: {exc}")
    
    def batch_process_submissions(self, submission_ids: List[str]) -> Dict[str, Any]:
        """
        Process multiple submissions in batch.
        
        Args:
            submission_ids: List of submission IDs
            
        Returns:
            Batch processing results
        """
        try:
            results = []
            failed = []
            
            for submission_id in submission_ids:
                try:
                    result = self.process_new_submission({'id': submission_id})
                    results.append(result)
                except Exception as exc:
                    failed.append({
                        'submission_id': submission_id,
                        'error': str(exc)
                    })
            
            return {
                'total': len(submission_ids),
                'processed': len(results),
                'failed': len(failed),
                'results': results,
                'failed_items': failed
            }
            
        except Exception as exc:
            logger.error(f"Batch process failed: {exc}")
            raise ModerationError(f"Failed to batch process submissions: {exc}")
    
    def get_submission_details(self, submission_id: str) -> Dict[str, Any]:
        """
        Get detailed submission information.
        
        Args:
            submission_id: ID of submission
            
        Returns:
            Submission details
        """
        try:
            submission = self.repositories.submissions().get_by_id(submission_id)
            if not submission:
                raise ValidationError(f"Submission {submission_id} not found")
            
            # Get related data
            decisions = self.repositories.decisions().by_submission(submission_id)
            queue_items = self.repositories.queue().by_submission(submission_id)
            
            return {
                'submission': {
                    'id': str(submission.id),
                    'status': submission.status,
                    'submission_type': submission.submission_type,
                    'risk_score': submission.risk_score,
                    'ai_confidence': submission.ai_confidence,
                    'flag_reason': submission.flag_reason,
                    'created_at': submission.created_at.isoformat(),
                    'updated_at': submission.updated_at.isoformat(),
                },
                'decisions': [
                    {
                        'id': str(dec.id),
                        'decision_type': dec.decision_type,
                        'confidence': dec.confidence,
                        'is_automated': dec.is_automated,
                        'decided_at': dec.decided_at.isoformat(),
                    }
                    for dec in decisions
                ],
                'queue_items': [
                    {
                        'id': str(item.id),
                        'status': item.status,
                        'priority': item.priority,
                        'assigned_to': str(item.assigned_to_id) if item.assigned_to else None,
                    }
                    for item in queue_items
                ]
            }
            
        except Exception as exc:
            logger.error(f"Get submission details failed: {exc}")
            raise ModerationError(f"Failed to get submission details: {exc}")


class ReviewInteractor(BaseInteractor):
    """Interactor for review operations."""
    
    def review_submission(self, review_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Review a submission.
        
        Args:
            review_data: Review data including submission_id, reviewer_id, decision_type, reason
            
        Returns:
            Review result
        """
        try:
            result = self.use_cases['review_submission'].execute(
                review_data['submission_id'],
                review_data['reviewer_id'],
                review_data['decision_type'],
                review_data.get('reason', '')
            )
            
            return {
                'review_id': result['decision_id'],
                'submission_id': result['submission_id'],
                'decision_type': result['decision_type'],
                'reviewer_id': result['reviewer_id'],
                'status': result['status'],
                'reviewed_at': result['reviewed_at']
            }
            
        except Exception as exc:
            logger.error(f"Review submission failed: {exc}")
            raise ModerationError(f"Failed to review submission: {exc}")
    
    def bulk_review_submissions(self, reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Review multiple submissions in bulk.
        
        Args:
            reviews: List of review data
            
        Returns:
            Bulk review results
        """
        try:
            results = []
            failed = []
            
            for review_data in reviews:
                try:
                    result = self.review_submission(review_data)
                    results.append(result)
                except Exception as exc:
                    failed.append({
                        'submission_id': review_data.get('submission_id'),
                        'error': str(exc)
                    })
            
            return {
                'total': len(reviews),
                'processed': len(results),
                'failed': len(failed),
                'results': results,
                'failed_items': failed
            }
            
        except Exception as exc:
            logger.error(f"Bulk review failed: {exc}")
            raise ModerationError(f"Failed to bulk review submissions: {exc}")
    
    def get_review_queue(self, reviewer_id: str = None, limit: int = 50) -> Dict[str, Any]:
        """
        Get review queue.
        
        Args:
            reviewer_id: Optional reviewer filter
            limit: Maximum number of items
            
        Returns:
            Review queue data
        """
        try:
            queue_items = self.repositories.queue().unassigned()[:limit]
            
            if reviewer_id:
                # Get items assigned to specific reviewer
                queue_items = self.repositories.queue().by_assigned_to(reviewer_id)[:limit]
            
            return {
                'queue_items': [
                    {
                        'id': str(item.id),
                        'submission_id': str(item.submission_id),
                        'priority': item.priority,
                        'status': item.status,
                        'created_at': item.created_at.isoformat(),
                        'due_date': item.due_date.isoformat() if item.due_date else None,
                    }
                    for item in queue_items
                ],
                'total': len(queue_items)
            }
            
        except Exception as exc:
            logger.error(f"Get review queue failed: {exc}")
            raise ModerationError(f"Failed to get review queue: {exc}")


class AppealInteractor(BaseInteractor):
    """Interactor for appeal operations."""
    
    def create_appeal(self, appeal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create an appeal.
        
        Args:
            appeal_data: Appeal data
            
        Returns:
            Appeal result
        """
        try:
            result = self.use_cases['appeal_decision'].execute(
                appeal_data['decision_id'],
                appeal_data['appellant_id'],
                appeal_data['appeal_type'],
                appeal_data.get('reason', ''),
                appeal_data.get('evidence', {})
            )
            
            return {
                'appeal_id': result['appeal_id'],
                'decision_id': result['decision_id'],
                'status': result['status'],
                'appeal_type': result['appeal_type'],
                'processed_at': result.get('processed_at'),
                'outcome': result.get('outcome')
            }
            
        except Exception as exc:
            logger.error(f"Create appeal failed: {exc}")
            raise ModerationError(f"Failed to create appeal: {exc}")
    
    def process_appeal(self, appeal_id: str, reviewer_id: str, 
                       decision: str, reason: str = "") -> Dict[str, Any]:
        """
        Process an appeal.
        
        Args:
            appeal_id: ID of appeal
            reviewer_id: ID of reviewer
            decision: Appeal decision
            reason: Reason for decision
            
        Returns:
            Appeal processing result
        """
        try:
            # Get appeal
            appeal = self.repositories.appeals().get_by_id(appeal_id)
            if not appeal:
                raise ValidationError(f"Appeal {appeal_id} not found")
            
            # Update appeal status
            appeal.status = decision
            appeal.reviewed_by_id = reviewer_id
            appeal.reviewed_at = timezone.now()
            appeal.review_reason = reason
            appeal.save()
            
            return {
                'appeal_id': str(appeal.id),
                'status': appeal.status,
                'reviewer_id': reviewer_id,
                'reviewed_at': appeal.reviewed_at.isoformat(),
                'outcome': decision
            }
            
        except Exception as exc:
            logger.error(f"Process appeal failed: {exc}")
            raise ModerationError(f"Failed to process appeal: {exc}")
    
    def get_appeal_details(self, appeal_id: str) -> Dict[str, Any]:
        """
        Get appeal details.
        
        Args:
            appeal_id: ID of appeal
            
        Returns:
            Appeal details
        """
        try:
            appeal = self.repositories.appeals().get_by_id(appeal_id)
            if not appeal:
                raise ValidationError(f"Appeal {appeal_id} not found")
            
            # Get original decision
            original_decision = self.repositories.decisions().get_by_id(str(appeal.original_decision_id))
            
            return {
                'appeal': {
                    'id': str(appeal.id),
                    'status': appeal.status,
                    'appeal_type': appeal.appeal_type,
                    'reason': appeal.reason,
                    'evidence': appeal.evidence,
                    'created_at': appeal.created_at.isoformat(),
                    'reviewed_at': appeal.reviewed_at.isoformat() if appeal.reviewed_at else None,
                },
                'original_decision': {
                    'id': str(original_decision.id),
                    'decision_type': original_decision.decision_type,
                    'confidence': original_decision.confidence,
                    'decided_at': original_decision.decided_at.isoformat(),
                } if original_decision else None
            }
            
        except Exception as exc:
            logger.error(f"Get appeal details failed: {exc}")
            raise ModerationError(f"Failed to get appeal details: {exc}")


class RuleInteractor(BaseInteractor):
    """Interactor for auto-approval rule operations."""
    
    def create_rule(self, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new auto-approval rule."""
        try:
            result = self.use_cases['manage_rules'].create_rule(rule_data)
            return result
        except Exception as exc:
            logger.error(f"Create rule failed: {exc}")
            raise ModerationError(f"Failed to create rule: {exc}")
    
    def update_rule(self, rule_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing rule."""
        try:
            result = self.use_cases['manage_rules'].update_rule(rule_id, update_data)
            return result
        except Exception as exc:
            logger.error(f"Update rule failed: {exc}")
            raise ModerationError(f"Failed to update rule: {exc}")
    
    def deactivate_rule(self, rule_id: str) -> Dict[str, Any]:
        """Deactivate a rule."""
        try:
            result = self.use_cases['manage_rules'].deactivate_rule(rule_id)
            return result
        except Exception as exc:
            logger.error(f"Deactivate rule failed: {exc}")
            raise ModerationError(f"Failed to deactivate rule: {exc}")
    
    def test_rule(self, rule_id: str, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Test a rule against test data."""
        try:
            # This would implement rule testing logic
            # For now, return a mock result
            return {
                'rule_id': rule_id,
                'test_result': 'passed',
                'confidence': 0.85,
                'matched_conditions': ['condition1', 'condition2']
            }
        except Exception as exc:
            logger.error(f"Test rule failed: {exc}")
            raise ModerationError(f"Failed to test rule: {exc}")


class BotInteractor(BaseInteractor):
    """Interactor for task bot operations."""
    
    def create_bot(self, bot_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new task bot."""
        try:
            result = self.use_cases['manage_bots'].create_bot(bot_data)
            return result
        except Exception as exc:
            logger.error(f"Create bot failed: {exc}")
            raise ModerationError(f"Failed to create bot: {exc}")
    
    def start_bot(self, bot_id: str) -> Dict[str, Any]:
        """Start a task bot."""
        try:
            result = self.use_cases['manage_bots'].start_bot(bot_id)
            return result
        except Exception as exc:
            logger.error(f"Start bot failed: {exc}")
            raise ModerationError(f"Failed to start bot: {exc}")
    
    def stop_bot(self, bot_id: str) -> Dict[str, Any]:
        """Stop a task bot."""
        try:
            result = self.use_cases['manage_bots'].stop_bot(bot_id)
            return result
        except Exception as exc:
            logger.error(f"Stop bot failed: {exc}")
            raise ModerationError(f"Failed to stop bot: {exc}")
    
    def get_bot_status(self, bot_id: str) -> Dict[str, Any]:
        """Get bot status."""
        try:
            bot = self.repositories.bots().get_by_id(bot_id)
            if not bot:
                raise ValidationError(f"Bot {bot_id} not found")
            
            return {
                'bot_id': str(bot.id),
                'name': bot.name,
                'status': bot.status,
                'is_active': bot.is_active,
                'performance_score': bot.performance_score,
                'last_activity': bot.updated_at.isoformat()
            }
        except Exception as exc:
            logger.error(f"Get bot status failed: {exc}")
            raise ModerationError(f"Failed to get bot status: {exc}")


class AnalyticsInteractor(BaseInteractor):
    """Interactor for analytics and statistics."""
    
    def get_dashboard_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get dashboard statistics."""
        try:
            result = self.use_cases['get_stats'].execute(days=days)
            
            # Add additional analytics
            queue_stats = self.repositories.queue().get_queue_stats()
            bot_stats = self.repositories.bots().get_bot_stats()
            
            return {
                **result,
                'queue': queue_stats,
                'bots': bot_stats
            }
        except Exception as exc:
            logger.error(f"Get dashboard stats failed: {exc}")
            raise ModerationError(f"Failed to get dashboard stats: {exc}")
    
    def get_performance_metrics(self, days: int = 7) -> Dict[str, Any]:
        """Get performance metrics."""
        try:
            # This would implement performance metrics calculation
            return {
                'avg_processing_time': 2.5,  # seconds
                'throughput': 150,  # submissions per hour
                'accuracy': 0.92,
                'false_positive_rate': 0.08,
                'period_days': days
            }
        except Exception as exc:
            logger.error(f"Get performance metrics failed: {exc}")
            raise ModerationError(f"Failed to get performance metrics: {exc}")
    
    def get_user_activity(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get user activity statistics."""
        try:
            result = self.use_cases['get_stats'].execute(days=days, user_id=user_id)
            
            return {
                'user_id': user_id,
                'period_days': days,
                **result
            }
        except Exception as exc:
            logger.error(f"Get user activity failed: {exc}")
            raise ModerationError(f"Failed to get user activity: {exc}")


# Interactor factory
class InteractorFactory:
    """Factory for creating interactor instances."""
    
    @staticmethod
    def submissions() -> SubmissionInteractor:
        """Create submissions interactor."""
        return SubmissionInteractor()
    
    @staticmethod
    def reviews() -> ReviewInteractor:
        """Create reviews interactor."""
        return ReviewInteractor()
    
    @staticmethod
    def appeals() -> AppealInteractor:
        """Create appeals interactor."""
        return AppealInteractor()
    
    @staticmethod
    def rules() -> RuleInteractor:
        """Create rules interactor."""
        return RuleInteractor()
    
    @staticmethod
    def bots() -> BotInteractor:
        """Create bots interactor."""
        return BotInteractor()
    
    @staticmethod
    def analytics() -> AnalyticsInteractor:
        """Create analytics interactor."""
        return AnalyticsInteractor()


# Initialize logging
logger.info("Interactors module initialized with business logic coordination")
