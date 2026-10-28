# =============================================================================
# auto_mod/factories.py
# =============================================================================

"""
Factory classes for auto moderation system.
Provides factory methods for creating instances of various components.
"""

import logging
from typing import Any, Dict, List, Optional, Type, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import (
    SuspiciousSubmission, ModerationDecision, ModerationAppeal,
    ModerationQueue, TaskBot, AutoApprovalRule, MLModelVersion, ContentSignal
)
from .serializers import (
    SuspiciousSubmissionSerializer, ModerationDecisionSerializer,
    ModerationAppealSerializer, ModerationQueueSerializer,
    TaskBotSerializer, AutoApprovalRuleSerializer
)
from .services import ModerationService, ScannerService, RuleEngineService
from .exceptions import ModerationError, ValidationError

logger = logging.getLogger(__name__)

User = get_user_model()


class BaseFactory:
    """Base factory class."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def create(self, **kwargs) -> Any:
        """Create instance."""
        raise NotImplementedError("Subclasses must implement create method")
    
    def create_batch(self, items: List[Dict[str, Any]]) -> List[Any]:
        """Create multiple instances."""
        instances = []
        for item_data in items:
            try:
                instance = self.create(**item_data)
                instances.append(instance)
            except Exception as exc:
                self.logger.error(f"Create batch item failed: {exc}")
                continue
        return instances


class SubmissionFactory(BaseFactory):
    """Factory for creating SuspiciousSubmission instances."""
    
    def create(self, user: User = None, submission_type: str = "text",
               content: str = "", metadata: Dict[str, Any] = None,
               **kwargs) -> SuspiciousSubmission:
        """
        Create a suspicious submission.
        
        Args:
            user: User who created the submission
            submission_type: Type of submission
            content: Content text
            metadata: Additional metadata
            **kwargs: Additional fields
            
        Returns:
            Created submission
        """
        try:
            if not user:
                raise ValidationError("User is required")
            
            submission = SuspiciousSubmission.objects.create(
                user=user,
                submission_type=submission_type,
                text_content=content,
                metadata=metadata or {},
                **kwargs
            )
            
            self.logger.info(f"Created submission {submission.id}")
            return submission
            
        except Exception as exc:
            self.logger.error(f"Create submission failed: {exc}")
            raise ModerationError(f"Failed to create submission: {exc}")
    
    def create_with_auto_processing(self, user: User = None, **kwargs) -> Dict[str, Any]:
        """
        Create submission with automatic processing.
        
        Args:
            user: User who created the submission
            **kwargs: Submission fields
            
        Returns:
            Submission and decision data
        """
        try:
            # Create submission
            submission = self.create(user=user, **kwargs)
            
            # Auto-process submission
            moderation_service = ModerationService()
            decision = moderation_service.process_submission(submission)
            
            return {
                'submission': submission,
                'decision': decision,
                'processed_at': timezone.now(),
            }
            
        except Exception as exc:
            self.logger.error(f"Create submission with auto-processing failed: {exc}")
            raise ModerationError(f"Failed to create submission with auto-processing: {exc}")
    
    def create_test_data(self, count: int = 10) -> List[SuspiciousSubmission]:
        """Create test submission data."""
        try:
            # Get or create test user
            test_user, created = User.objects.get_or_create(
                username='test_user',
                defaults={
                    'email': 'test@example.com',
                    'is_staff': False,
                }
            )
            
            submissions = []
            
            for i in range(count):
                submission_data = {
                    'user': test_user,
                    'submission_type': 'text',
                    'content': f'Test submission content {i}',
                    'metadata': {'test': True, 'index': i},
                    'risk_score': 0.5,
                    'ai_confidence': 0.7,
                }
                
                submission = self.create(**submission_data)
                submissions.append(submission)
            
            self.logger.info(f"Created {count} test submissions")
            return submissions
            
        except Exception as exc:
            self.logger.error(f"Create test data failed: {exc}")
            raise ModerationError(f"Failed to create test data: {exc}")


class DecisionFactory(BaseFactory):
    """Factory for creating ModerationDecision instances."""
    
    def create(self, submission: SuspiciousSubmission, decision_type: str = "approve",
               moderator: User = None, confidence: float = 0.8,
               reason: str = "", is_automated: bool = False,
               **kwargs) -> ModerationDecision:
        """
        Create a moderation decision.
        
        Args:
            submission: Submission being decided
            decision_type: Type of decision
            moderator: Moderator who made the decision
            confidence: Decision confidence
            reason: Decision reason
            is_automated: Whether decision is automated
            **kwargs: Additional fields
            
        Returns:
            Created decision
        """
        try:
            if not submission:
                raise ValidationError("Submission is required")
            
            decision = ModerationDecision.objects.create(
                submission=submission,
                decider=moderator,
                decision_type=decision_type,
                confidence=confidence,
                reason=reason,
                is_automated=is_automated,
                **kwargs
            )
            
            self.logger.info(f"Created decision {decision.id}")
            return decision
            
        except Exception as exc:
            self.logger.error(f"Create decision failed: {exc}")
            raise ModerationError(f"Failed to create decision: {exc}")
    
    def create_automated(self, submission: SuspiciousSubmission, 
                        decision_type: str = "approve", confidence: float = 0.8,
                        reason: str = "", **kwargs) -> ModerationDecision:
        """Create automated decision."""
        return self.create(
            submission=submission,
            decision_type=decision_type,
            moderator=None,
            confidence=confidence,
            reason=reason,
            is_automated=True,
            **kwargs
        )
    
    def create_manual(self, submission: SuspiciousSubmission, moderator: User,
                     decision_type: str = "approve", confidence: float = 0.9,
                     reason: str = "", **kwargs) -> ModerationDecision:
        """Create manual decision."""
        return self.create(
            submission=submission,
            decision_type=decision_type,
            moderator=moderator,
            confidence=confidence,
            reason=reason,
            is_automated=False,
            **kwargs
        )


class AppealFactory(BaseFactory):
    """Factory for creating ModerationAppeal instances."""
    
    def create(self, original_decision: ModerationDecision, user: User = None,
               appeal_type: str = "reconsider", reason: str = "",
               evidence: Dict[str, Any] = None, **kwargs) -> ModerationAppeal:
        """
        Create an appeal.
        
        Args:
            original_decision: Original decision being appealed
            user: User filing the appeal
            appeal_type: Type of appeal
            reason: Appeal reason
            evidence: Appeal evidence
            **kwargs: Additional fields
            
        Returns:
            Created appeal
        """
        try:
            if not original_decision:
                raise ValidationError("Original decision is required")
            
            if not user:
                raise ValidationError("User is required")
            
            appeal = ModerationAppeal.objects.create(
                original_decision=original_decision,
                user=user,
                appeal_type=appeal_type,
                reason=reason,
                evidence=evidence or {},
                **kwargs
            )
            
            self.logger.info(f"Created appeal {appeal.id}")
            return appeal
            
        except Exception as exc:
            self.logger.error(f"Create appeal failed: {exc}")
            raise ModerationError(f"Failed to create appeal: {exc}")
    
    def create_with_auto_review(self, original_decision: ModerationDecision, 
                               user: User = None, **kwargs) -> Dict[str, Any]:
        """Create appeal with automatic review."""
        try:
            # Create appeal
            appeal = self.create(original_decision=original_decision, user=user, **kwargs)
            
            # Auto-review appeal
            from .logic import appeal_logic
            appeal_data = {
                'original_decision_id': str(original_decision.id),
                'user_id': str(user.id),
                'appeal_type': kwargs.get('appeal_type', 'reconsider'),
                'reason': kwargs.get('reason', ''),
                'evidence': kwargs.get('evidence', {}),
            }
            
            review_result = appeal_logic.process_appeal(appeal_data)
            
            return {
                'appeal': appeal,
                'review_result': review_result,
                'processed_at': timezone.now(),
            }
            
        except Exception as exc:
            self.logger.error(f"Create appeal with auto-review failed: {exc}")
            raise ModerationError(f"Failed to create appeal with auto-review: {exc}")


class QueueFactory(BaseFactory):
    """Factory for creating ModerationQueue instances."""
    
    def create(self, submission: SuspiciousSubmission, priority: str = "normal",
               assigned_to: User = None, assigned_by: User = None,
               **kwargs) -> ModerationQueue:
        """
        Create a queue item.
        
        Args:
            submission: Submission to queue
            priority: Queue priority
            assigned_to: User assigned to
            assigned_by: User who assigned
            **kwargs: Additional fields
            
        Returns:
            Created queue item
        """
        try:
            if not submission:
                raise ValidationError("Submission is required")
            
            queue_item = ModerationQueue.objects.create(
                submission=submission,
                priority=priority,
                assigned_to=assigned_to,
                assigned_by=assigned_by,
                due_date=timezone.now() + timedelta(hours=24),
                **kwargs
            )
            
            self.logger.info(f"Created queue item {queue_item.id}")
            return queue_item
            
        except Exception as exc:
            self.logger.error(f"Create queue item failed: {exc}")
            raise ModerationError(f"Failed to create queue item: {exc}")
    
    def create_with_auto_assignment(self, submission: SuspiciousSubmission,
                                  **kwargs) -> Dict[str, Any]:
        """Create queue item with automatic assignment."""
        try:
            # Create queue item
            queue_item = self.create(submission=submission, **kwargs)
            
            # Auto-assign
            from .logic import queue_logic
            assigned_moderator_id = queue_logic.assign_queue_item(queue_item)
            
            if assigned_moderator_id:
                queue_item.assigned_to_id = assigned_moderator_id
                queue_item.status = 'assigned'
                queue_item.save()
            
            return {
                'queue_item': queue_item,
                'assigned_moderator_id': assigned_moderator_id,
                'created_at': timezone.now(),
            }
            
        except Exception as exc:
            self.logger.error(f"Create queue item with auto-assignment failed: {exc}")
            raise ModerationError(f"Failed to create queue item with auto-assignment: {exc}")


class TaskBotFactory(BaseFactory):
    """Factory for creating TaskBot instances."""
    
    def create(self, name: str, bot_type: str = "scanner", configuration: Dict[str, Any] = None,
               **kwargs) -> TaskBot:
        """
        Create a task bot.
        
        Args:
            name: Bot name
            bot_type: Type of bot
            configuration: Bot configuration
            **kwargs: Additional fields
            
        Returns:
            Created bot
        """
        try:
            bot = TaskBot.objects.create(
                name=name,
                bot_type=bot_type,
                configuration=configuration or {},
                **kwargs
            )
            
            self.logger.info(f"Created task bot {bot.id}")
            return bot
            
        except Exception as exc:
            self.logger.error(f"Create task bot failed: {exc}")
            raise ModerationError(f"Failed to create task bot: {exc}")
    
    def create_scanner(self, name: str = "Content Scanner", 
                       configuration: Dict[str, Any] = None) -> TaskBot:
        """Create a scanner bot."""
        default_config = {
            'scan_types': ['text', 'image'],
            'confidence_threshold': 0.7,
            'max_retries': 3,
        }
        
        if configuration:
            default_config.update(configuration)
        
        return self.create(
            name=name,
            bot_type='scanner',
            configuration=default_config
        )
    
    def create_analyzer(self, name: str = "Content Analyzer",
                       configuration: Dict[str, Any] = None) -> TaskBot:
        """Create an analyzer bot."""
        default_config = {
            'analysis_types': ['sentiment', 'toxicity', 'spam'],
            'confidence_threshold': 0.8,
            'processing_timeout': 30,
        }
        
        if configuration:
            default_config.update(configuration)
        
        return self.create(
            name=name,
            bot_type='analyzer',
            configuration=default_config
        )
    
    def create_reviewer(self, name: str = "Content Reviewer",
                       configuration: Dict[str, Any] = None) -> TaskBot:
        """Create a reviewer bot."""
        default_config = {
            'review_criteria': ['content_quality', 'policy_violation'],
            'auto_approve_threshold': 0.9,
            'auto_reject_threshold': 0.1,
        }
        
        if configuration:
            default_config.update(configuration)
        
        return self.create(
            name=name,
            bot_type='reviewer',
            configuration=default_config
        )


class RuleFactory(BaseFactory):
    """Factory for creating AutoApprovalRule instances."""
    
    def create(self, name: str, rule_type: str = "threshold", conditions: Dict[str, Any] = None,
               confidence_threshold: float = 0.8, submission_type: str = "text",
               **kwargs) -> AutoApprovalRule:
        """
        Create an auto-approval rule.
        
        Args:
            name: Rule name
            rule_type: Type of rule
            conditions: Rule conditions
            confidence_threshold: Confidence threshold
            submission_type: Submission type
            **kwargs: Additional fields
            
        Returns:
            Created rule
        """
        try:
            rule = AutoApprovalRule.objects.create(
                name=name,
                rule_type=rule_type,
                conditions=conditions or {},
                confidence_threshold=confidence_threshold,
                submission_type=submission_type,
                **kwargs
            )
            
            self.logger.info(f"Created rule {rule.id}")
            return rule
            
        except Exception as exc:
            self.logger.error(f"Create rule failed: {exc}")
            raise ModerationError(f"Failed to create rule: {exc}")
    
    def create_threshold_rule(self, name: str, field: str = "risk_score",
                           operator: str = "lt", value: float = 0.3,
                           **kwargs) -> AutoApprovalRule:
        """Create a threshold-based rule."""
        conditions = {
            'field': field,
            'operator': operator,
            'value': value,
        }
        
        return self.create(
            name=name,
            rule_type='threshold',
            conditions=conditions,
            **kwargs
        )
    
    def create_keyword_rule(self, name: str, keywords: List[str],
                           action: str = "approve", **kwargs) -> AutoApprovalRule:
        """Create a keyword-based rule."""
        conditions = {
            'keywords': keywords,
            'action': action,
        }
        
        return self.create(
            name=name,
            rule_type='keyword',
            conditions=conditions,
            **kwargs
        )
    
    def create_ml_model_rule(self, name: str, model_name: str,
                           model_threshold: float = 0.8, **kwargs) -> AutoApprovalRule:
        """Create an ML model-based rule."""
        conditions = {
            'model_name': model_name,
            'model_threshold': model_threshold,
        }
        
        return self.create(
            name=name,
            rule_type='ml_model',
            conditions=conditions,
            **kwargs
        )


class MLModelVersionFactory(BaseFactory):
    """Factory for creating MLModelVersion instances."""
    
    def create(self, model_name: str, version: str, model_type: str = "text_classifier",
               accuracy: float = 0.0, precision: float = 0.0,
               recall: float = 0.0, f1_score: float = 0.0,
               **kwargs) -> MLModelVersion:
        """
        Create an ML model version.
        
        Args:
            model_name: Model name
            version: Model version
            model_type: Type of model
            accuracy: Model accuracy
            precision: Model precision
            recall: Model recall
            f1_score: F1 score
            **kwargs: Additional fields
            
        Returns:
            Created model version
        """
        try:
            model_version = MLModelVersion.objects.create(
                model_name=model_name,
                version=version,
                model_type=model_type,
                accuracy=accuracy,
                precision=precision,
                recall=recall,
                f1_score=f1_score,
                **kwargs
            )
            
            self.logger.info(f"Created ML model version {model_version.id}")
            return model_version
            
        except Exception as exc:
            self.logger.error(f"Create ML model version failed: {exc}")
            raise ModerationError(f"Failed to create ML model version: {exc}")
    
    def create_text_classifier(self, model_name: str, version: str,
                             metrics: Dict[str, float] = None, **kwargs) -> MLModelVersion:
        """Create a text classifier model version."""
        default_metrics = {
            'accuracy': 0.85,
            'precision': 0.82,
            'recall': 0.88,
            'f1_score': 0.85,
        }
        
        if metrics:
            default_metrics.update(metrics)
        
        return self.create(
            model_name=model_name,
            version=version,
            model_type='text_classifier',
            **default_metrics,
            **kwargs
        )
    
    def create_image_classifier(self, model_name: str, version: str,
                              metrics: Dict[str, float] = None, **kwargs) -> MLModelVersion:
        """Create an image classifier model version."""
        default_metrics = {
            'accuracy': 0.92,
            'precision': 0.90,
            'recall': 0.94,
            'f1_score': 0.92,
        }
        
        if metrics:
            default_metrics.update(metrics)
        
        return self.create(
            model_name=model_name,
            version=version,
            model_type='image_classifier',
            **default_metrics,
            **kwargs
        )


class ContentSignalFactory(BaseFactory):
    """Factory for creating ContentSignal instances."""
    
    def create(self, submission: SuspiciousSubmission, signal_type: str = "spam",
               severity: str = "medium", confidence: float = 0.8,
               details: Dict[str, Any] = None, **kwargs) -> ContentSignal:
        """
        Create a content signal.
        
        Args:
            submission: Submission that triggered the signal
            signal_type: Type of signal
            severity: Signal severity
            confidence: Signal confidence
            details: Signal details
            **kwargs: Additional fields
            
        Returns:
            Created signal
        """
        try:
            signal = ContentSignal.objects.create(
                submission=submission,
                signal_type=signal_type,
                severity=severity,
                confidence=confidence,
                details=details or {},
                **kwargs
            )
            
            self.logger.info(f"Created content signal {signal.id}")
            return signal
            
        except Exception as exc:
            self.logger.error(f"Create content signal failed: {exc}")
            raise ModerationError(f"Failed to create content signal: {exc}")
    
    def create_spam_signal(self, submission: SuspiciousSubmission,
                          confidence: float = 0.8, **kwargs) -> ContentSignal:
        """Create a spam signal."""
        return self.create(
            submission=submission,
            signal_type='spam',
            severity='medium',
            confidence=confidence,
            **kwargs
        )
    
    def create_toxicity_signal(self, submission: SuspiciousSubmission,
                              confidence: float = 0.9, **kwargs) -> ContentSignal:
        """Create a toxicity signal."""
        return self.create(
            submission=submission,
            signal_type='toxicity',
            severity='high',
            confidence=confidence,
            **kwargs
        )
    
    def create_violence_signal(self, submission: SuspiciousSubmission,
                              confidence: float = 0.95, **kwargs) -> ContentSignal:
        """Create a violence signal."""
        return self.create(
            submission=submission,
            signal_type='violence',
            severity='critical',
            confidence=confidence,
            **kwargs
        )


class ServiceFactory:
    """Factory for creating service instances."""
    
    @staticmethod
    def create_moderation_service() -> ModerationService:
        """Create moderation service."""
        return ModerationService()
    
    @staticmethod
    def create_scanner_service() -> ScannerService:
        """Create scanner service."""
        return ScannerService()
    
    @staticmethod
    def create_rule_engine_service() -> RuleEngineService:
        """Create rule engine service."""
        return RuleEngineService()


class TestDataManager:
    """Factory for creating test data."""
    
    def __init__(self):
        self.submission_factory = SubmissionFactory()
        self.decision_factory = DecisionFactory()
        self.appeal_factory = AppealFactory()
        self.queue_factory = QueueFactory()
        self.bot_factory = TaskBotFactory()
        self.rule_factory = RuleFactory()
        self.signal_factory = ContentSignalFactory()
    
    def create_complete_test_scenario(self) -> Dict[str, Any]:
        """Create a complete test scenario."""
        try:
            # Create test user
            test_user, created = User.objects.get_or_create(
                username='test_scenario_user',
                defaults={
                    'email': 'test_scenario@example.com',
                    'is_staff': False,
                }
            )
            
            # Create moderator
            moderator, created = User.objects.get_or_create(
                username='test_moderator',
                defaults={
                    'email': 'moderator@example.com',
                    'is_staff': True,
                }
            )
            
            # Create submission
            submission = self.submission_factory.create(
                user=test_user,
                submission_type='text',
                content='This is a test submission for scenario testing',
                metadata={'test': True}
            )
            
            # Create decision
            decision = self.decision_factory.create_manual(
                submission=submission,
                moderator=moderator,
                decision_type='approve',
                reason='Test scenario approval'
            )
            
            # Create appeal
            appeal = self.appeal_factory.create(
                original_decision=decision,
                user=test_user,
                appeal_type='reconsider',
                reason='Test appeal for scenario'
            )
            
            # Create queue item
            queue_item = self.queue_factory.create(
                submission=self.submission_factory.create(
                    user=test_user,
                    submission_type='text',
                    content='Another test submission for queue'
                )
            )
            
            # Create bot
            bot = self.bot_factory.create_scanner('Test Scanner Bot')
            
            # Create rule
            rule = self.rule_factory.create_threshold_rule('Test Rule')
            
            # Create signal
            signal = self.signal_factory.create_spam_signal(submission)
            
            return {
                'user': test_user,
                'moderator': moderator,
                'submission': submission,
                'decision': decision,
                'appeal': appeal,
                'queue_item': queue_item,
                'bot': bot,
                'rule': rule,
                'signal': signal,
                'created_at': timezone.now(),
            }
            
        except Exception as exc:
            logger.error(f"Create complete test scenario failed: {exc}")
            raise ModerationError(f"Failed to create test scenario: {exc}")


# Global factory instances
submission_factory = SubmissionFactory()
decision_factory = DecisionFactory()
appeal_factory = AppealFactory()
queue_factory = QueueFactory()
bot_factory = TaskBotFactory()
rule_factory = RuleFactory()
model_version_factory = MLModelVersionFactory()
signal_factory = ContentSignalFactory()
service_factory = ServiceFactory()
test_data_manager = TestDataManager()


# Utility functions
def create_submission(user: User = None, **kwargs) -> SuspiciousSubmission:
    """Create submission."""
    return submission_factory.create(user=user, **kwargs)


def create_decision(submission: SuspiciousSubmission, **kwargs) -> ModerationDecision:
    """Create decision."""
    return decision_factory.create(submission=submission, **kwargs)


def create_appeal(original_decision: ModerationDecision, user: User = None, **kwargs) -> ModerationAppeal:
    """Create appeal."""
    return appeal_factory.create(original_decision=original_decision, user=user, **kwargs)


def create_queue_item(submission: SuspiciousSubmission, **kwargs) -> ModerationQueue:
    """Create queue item."""
    return queue_factory.create(submission=submission, **kwargs)


def create_bot(name: str, bot_type: str = "scanner", **kwargs) -> TaskBot:
    """Create bot."""
    return bot_factory.create(name=name, bot_type=bot_type, **kwargs)


def create_rule(name: str, rule_type: str = "threshold", **kwargs) -> AutoApprovalRule:
    """Create rule."""
    return rule_factory.create(name=name, rule_type=rule_type, **kwargs)


def create_test_scenario() -> Dict[str, Any]:
    """Create complete test scenario."""
    return test_data_manager.create_complete_test_scenario()


# Initialize logging
logger.info("Factories module initialized with factory classes for auto moderation")
