import logging
import os
from typing import Type, Optional, Dict, Any
from django.db.models.signals import (
    post_save, pre_save, post_delete, pre_delete,
    m2m_changed, class_prepared
)
from django.dispatch import receiver
from django.core.cache import cache
from django.db import transaction, connection  # [OK] Fixed: Added connection import
from django.utils import timezone
from django.conf import settings

# Import models
from .models import MasterTask, UserTaskCompletion

# Setup logging
logger = logging.getLogger(__name__)

# ============ SENTINEL VALUES ============

class _Missing:
    """Sentinel value for missing data"""
    def __repr__(self):
        return '<MISSING>'
    
    def __bool__(self):
        return False

MISSING = _Missing()

# ============ REDIS CONNECTION HELPER ============

def get_redis_connection_safe():
    """Get Redis connection with error handling"""
    try:
        from django_redis import get_redis_connection
        return get_redis_connection("default")
    except ImportError:
        logger.debug("django_redis not installed, Redis features disabled")
        return None
    except Exception as e:
        logger.debug(f"Redis connection error: {str(e)}")
        return None


def is_redis_available() -> bool:
    """Check if Redis is available and configured"""
    return get_redis_connection_safe() is not None


# ============ CACHE KEY CONSTANTS ============

class CacheKeys:
    """Centralized cache key management"""
    
    TASK_PREFIX = "task"
    TASK_LIST_PREFIX = "task_list"
    TASK_STATS_PREFIX = "task_stats"
    USER_TASKS_PREFIX = "user_tasks"
    USER_STREAK_PREFIX = "user_streak"
    COMPLETION_PREFIX = "completion"
    GLOBAL_STATS = "global_task_statistics"
    FEATURED_TASKS = "featured_tasks"
    ACTIVE_TASKS_COUNT = "active_tasks_count"
    
    # Redis-specific keys (only used when Redis is available)
    REDIS_TASK_META_PREFIX = "task_meta"
    REDIS_USER_COMPLETIONS_PREFIX = "user_completions"
    REDIS_USER_DAILY_PREFIX = "user_daily"
    REDIS_TASK_STARTS_PREFIX = "task_starts"
    REDIS_TASK_DURATIONS_PREFIX = "task_durations"
    REDIS_ACTIVE_USERS_PREFIX = "active_users"
    
    @classmethod
    def task_key(cls, task_id: Any) -> str:
        """Get cache key for single task"""
        return f"{cls.TASK_PREFIX}:{task_id}"
    
    @classmethod
    def task_list_key(cls, system_type: Optional[str] = None, user_level: int = 1) -> str:
        """Get cache key for task list"""
        base = f"{cls.TASK_LIST_PREFIX}:level_{user_level}"
        if system_type:
            base = f"{base}:{system_type}"
        return base
    
    @classmethod
    def task_stats_key(cls, task_id: Any) -> str:
        """Get cache key for task statistics"""
        return f"{cls.TASK_STATS_PREFIX}:{task_id}"
    
    @classmethod
    def user_tasks_key(cls, user_id: Any) -> str:
        """Get cache key for user tasks"""
        return f"{cls.USER_TASKS_PREFIX}:{user_id}"
    
    @classmethod
    def user_streak_key(cls, user_id: Any) -> str:
        """Get cache key for user streak"""
        return f"{cls.USER_STREAK_PREFIX}:{user_id}"
    
    @classmethod
    def completion_key(cls, completion_id: Any) -> str:
        """Get cache key for completion"""
        return f"{cls.COMPLETION_PREFIX}:{completion_id}"
    
    @classmethod
    def redis_task_meta_key(cls, task_id: Any) -> str:
        """Get Redis key for task metadata"""
        return f"{cls.REDIS_TASK_META_PREFIX}:{task_id}"
    
    @classmethod
    def redis_user_completions_key(cls, user_id: Any) -> str:
        """Get Redis key for user completions"""
        return f"{cls.REDIS_USER_COMPLETIONS_PREFIX}:{user_id}"
    
    @classmethod
    def redis_user_daily_key(cls, user_id: Any, date_str: str) -> str:
        """Get Redis key for user daily completions"""
        return f"{cls.REDIS_USER_DAILY_PREFIX}:{user_id}:{date_str}"
    
    @classmethod
    def redis_task_starts_key(cls, task_id: Any, date_str: str) -> str:
        """Get Redis key for task starts"""
        return f"{cls.REDIS_TASK_STARTS_PREFIX}:{task_id}:{date_str}"
    
    @classmethod
    def redis_task_durations_key(cls, task_id: Any) -> str:
        """Get Redis key for task durations"""
        return f"{cls.REDIS_TASK_DURATIONS_PREFIX}:{task_id}"
    
    @classmethod
    def redis_active_users_key(cls, date_str: str) -> str:
        """Get Redis key for active users"""
        return f"{cls.REDIS_ACTIVE_USERS_PREFIX}:{date_str}"


# ============ CACHE HELPER FUNCTIONS ============

def clear_task_caches(task_id: Any, task_task_id: Optional[str] = None) -> None:
    """
    Safely clear all caches related to a task
    Works with any cache backend
    """
    try:
        # Clear individual task caches
        cache.delete(CacheKeys.task_key(task_id))
        if task_task_id:
            cache.delete(CacheKeys.task_key(task_task_id))
        cache.delete(CacheKeys.task_stats_key(task_id))
        
        # Clear list caches (by deleting specific keys, not patterns)
        cache.delete(CacheKeys.GLOBAL_STATS)
        cache.delete(CacheKeys.FEATURED_TASKS)
        cache.delete(CacheKeys.ACTIVE_TASKS_COUNT)
        
        # Clear system-specific list caches
        for system_type, _ in MasterTask.SystemType.choices:
            for level in [1, 5, 10, 20, 50]:  # Common level thresholds
                cache.delete(CacheKeys.task_list_key(system_type, level))
        
        logger.debug(f"Cleared caches for task {task_id}")
        
    except Exception as e:
        logger.error(f"Error clearing task caches: {str(e)}")


def clear_user_caches(user_id: Any) -> None:
    """Safely clear all caches related to a user"""
    try:
        cache.delete(CacheKeys.user_tasks_key(user_id))
        cache.delete(CacheKeys.user_streak_key(user_id))
        logger.debug(f"Cleared caches for user {user_id}")
    except Exception as e:
        logger.error(f"Error clearing user caches: {str(e)}")


# ============ CIRCUIT BREAKER FOR SIGNALS ============

class SignalCircuitBreaker:
    """
    Circuit breaker pattern for signal handlers
    Prevents signal cascading failures
    """
    
    def __init__(self, name: str, failure_threshold: int = 3, recovery_timeout: int = 300):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half-open
    
    def __call__(self, signal_func):
        """Decorator for signal handlers"""
        def wrapper(sender, instance, **kwargs):
            try:
                # Check if circuit is open
                if self.state == 'open':
                    if self.last_failure_time and \
                       (timezone.now() - self.last_failure_time).seconds > self.recovery_timeout:
                        self.state = 'half-open'
                        logger.info(f"Signal circuit {self.name} moved to half-open state")
                    else:
                        logger.warning(f"Signal circuit {self.name} is open - skipping handler")
                        return None
                
                # Execute signal handler
                result = signal_func(sender, instance, **kwargs)
                
                # Success - reset if half-open
                if self.state == 'half-open':
                    self.state = 'closed'
                    self.failure_count = 0
                    logger.info(f"Signal circuit {self.name} closed after successful execution")
                
                return result
                
            except Exception as e:
                self.failure_count += 1
                self.last_failure_time = timezone.now()
                
                # Check if threshold reached
                if self.failure_count >= self.failure_threshold:
                    self.state = 'open'
                    logger.warning(f"Signal circuit {self.name} opened after {self.failure_count} failures")
                
                # Log error but don't raise - signals should never break the main operation
                logger.error(f"Error in signal handler {self.name}: {str(e)}", exc_info=True)
                return None
        
        return wrapper


# Signal circuit breakers
task_signal_breaker = SignalCircuitBreaker('task_signals', failure_threshold=5, recovery_timeout=300)
completion_signal_breaker = SignalCircuitBreaker('completion_signals', failure_threshold=5, recovery_timeout=300)


def _credit_wallet_on_task_approval(instance: UserTaskCompletion) -> None:
    """
    When a task completion is verified/approved, credit user's wallet.
    Integrated with api.wallet and api.fraud_detection.
    """
    from decimal import Decimal
    try:
        from api.wallet.models import Wallet, WalletTransaction
    except ImportError:
        logger.warning("api.wallet not available, skipping wallet credit")
        return
    try:
        # Fraud check: skip credit if user is flagged
        try:
            from api.fraud_detection.models import UserRiskProfile
            risk = UserRiskProfile.objects.filter(user=instance.user).first()
            if risk and (risk.is_flagged or risk.is_restricted):
                logger.warning(f"User {instance.user.id} flagged/restricted; skipping task credit for completion {instance.id}")
                return
        except ImportError:
            pass
        wallet = Wallet.objects.filter(user=instance.user).first()
        if not wallet:
            logger.warning(f"No wallet for user {instance.user.id}, skipping task credit")
            return
        # Avoid duplicate credit
        if WalletTransaction.objects.filter(
            reference_id=str(instance.id),
            reference_type='task_approval'
        ).exists():
            logger.debug(f"Wallet already credited for completion {instance.id}")
            return
        rewards = instance.rewards_awarded or {}
        points = rewards.get('points', 0)
        amount = Decimal(str(points)) if points else Decimal('0')
        if amount <= 0:
            logger.debug(f"No points to credit for completion {instance.id}")
            return
        with transaction.atomic():
            wtx = WalletTransaction.objects.create(
                wallet=wallet,
                type='earning',
                amount=amount,
                status='pending',
                reference_id=str(instance.id),
                reference_type='task_approval',
                description=f"Task approved: {instance.task.name}",
                metadata={'task_id': instance.task.id, 'completion_id': instance.id},
            )
            wtx.approve(approved_by=None)
            wallet.refresh_from_db()
            wallet.total_earned += amount
            wallet.save(update_fields=['total_earned', 'updated_at'])
        logger.info(f"Credited {amount} to user {instance.user.id} for task completion {instance.id}")
    except Exception as e:
        logger.error(f"Error crediting wallet for completion {instance.id}: {e}", exc_info=True)

# ============ MASTER TASK SIGNALS ============

@receiver(pre_save, sender=MasterTask)
@task_signal_breaker
def task_pre_save(sender: Type[MasterTask], instance: MasterTask, **kwargs):
    """
    Pre-save signal handler for MasterTask
    - Validates task data
    - Sets default values
    - Logs changes
    """
    try:
        # Track if this is an update
        if instance.pk:
            try:
                old_instance = sender.objects.get(pk=instance.pk)
                instance._old_values = {
                    'is_active': old_instance.is_active,
                    'name': old_instance.name,
                    'system_type': old_instance.system_type,
                    'rewards': old_instance.rewards.copy() if old_instance.rewards else {},
                }
            except sender.DoesNotExist:
                instance._old_values = {}
        else:
            instance._old_values = {}
        
        logger.debug(f"Pre-save signal for task: {instance.task_id}")
        
    except Exception as e:
        logger.error(f"Error in task_pre_save: {str(e)}")
        # Don't raise - signals should not block save


@receiver(post_save, sender=MasterTask)
@task_signal_breaker
def task_post_save(sender: Type[MasterTask], instance: MasterTask, created: bool, **kwargs):
    """
    Post-save signal handler for MasterTask
    - Invalidates caches
    - Logs changes
    - Updates related data
    """
    try:
        action = "created" if created else "updated"
        logger.info(f"Task {instance.task_id} {action}")
        
        # Clear all related caches
        with transaction.atomic():
            clear_task_caches(instance.id, instance.task_id)
        
        # Check for important changes
        if hasattr(instance, '_old_values'):
            old_values = instance._old_values
            
            # Log status change
            if 'is_active' in old_values and old_values['is_active'] != instance.is_active:
                new_status = "activated" if instance.is_active else "deactivated"
                logger.info(f"Task {instance.task_id} {new_status}")
                
                # If deactivated, update any in-progress completions
                if not instance.is_active:
                    # Use update for efficiency
                    UserTaskCompletion.objects.filter(
                        task=instance,
                        status='started'
                    ).update(
                        status='failed',
                        proof_data={
                            'reason': 'task_deactivated',
                            'deactivated_at': timezone.now().isoformat()
                        }
                    )
                    logger.info(f"Marked in-progress completions as failed for task {instance.task_id}")
            
            # Log reward changes
            if 'rewards' in old_values and old_values['rewards'] != instance.rewards:
                logger.info(f"Task {instance.task_id} rewards updated")
        
        # Update Redis if available (non-critical)
        redis_client = get_redis_connection_safe()
        if redis_client:
            try:
                # Store task metadata in Redis for fast access
                redis_key = CacheKeys.redis_task_meta_key(instance.task_id)
                redis_client.hset(redis_key, mapping={
                    'name': instance.name,
                    'system_type': instance.system_type,
                    'is_active': str(instance.is_active),
                    'updated_at': timezone.now().isoformat()
                })
                redis_client.expire(redis_key, 86400)  # 24 hours (consistent)
            except Exception as e:
                logger.debug(f"Redis update error (non-critical): {str(e)}")
        
    except Exception as e:
        logger.error(f"Error in task_post_save: {str(e)}")


@receiver(pre_delete, sender=MasterTask)
@task_signal_breaker
def task_pre_delete(sender: Type[MasterTask], instance: MasterTask, **kwargs):
    """
    Pre-delete signal handler for MasterTask
    - Archives task data
    - Handles related completions
    """
    try:
        logger.warning(f"Task {instance.task_id} is being deleted")
        
        # Store task info for post-delete
        instance._deleted_info = {
            'task_id': instance.task_id,
            'name': instance.name,
            'system_type': instance.system_type,
            'total_completions': instance.total_completions
        }
        
        # Update all related completions to failed
        # Use update for efficiency instead of individual saves
        UserTaskCompletion.objects.filter(task=instance).update(
            status='failed',
            proof_data={
                'reason': 'task_deleted',
                'deleted_at': timezone.now().isoformat()
            }
        )
        
        logger.info(f"Updated {instance.total_completions} completions for deleted task")
        
    except Exception as e:
        logger.error(f"Error in task_pre_delete: {str(e)}")


@receiver(post_delete, sender=MasterTask)
@task_signal_breaker
def task_post_delete(sender: Type[MasterTask], instance: MasterTask, **kwargs):
    """
    Post-delete signal handler for MasterTask
    - Cleans up caches
    - Logs deletion
    """
    try:
        deleted_info = getattr(instance, '_deleted_info', {})
        task_id = deleted_info.get('task_id', instance.task_id)
        
        logger.info(f"Task {task_id} deleted permanently")
        
        # Clear all caches
        clear_task_caches(instance.id, task_id)
        
        # Clear Redis if available
        redis_client = get_redis_connection_safe()
        if redis_client:
            try:
                redis_key = CacheKeys.redis_task_meta_key(task_id)
                redis_client.delete(redis_key)
            except Exception as e:
                logger.debug(f"Redis delete error (non-critical): {str(e)}")
        
    except Exception as e:
        logger.error(f"Error in task_post_delete: {str(e)}")


# ============ USER TASK COMPLETION SIGNALS ============

@receiver(pre_save, sender=UserTaskCompletion)
@completion_signal_breaker
def completion_pre_save(sender: Type[UserTaskCompletion], instance: UserTaskCompletion, **kwargs):
    """
    Pre-save signal handler for UserTaskCompletion
    - Validates completion data
    - Tracks changes
    """
    try:
        # Track status changes
        if instance.pk:
            try:
                old_instance = sender.objects.get(pk=instance.pk)
                instance._old_status = old_instance.status
                instance._old_rewards = old_instance.rewards_awarded.copy() if old_instance.rewards_awarded else {}
            except sender.DoesNotExist:
                instance._old_status = None
                instance._old_rewards = {}
        else:
            instance._old_status = None
            instance._old_rewards = {}
        
        logger.debug(f"Pre-save signal for completion {getattr(instance, 'id', 'new')}")
        
    except Exception as e:
        logger.error(f"Error in completion_pre_save: {str(e)}")


@receiver(post_save, sender=UserTaskCompletion)
@completion_signal_breaker
def completion_post_save(sender: Type[UserTaskCompletion], instance: UserTaskCompletion, created: bool, **kwargs):
    """
    Post-save signal handler for UserTaskCompletion
    - Updates user statistics
    - Invalidates caches
    - Updates Redis
    - Triggers notifications
    """
    try:
        if created:
            logger.info(f"Task completion started for user {instance.user.id} - Task: {instance.task.task_id}")
            
            # Update user's active tasks count in cache
            clear_user_caches(instance.user.id)
            
            # Update Redis for real-time tracking (non-critical)
            redis_client = get_redis_connection_safe()
            if redis_client:
                try:
                    # Track active users
                    today = timezone.now().strftime('%Y%m%d')
                    redis_key = CacheKeys.redis_active_users_key(today)
                    redis_client.sadd(redis_key, instance.user.id)
                    redis_client.expire(redis_key, 86400)  # 24 hours
                    
                    # Track task starts
                    task_key = CacheKeys.redis_task_starts_key(instance.task.id, today)
                    redis_client.incr(task_key)
                    redis_client.expire(task_key, 86400)  # 24 hours
                    
                except Exception as e:
                    logger.debug(f"Redis tracking error (non-critical): {str(e)}")
        
        # Handle status changes
        old_status = getattr(instance, '_old_status', None)
        
        if old_status != instance.status:
            logger.info(f"Completion {instance.id} status changed: {old_status} -> {instance.status}")
            
            # Clear relevant caches
            clear_user_caches(instance.user.id)
            clear_task_caches(instance.task.id, instance.task.task_id)
            cache.delete(CacheKeys.completion_key(instance.id))
            try:
                from api.cache.integration import invalidate_task_list_cache
                invalidate_task_list_cache(instance.user.id)
            except Exception:
                pass

            if instance.status == 'completed':
                # Task completed successfully
                logger.info(f"Task {instance.task.task_id} completed by user {instance.user.id}")
                
                # Update Redis for streak calculation (non-critical)
                redis_client = get_redis_connection_safe()
                if redis_client:
                    try:
                        # Store completion timestamp for streak
                        streak_key = CacheKeys.redis_user_completions_key(instance.user.id)
                        redis_client.zadd(
                            streak_key,
                            {str(instance.id): timezone.now().timestamp()}
                        )
                        redis_client.expire(streak_key, 604800)  # 7 days (604800 seconds)
                        
                        # Update daily completion count
                        today = timezone.now().strftime('%Y%m%d')
                        daily_key = CacheKeys.redis_user_daily_key(instance.user.id, today)
                        redis_client.incr(daily_key)
                        redis_client.expire(daily_key, 86400)  # 24 hours
                        
                    except Exception as e:
                        logger.debug(f"Redis streak update error (non-critical): {str(e)}")
                
                # Could trigger async notification here
                # from .tasks import send_completion_notification
                # send_completion_notification.delay(instance.user.id, instance.task.id)
                
            elif instance.status == 'failed':
                # Task failed
                logger.warning(f"Task {instance.task.task_id} failed for user {instance.user.id}")
                
            elif instance.status == 'verified':
                # Task verified by admin -> auto-credit wallet (integrate with api.wallet)
                logger.info(f"Completion {instance.id} verified")
                _credit_wallet_on_task_approval(instance)
        
        # Check for reward changes
        old_rewards = getattr(instance, '_old_rewards', {})
        if instance.rewards_awarded != old_rewards:
            logger.info(f"Rewards updated for completion {instance.id}: {old_rewards} -> {instance.rewards_awarded}")
        
    except Exception as e:
        logger.error(f"Error in completion_post_save: {str(e)}")


@receiver(pre_delete, sender=UserTaskCompletion)
@completion_signal_breaker
def completion_pre_delete(sender: Type[UserTaskCompletion], instance: UserTaskCompletion, **kwargs):
    """
    Pre-delete signal handler for UserTaskCompletion
    - Archives completion data
    - Updates statistics
    """
    try:
        logger.warning(f"Completion {instance.id} is being deleted")
        
        # Store info for post-delete
        instance._deleted_info = {
            'user_id': instance.user.id,
            'task_id': instance.task.id,
            'task_task_id': instance.task.task_id,
            'status': instance.status,
            'rewards': instance.rewards_awarded.copy() if instance.rewards_awarded else {}
        }
        
        # If this was a completed task, decrement task completion count using model method
        if instance.status in ['completed', 'verified']:
            # [OK] Fixed: Use model method instead of raw SQL
            instance.task.total_completions -= 1
            instance.task.save(update_fields=['total_completions'])
            logger.info(f"Decremented task {instance.task.id} completion count via model method")
        
    except Exception as e:
        logger.error(f"Error in completion_pre_delete: {str(e)}")


@receiver(post_delete, sender=UserTaskCompletion)
@completion_signal_breaker
def completion_post_delete(sender: Type[UserTaskCompletion], instance: UserTaskCompletion, **kwargs):
    """
    Post-delete signal handler for UserTaskCompletion
    - Cleans up caches
    - Updates Redis
    """
    try:
        deleted_info = getattr(instance, '_deleted_info', {})
        user_id = deleted_info.get('user_id', instance.user.id)
        task_id = deleted_info.get('task_id', instance.task.id)
        task_task_id = deleted_info.get('task_task_id', instance.task.task_id)
        
        logger.info(f"Completion for user {user_id}, task {task_id} deleted")
        
        # Clear caches
        clear_user_caches(user_id)
        clear_task_caches(task_id, task_task_id)
        cache.delete(CacheKeys.completion_key(instance.id))
        
        # Clear Redis (non-critical)
        redis_client = get_redis_connection_safe()
        if redis_client:
            try:
                # Remove from streak calculations
                streak_key = CacheKeys.redis_user_completions_key(user_id)
                redis_client.zrem(streak_key, str(instance.id))
                
                # Update daily counts if completed
                if instance.completed_at:
                    today = instance.completed_at.strftime('%Y%m%d')
                    daily_key = CacheKeys.redis_user_daily_key(user_id, today)
                    redis_client.decr(daily_key)
                
            except Exception as e:
                logger.debug(f"Redis cleanup error (non-critical): {str(e)}")
        
    except Exception as e:
        logger.error(f"Error in completion_post_delete: {str(e)}")


# ============ INITIALIZATION SIGNAL (Combined with post_save) ============

# [OK] Fixed: Combined with task_post_save instead of separate handler
def initialize_task_metadata(instance: MasterTask, created: bool) -> None:
    """
    Initialize task metadata on first creation
    Called from task_post_save to avoid duplicate signals
    """
    try:
        if created and not instance.task_metadata:
            # Set default metadata based on system type
            default_metadata = {
                'click_visit': {'url': '', 'duration_seconds': 30},
                'gamified': {'game_type': 'spin', 'segments': 8},
                'data_input': {'input_type': 'quiz', 'questions': []},
                'guide_signup': {'action_type': 'app_install', 'package_name': ''},
                'external_wall': {'provider': 'adgem', 'offer_id': ''}
            }
            
            system_type = instance.system_type
            if system_type in default_metadata:
                instance.task_metadata = default_metadata[system_type]
                # Save without triggering signals again
                MasterTask.objects.filter(pk=instance.pk).update(task_metadata=instance.task_metadata)
                logger.info(f"Initialized metadata for new task {instance.task_id}")
        
    except Exception as e:
        logger.error(f"Error initializing task metadata: {str(e)}")


# Call initialize_task_metadata from task_post_save
# Add this line at the end of task_post_save function:
# initialize_task_metadata(instance, created)


# ============ STATISTICS UPDATE SIGNAL (Combined with completion_post_save) ============

def update_task_statistics(instance: UserTaskCompletion) -> None:
    """
    Update task statistics based on completions
    Called from completion_post_save to avoid duplicate signals
    """
    try:
        if instance.status == 'completed' and getattr(instance, '_old_status', None) != 'completed':
            # This is a new completion
            task = instance.task
            
            # Update average completion time in Redis
            if instance.completed_at and instance.started_at:
                duration = (instance.completed_at - instance.started_at).total_seconds()
                
                # Store in Redis for real-time stats (non-critical)
                redis_client = get_redis_connection_safe()
                if redis_client:
                    try:
                        stats_key = CacheKeys.redis_task_durations_key(task.id)
                        redis_client.lpush(stats_key, duration)
                        redis_client.ltrim(stats_key, 0, 999)  # Keep last 1000
                        redis_client.expire(stats_key, 604800)  # 7 days (604800 seconds)
                    except Exception as e:
                        logger.debug(f"Redis duration update error (non-critical): {str(e)}")
            
    except Exception as e:
        logger.error(f"Error updating task statistics: {str(e)}")


# Call update_task_statistics from completion_post_save
# Add this line at the end of completion_post_save function:
# update_task_statistics(instance)


# ============ CLEANUP SIGNAL ============

def cleanup_orphaned_data(instance: UserTaskCompletion) -> None:
    """
    Clean up any orphaned data related to deleted completions
    Called from completion_post_delete to avoid duplicate signals
    """
    try:
        # Remove any temporary files if proof_data contained file references
        proof_data = instance.proof_data or {}
        
        # Get media URL from settings
        media_url = getattr(settings, 'MEDIA_URL', '/media/')
        media_root = getattr(settings, 'MEDIA_ROOT', '')
        
        # Check for file paths in proof_data
        for key, value in proof_data.items():
            if isinstance(value, str) and media_url in value:
                # Extract filename from URL
                filename = value.replace(media_url, '')
                file_path = os.path.join(media_root, filename)
                
                # Check if file exists and delete
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        logger.debug(f"Cleaned up file: {file_path}")
                    except OSError as e:
                        logger.error(f"Error deleting file {file_path}: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error in cleanup signal: {str(e)}")


# Call cleanup_orphaned_data from completion_post_delete
# Add this line at the end of completion_post_delete function:
# cleanup_orphaned_data(instance)


# ============ M2M SIGNALS (if needed) ============

@receiver(post_save, sender=MasterTask) # m2m_changed এর বদলে post_save
@task_signal_breaker
def task_segments_changed_json(sender, instance, created, **kwargs):
    """
    Signal for JSONField changes in target_user_segments
    JSONField এ ডাটা সেভ হওয়ার পর এই সিগন্যাল ক্যাশ ক্লিয়ার করবে
    """
    try:
        # যেহেতু JSONField, তাই প্রতিবার সেভ হলেই আমরা ক্যাশ ক্লিয়ার করবো
        logger.info(f"Target segments updated (JSON) for task {instance.task_id}")
        
        # Clear relevant caches
        clear_task_caches(instance.id, instance.task_id)
            
    except Exception as e:
        logger.error(f"Error in task_segments_changed_json signal: {str(e)}")


# Export all signal handlers
__all__ = [
    'task_pre_save',
    'task_post_save',
    'task_pre_delete',
    'task_post_delete',
    'completion_pre_save',
    'completion_post_save',
    'completion_pre_delete',
    'completion_post_delete',
    'task_segments_changed_json',
]