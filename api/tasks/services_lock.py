"""
PART 8: TaskLockService - Exclusive Task Ownership Management

Design Pattern: Distributed Lock with Fallback
✓ User clicks task → acquire EXCLUSIVE lock
✓ Lock expires after 30 minutes (configurable)
✓ Expired locks auto-cleanup every 5 minutes
✓ Lock must be held to complete task (ownership validation)

This service handles:
1. Lock acquisition (with retry logic)
2. Lock release (manual or automatic)
3. Lock verification (ownership check)
4. Distributed coordination
"""

import logging
import time
from typing import Tuple, Optional
from datetime import timedelta
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.core.exceptions import ValidationError
from django_redis import get_redis_connection

from .models import TaskLock, TaskEventLog, MasterTask
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class OwnershipError(Exception):
    """User does not own lock for this task"""
    pass


class LockExpiredError(Exception):
    """Lock has expired and is no longer valid"""
    pass


class LockContentionError(Exception):
    """Another user currently holds lock for this task"""
    pass


class ConcurrencyError(Exception):
    """Lock was modified by another worker (optimistic locking failure)"""
    pass


class TaskLockService:
    """
    Service to manage exclusive task locks.
    
    Usage:
        lock_service = TaskLockService()
        success, lock = lock_service.acquire_lock(user_id=123, task_id=456)
        if success:
            # Proceed with task completion
            lock_service.release_lock(lock, reason='normal_completion')
        else:
            # Task is locked by another user
            return Response({'error': 'Task unavailable'})
    """
    
    DEFAULT_LOCK_TIMEOUT_SECONDS = 1800  # 30 minutes
    REDIS_LOCK_KEY_PREFIX = 'task_lock'
    
    def __init__(self, lock_timeout_seconds: int = DEFAULT_LOCK_TIMEOUT_SECONDS):
        """
        Initialize lock service with configurable timeout.
        
        Args:
            lock_timeout_seconds: How long locks remain valid (default: 30 min)
        """
        self.lock_timeout = timedelta(seconds=lock_timeout_seconds)
        self.redis_client = self._get_redis_client()
    
    def _get_redis_client(self):
        """Get Redis connection with fallback to None"""
        try:
            return get_redis_connection('default')
        except Exception as e:
            logger.warning(f"Redis unavailable, will use database-only locking: {e}")
            return None
    
    # =========================================================================
    # LOCK ACQUISITION
    # =========================================================================
    
    def acquire_lock(
        self,
        user_id: int,
        task_id: int,
        lock_type: str = TaskLock.LockType.EXCLUSIVE,
        worker_id: str = 'web_request'
    ) -> Tuple[bool, Optional[TaskLock]]:
        """
        Acquire lock on task for user (exclusive or shared).
        
        Args:
            user_id: User requesting the lock
            task_id: Task to lock
            lock_type: Type of lock (EXCLUSIVE = 1 user only)
            worker_id: Identifier of who acquired lock (for debugging)
        
        Returns:
            (success: bool, lock: TaskLock|None)
            - (True, lock_obj) if acquired successfully
            - (False, None) if task locked by another user
        
        Raises:
            ValidationError: User or task not found
        """
        try:
            # Validate user and task exist
            user = User.objects.get(id=user_id)
            task = MasterTask.objects.get(id=task_id)
        except User.DoesNotExist:
            raise ValidationError(f"User {user_id} not found")
        except MasterTask.DoesNotExist:
            raise ValidationError(f"Task {task_id} not found")
        
        # Calculate lock expiry
        expires_at = timezone.now() + self.lock_timeout
        
        # Try to acquire lock
        return self._create_lock_or_handle_contention(
            user=user,
            task=task,
            lock_type=lock_type,
            expires_at=expires_at,
            worker_id=worker_id
        )
    
    @transaction.atomic
    def _create_lock_or_handle_contention(
        self,
        user,
        task,
        lock_type: str,
        expires_at,
        worker_id: str
    ) -> Tuple[bool, Optional[TaskLock]]:
        """
        Attempt to create lock.
        If EXCLUSIVE lock exists and NOT expired, return False.
        If EXCLUSIVE lock exists and IS expired, delete it and retry.
        """
        try:
            # Attempt to create lock
            lock = TaskLock.objects.create(
                task=task,
                user=user,
                lock_type=lock_type,
                acquired_at=timezone.now(),
                expires_at=expires_at,
                lock_holder_worker=worker_id,
                version=0
            )
            
            # Log acquisition
            TaskEventLog.objects.create(
                event_type=TaskEventLog.EventType.LOCK_ACQUIRED,
                task=task,
                user=user,
                actor_type=TaskEventLog.ActorType.USER,
                actor_id=str(user.id),
                event_data={
                    'lock_id': str(lock.id),
                    'lock_type': lock_type,
                    'worker_id': worker_id
                }
            )
            
            logger.info(f"Lock acquired: {user.username} → {task.name}")
            return True, lock
        
        except IntegrityError:
            # EXCLUSIVE lock already exists for this task
            # Check if it's expired
            existing_lock = TaskLock.objects.filter(
                task=task,
                lock_type=TaskLock.LockType.EXCLUSIVE,
                released_at__isnull=True
            ).first()
            
            if not existing_lock:
                # Race condition - lock was released between check and create
                # Retry once
                return self._create_lock_or_handle_contention(
                    user=user,
                    task=task,
                    lock_type=lock_type,
                    expires_at=expires_at,
                    worker_id=worker_id
                )
            
            # Check if existing lock is expired
            if existing_lock.is_expired:
                logger.warning(f"Cleaning up expired lock: {existing_lock.id}")
                existing_lock.delete()
                # Retry creation
                return self._create_lock_or_handle_contention(
                    user=user,
                    task=task,
                    lock_type=lock_type,
                    expires_at=expires_at,
                    worker_id=worker_id
                )
            
            # Lock is held by another user
            logger.info(
                f"Lock contention: {user.username} could not lock {task.name} "
                f"(held by {existing_lock.user.username})"
            )
            raise LockContentionError(
                f"Task is currently being worked on by another user. "
                f"Try again in {existing_lock.time_remaining_seconds} seconds."
            )
    
    # =========================================================================
    # LOCK RELEASE
    # =========================================================================
    
    def release_lock(
        self,
        lock: TaskLock,
        reason: str = 'normal_completion'
    ) -> bool:
        """
        Release lock (task completed, abandoned, or timeout).
        
        Args:
            lock: TaskLock object to release
            reason: Why lock is released:
                   'normal_completion', 'user_abandon', 'expired', 'admin_override'
        
        Returns:
            True if released successfully
        """
        if not lock:
            return False
        
        if lock.released_at is not None:
            logger.debug(f"Lock {lock.id} already released")
            return False  # Already released
        
        lock.release(reason=reason)
        return True
    
    def release_lock_by_id(self, lock_id: str, reason: str = 'normal_completion') -> bool:
        """Release lock by ID"""
        try:
            lock = TaskLock.objects.get(id=lock_id)
            return self.release_lock(lock, reason=reason)
        except TaskLock.DoesNotExist:
            logger.warning(f"Lock {lock_id} not found for release")
            return False
    
    # =========================================================================
    # LOCK VERIFICATION (OWNERSHIP CHECK)
    # =========================================================================
    
    def verify_ownership(
        self,
        user_id: int,
        task_id: int
    ) -> Tuple[bool, Optional[TaskLock], Optional[str]]:
        """
        Verify that user owns active lock for task.
        Called before allowing completion.
        
        Returns:
            (is_owner: bool, lock: TaskLock|None, error_reason: str|None)
        """
        lock = TaskLock.objects.filter(
            user_id=user_id,
            task_id=task_id,
            lock_type=TaskLock.LockType.EXCLUSIVE,
            released_at__isnull=True
        ).first()
        
        if not lock:
            return False, None, "No active lock found (task not started)"
        
        if lock.is_expired:
            # Lock expired - clean it up
            lock.delete()
            return False, None, "Lock expired (task timeout)"
        
        # User owns active lock
        return True, lock, None
    
    # =========================================================================
    # BULK CLEANUP (For Expired Locks)
    # =========================================================================
    
    def cleanup_expired_locks(self, batch_size: int = 1000) -> int:
        """
        Delete expired locks (called by celery task every 5 minutes).
        
        Args:
            batch_size: Process N locks per call (prevent long locks)
        
        Returns:
            Number of locks deleted
        """
        expired_cutoff = timezone.now() - timedelta(minutes=5)
        
        expired_locks = TaskLock.objects.filter(
            released_at__isnull=True,
            expires_at__lt=expired_cutoff
        )[:batch_size]
        
        count = 0
        for lock in expired_locks:
            # Log cleanup event
            TaskEventLog.objects.create(
                event_type=TaskEventLog.EventType.LOCK_EXPIRED,
                task=lock.task,
                user=lock.user,
                actor_type=TaskEventLog.ActorType.SYSTEM,
                event_data={
                    'lock_id': str(lock.id),
                    'held_duration_seconds': int(
                        (lock.expires_at - lock.acquired_at).total_seconds()
                    ),
                    'reason': 'expired'
                }
            )
            
            lock.delete()
            count += 1
        
        if count > 0:
            logger.info(f"Cleaned up {count} expired task locks")
        
        return count
    
    # =========================================================================
    # LOCK STATUS QUERIES
    # =========================================================================
    
    def get_active_locks_for_task(self, task_id: int) -> list:
        """Get all active locks for a task"""
        return list(
            TaskLock.objects.filter(
                task_id=task_id,
                released_at__isnull=True,
                lock_type=TaskLock.LockType.EXCLUSIVE
            )
        )
    
    def get_user_active_locks(self, user_id: int) -> list:
        """Get all active locks held by user"""
        return list(
            TaskLock.objects.filter(
                user_id=user_id,
                released_at__isnull=True
            ).select_related('task')
        )
    
    def count_concurrent_users(self, task_id: int) -> int:
        """Count unique users currently working on a task"""
        return TaskLock.objects.filter(
            task_id=task_id,
            released_at__isnull=True
        ).values('user_id').distinct().count()
    
    # =========================================================================
    # LOCK FORCE RELEASE (ADMIN OVERRIDE)
    # =========================================================================
    
    def force_release_lock(
        self,
        lock_id: str,
        admin_user,
        reason: str = 'admin_override'
    ) -> bool:
        """
        Admin-only: Force release a lock.
        
        Args:
            lock_id: Lock to release
            admin_user: Admin user performing override
            reason: Why admin released lock
        
        Returns:
            True if override successful
        """
        try:
            lock = TaskLock.objects.get(id=lock_id)
            lock.released_at = timezone.now()
            lock.save(update_fields=['released_at'])
            
            # Log admin override
            TaskEventLog.objects.create(
                event_type=TaskEventLog.EventType.ADMIN_OVERRIDE,
                task=lock.task,
                user=lock.user,
                actor_type=TaskEventLog.ActorType.ADMIN,
                actor_id=str(admin_user.id),
                event_data={
                    'lock_id': str(lock.id),
                    'admin_user_id': admin_user.id,
                    'reason': reason
                }
            )
            
            logger.warning(
                f"Admin {admin_user.username} released lock {lock_id} "
                f"for {lock.user.username} on {lock.task.name}"
            )
            
            return True
        
        except TaskLock.DoesNotExist:
            logger.error(f"Lock {lock_id} not found for admin override")
            return False


# =========================================================================
# HELPER FUNCTION (Module-level convenience)
# =========================================================================

def acquire_task_lock(
    user_id: int,
    task_id: int,
    timeout_seconds: int = 1800
) -> Tuple[bool, Optional[TaskLock]]:
    """
    Convenience function to acquire lock.
    
    Example:
        success, lock = acquire_task_lock(user_id=123, task_id=456)
        if success:
            # Proceed with task completion
            ...
    """
    service = TaskLockService(lock_timeout_seconds=timeout_seconds)
    return service.acquire_lock(user_id, task_id)
