# =============================================================================
# auto_mod/repositories.py
# =============================================================================

"""
Repository pattern implementation for auto moderation system.
Provides data access abstraction and query optimization.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import models, transaction
from django.core.cache import cache

from .models import (
    SuspiciousSubmission, ModerationDecision, ModerationAppeal,
    ModerationQueue, TaskBot, AutoApprovalRule, MLModelVersion,
    ContentSignal, ProofScanner
)
from .selectors import BaseSelector
from .exceptions import RepositoryError

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base repository with common functionality."""
    
    def __init__(self, model_class):
        self.model_class = model_class
        self.cache_timeout = 300  # 5 minutes
    
    def get_by_id(self, obj_id: str) -> Optional[Any]:
        """Get object by ID."""
        try:
            return self.model_class.objects.get(id=obj_id)
        except self.model_class.DoesNotExist:
            return None
        except Exception as exc:
            logger.error(f"Get by ID failed: {exc}")
            raise RepositoryError(f"Failed to get {self.model_class.__name__}: {exc}")
    
    def get_all(self, limit: int = None) -> List[Any]:
        """Get all objects."""
        try:
            queryset = self.model_class.objects.all()
            if limit:
                queryset = queryset[:limit]
            return list(queryset)
        except Exception as exc:
            logger.error(f"Get all failed: {exc}")
            raise RepositoryError(f"Failed to get all {self.model_class.__name__}: {exc}")
    
    def create(self, **kwargs) -> Any:
        """Create new object."""
        try:
            return self.model_class.objects.create(**kwargs)
        except Exception as exc:
            logger.error(f"Create failed: {exc}")
            raise RepositoryError(f"Failed to create {self.model_class.__name__}: {exc}")
    
    def update(self, obj_id: str, **kwargs) -> Any:
        """Update object."""
        try:
            obj = self.get_by_id(obj_id)
            if not obj:
                raise RepositoryError(f"{self.model_class.__name__} {obj_id} not found")
            
            for key, value in kwargs.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)
            
            obj.save()
            return obj
        except Exception as exc:
            logger.error(f"Update failed: {exc}")
            raise RepositoryError(f"Failed to update {self.model_class.__name__}: {exc}")
    
    def delete(self, obj_id: str) -> bool:
        """Delete object."""
        try:
            obj = self.get_by_id(obj_id)
            if not obj:
                return False
            
            obj.delete()
            return True
        except Exception as exc:
            logger.error(f"Delete failed: {exc}")
            raise RepositoryError(f"Failed to delete {self.model_class.__name__}: {exc}")
    
    def count(self) -> int:
        """Count objects."""
        try:
            return self.model_class.objects.count()
        except Exception as exc:
            logger.error(f"Count failed: {exc}")
            raise RepositoryError(f"Failed to count {self.model_class.__name__}: {exc}")
    
    def exists(self, **kwargs) -> bool:
        """Check if object exists."""
        try:
            return self.model_class.objects.filter(**kwargs).exists()
        except Exception as exc:
            logger.error(f"Exists check failed: {exc}")
            return False


class SuspiciousSubmissionRepository(BaseRepository):
    """Repository for SuspiciousSubmission operations."""
    
    def __init__(self):
        super().__init__(SuspiciousSubmission)
    
    def by_status(self, status: str) -> List[SuspiciousSubmission]:
        """Get submissions by status."""
        try:
            return list(self.model_class.objects.filter(status=status))
        except Exception as exc:
            logger.error(f"Get by status failed: {exc}")
            raise RepositoryError(f"Failed to get submissions by status: {exc}")
    
    def by_user(self, user_id: Union[str, int]) -> List[SuspiciousSubmission]:
        """Get submissions by user."""
        try:
            return list(self.model_class.objects.filter(user_id=user_id))
        except Exception as exc:
            logger.error(f"Get by user failed: {exc}")
            raise RepositoryError(f"Failed to get submissions by user: {exc}")
    
    def by_date_range(self, start_date: datetime, end_date: datetime = None) -> List[SuspiciousSubmission]:
        """Get submissions by date range."""
        try:
            queryset = self.model_class.objects.filter(created_at__gte=start_date)
            if end_date:
                queryset = queryset.filter(created_at__lte=end_date)
            return list(queryset)
        except Exception as exc:
            logger.error(f"Get by date range failed: {exc}")
            raise RepositoryError(f"Failed to get submissions by date range: {exc}")
    
    def by_risk_score_range(self, min_score: float = None, max_score: float = None) -> List[SuspiciousSubmission]:
        """Get submissions by risk score range."""
        try:
            queryset = self.model_class.objects.all()
            if min_score is not None:
                queryset = queryset.filter(risk_score__gte=min_score)
            if max_score is not None:
                queryset = queryset.filter(risk_score__lte=max_score)
            return list(queryset)
        except Exception as exc:
            logger.error(f"Get by risk score range failed: {exc}")
            raise RepositoryError(f"Failed to get submissions by risk score range: {exc}")
    
    def high_risk(self, min_score: float = 7.0) -> List[SuspiciousSubmission]:
        """Get high risk submissions."""
        return self.by_risk_score_range(min_score=min_score)
    
    def pending_review(self) -> List[SuspiciousSubmission]:
        """Get submissions pending review."""
        return self.by_status('pending')
    
    def recent(self, days: int = 7) -> List[SuspiciousSubmission]:
        """Get recent submissions."""
        start_date = timezone.now() - timedelta(days=days)
        return self.by_date_range(start_date=start_date)
    
    def with_decisions(self) -> List[SuspiciousSubmission]:
        """Get submissions with decisions."""
        try:
            return list(self.model_class.objects.filter(decisions__isnull=False).distinct())
        except Exception as exc:
            logger.error(f"Get with decisions failed: {exc}")
            raise RepositoryError(f"Failed to get submissions with decisions: {exc}")
    
    def get_submission_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get submission statistics."""
        try:
            start_date = timezone.now() - timedelta(days=days)
            queryset = self.model_class.objects.filter(created_at__gte=start_date)
            
            total = queryset.count()
            pending = queryset.filter(status='pending').count()
            approved = queryset.filter(status='approved').count()
            rejected = queryset.filter(status='rejected').count()
            escalated = queryset.filter(status='escalated').count()
            
            return {
                'total': total,
                'pending': pending,
                'approved': approved,
                'rejected': rejected,
                'escalated': escalated,
                'approval_rate': (approved / total * 100) if total > 0 else 0,
                'rejection_rate': (rejected / total * 100) if total > 0 else 0
            }
        except Exception as exc:
            logger.error(f"Get stats failed: {exc}")
            raise RepositoryError(f"Failed to get submission stats: {exc}")


class ModerationDecisionRepository(BaseRepository):
    """Repository for ModerationDecision operations."""
    
    def __init__(self):
        super().__init__(ModerationDecision)
    
    def by_submission(self, submission_id: str) -> List[ModerationDecision]:
        """Get decisions by submission."""
        try:
            return list(self.model_class.objects.filter(submission_id=submission_id))
        except Exception as exc:
            logger.error(f"Get by submission failed: {exc}")
            raise RepositoryError(f"Failed to get decisions by submission: {exc}")
    
    def by_decider(self, decider_id: Union[str, int]) -> List[ModerationDecision]:
        """Get decisions by decider."""
        try:
            return list(self.model_class.objects.filter(decider_id=decider_id))
        except Exception as exc:
            logger.error(f"Get by decider failed: {exc}")
            raise RepositoryError(f"Failed to get decisions by decider: {exc}")
    
    def by_decision_type(self, decision_type: str) -> List[ModerationDecision]:
        """Get decisions by type."""
        try:
            return list(self.model_class.objects.filter(decision_type=decision_type))
        except Exception as exc:
            logger.error(f"Get by decision type failed: {exc}")
            raise RepositoryError(f"Failed to get decisions by type: {exc}")
    
    def by_date_range(self, start_date: datetime, end_date: datetime = None) -> List[ModerationDecision]:
        """Get decisions by date range."""
        try:
            queryset = self.model_class.objects.filter(decided_at__gte=start_date)
            if end_date:
                queryset = queryset.filter(decided_at__lte=end_date)
            return list(queryset)
        except Exception as exc:
            logger.error(f"Get by date range failed: {exc}")
            raise RepositoryError(f"Failed to get decisions by date range: {exc}")
    
    def automated(self) -> List[ModerationDecision]:
        """Get automated decisions."""
        try:
            return list(self.model_class.objects.filter(is_automated=True))
        except Exception as exc:
            logger.error(f"Get automated decisions failed: {exc}")
            raise RepositoryError(f"Failed to get automated decisions: {exc}")
    
    def manual(self) -> List[ModerationDecision]:
        """Get manual decisions."""
        try:
            return list(self.model_class.objects.filter(is_automated=False))
        except Exception as exc:
            logger.error(f"Get manual decisions failed: {exc}")
            raise RepositoryError(f"Failed to get manual decisions: {exc}")
    
    def with_appeals(self) -> List[ModerationDecision]:
        """Get decisions with appeals."""
        try:
            return list(self.model_class.objects.filter(appeals__isnull=False).distinct())
        except Exception as exc:
            logger.error(f"Get with appeals failed: {exc}")
            raise RepositoryError(f"Failed to get decisions with appeals: {exc}")
    
    def get_decision_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get decision statistics."""
        try:
            start_date = timezone.now() - timedelta(days=days)
            queryset = self.model_class.objects.filter(decided_at__gte=start_date)
            
            total = queryset.count()
            automated = queryset.filter(is_automated=True).count()
            manual = queryset.filter(is_automated=False).count()
            
            return {
                'total': total,
                'automated': automated,
                'manual': manual,
                'automation_rate': (automated / total * 100) if total > 0 else 0
            }
        except Exception as exc:
            logger.error(f"Get stats failed: {exc}")
            raise RepositoryError(f"Failed to get decision stats: {exc}")


class ModerationQueueRepository(BaseRepository):
    """Repository for ModerationQueue operations."""
    
    def __init__(self):
        super().__init__(ModerationQueue)
    
    def by_status(self, status: str) -> List[ModerationQueue]:
        """Get queue items by status."""
        try:
            return list(self.model_class.objects.filter(status=status))
        except Exception as exc:
            logger.error(f"Get by status failed: {exc}")
            raise RepositoryError(f"Failed to get queue items by status: {exc}")
    
    def by_assigned_to(self, assignee_id: Union[str, int]) -> List[ModerationQueue]:
        """Get queue items assigned to user."""
        try:
            return list(self.model_class.objects.filter(assigned_to_id=assignee_id))
        except Exception as exc:
            logger.error(f"Get by assigned to failed: {exc}")
            raise RepositoryError(f"Failed to get queue items by assigned to: {exc}")
    
    def by_priority(self, priority: str) -> List[ModerationQueue]:
        """Get queue items by priority."""
        try:
            return list(self.model_class.objects.filter(priority=priority))
        except Exception as exc:
            logger.error(f"Get by priority failed: {exc}")
            raise RepositoryError(f"Failed to get queue items by priority: {exc}")
    
    def unassigned(self) -> List[ModerationQueue]:
        """Get unassigned queue items."""
        try:
            return list(self.model_class.objects.filter(assigned_to__isnull=True))
        except Exception as exc:
            logger.error(f"Get unassigned failed: {exc}")
            raise RepositoryError(f"Failed to get unassigned queue items: {exc}")
    
    def overdue(self) -> List[ModerationQueue]:
        """Get overdue queue items."""
        try:
            return list(self.model_class.objects.filter(
                due_date__lt=timezone.now()
            ))
        except Exception as exc:
            logger.error(f"Get overdue failed: {exc}")
            raise RepositoryError(f"Failed to get overdue queue items: {exc}")
    
    def high_priority(self) -> List[ModerationQueue]:
        """Get high priority queue items."""
        try:
            return list(self.model_class.objects.filter(
                priority__in=['high', 'critical']
            ))
        except Exception as exc:
            logger.error(f"Get high priority failed: {exc}")
            raise RepositoryError(f"Failed to get high priority queue items: {exc}")
    
    def assign_to_user(self, queue_item_id: str, user_id: Union[str, int]) -> ModerationQueue:
        """Assign queue item to user."""
        try:
            queue_item = self.get_by_id(queue_item_id)
            if not queue_item:
                raise RepositoryError(f"Queue item {queue_item_id} not found")
            
            queue_item.assigned_to_id = user_id
            queue_item.status = 'assigned'
            queue_item.save()
            
            return queue_item
        except Exception as exc:
            logger.error(f"Assign to user failed: {exc}")
            raise RepositoryError(f"Failed to assign queue item to user: {exc}")
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        try:
            total = self.count()
            pending = len(self.by_status('pending'))
            assigned = len(self.by_status('assigned'))
            completed = len(self.by_status('completed'))
            overdue = len(self.overdue())
            unassigned = len(self.unassigned())
            
            return {
                'total': total,
                'pending': pending,
                'assigned': assigned,
                'completed': completed,
                'overdue': overdue,
                'unassigned': unassigned,
                'completion_rate': (completed / total * 100) if total > 0 else 0
            }
        except Exception as exc:
            logger.error(f"Get stats failed: {exc}")
            raise RepositoryError(f"Failed to get queue stats: {exc}")


class TaskBotRepository(BaseRepository):
    """Repository for TaskBot operations."""
    
    def __init__(self):
        super().__init__(TaskBot)
    
    def by_status(self, status: str) -> List[TaskBot]:
        """Get bots by status."""
        try:
            return list(self.model_class.objects.filter(status=status))
        except Exception as exc:
            logger.error(f"Get by status failed: {exc}")
            raise RepositoryError(f"Failed to get bots by status: {exc}")
    
    def by_bot_type(self, bot_type: str) -> List[TaskBot]:
        """Get bots by type."""
        try:
            return list(self.model_class.objects.filter(bot_type=bot_type))
        except Exception as exc:
            logger.error(f"Get by bot type failed: {exc}")
            raise RepositoryError(f"Failed to get bots by type: {exc}")
    
    def active(self) -> List[TaskBot]:
        """Get active bots."""
        try:
            return list(self.model_class.objects.filter(is_active=True))
        except Exception as exc:
            logger.error(f"Get active bots failed: {exc}")
            raise RepositoryError(f"Failed to get active bots: {exc}")
    
    def running(self) -> List[TaskBot]:
        """Get running bots."""
        return self.by_status('running')
    
    def idle(self) -> List[TaskBot]:
        """Get idle bots."""
        return self.by_status('idle')
    
    def error(self) -> List[TaskBot]:
        """Get bots with errors."""
        return self.by_status('error')
    
    def update_status(self, bot_id: str, status: str) -> TaskBot:
        """Update bot status."""
        try:
            bot = self.get_by_id(bot_id)
            if not bot:
                raise RepositoryError(f"Bot {bot_id} not found")
            
            bot.status = status
            bot.save()
            
            return bot
        except Exception as exc:
            logger.error(f"Update status failed: {exc}")
            raise RepositoryError(f"Failed to update bot status: {exc}")
    
    def get_bot_stats(self) -> Dict[str, Any]:
        """Get bot statistics."""
        try:
            total = self.count()
            active = len(self.active())
            running = len(self.running())
            idle = len(self.idle())
            error = len(self.error())
            
            return {
                'total': total,
                'active': active,
                'running': running,
                'idle': idle,
                'error': error,
                'active_rate': (active / total * 100) if total > 0 else 0
            }
        except Exception as exc:
            logger.error(f"Get stats failed: {exc}")
            raise RepositoryError(f"Failed to get bot stats: {exc}")


# Repository factory
class RepositoryFactory:
    """Factory for creating repository instances."""
    
    @staticmethod
    def submissions() -> SuspiciousSubmissionRepository:
        """Create submissions repository."""
        return SuspiciousSubmissionRepository()
    
    @staticmethod
    def decisions() -> ModerationDecisionRepository:
        """Create decisions repository."""
        return ModerationDecisionRepository()
    
    @staticmethod
    def queue() -> ModerationQueueRepository:
        """Create queue repository."""
        return ModerationQueueRepository()
    
    @staticmethod
    def bots() -> TaskBotRepository:
        """Create bots repository."""
        return TaskBotRepository()


# Caching repository wrapper
class CachedRepository:
    """Repository wrapper with caching."""
    
    def __init__(self, repository: BaseRepository, cache_timeout: int = 300):
        self.repository = repository
        self.cache_timeout = cache_timeout
    
    def get_by_id(self, obj_id: str) -> Optional[Any]:
        """Get object by ID with caching."""
        cache_key = f"{self.repository.model_class.__name__}:{obj_id}"
        cached_obj = cache.get(cache_key)
        
        if cached_obj:
            return cached_obj
        
        obj = self.repository.get_by_id(obj_id)
        if obj:
            cache.set(cache_key, obj, self.cache_timeout)
        
        return obj
    
    def clear_cache(self, obj_id: str = None) -> None:
        """Clear cache."""
        if obj_id:
            cache_key = f"{self.repository.model_class.__name__}:{obj_id}"
            cache.delete(cache_key)
        else:
            # Clear all cache for this model type
            pattern = f"{self.repository.model_class.__name__}:*"
            # This would require cache.delete_many with pattern matching
            pass


# Initialize logging
logger.info("Repositories module initialized with data access abstraction")
