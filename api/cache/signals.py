# api/cache/signals.py
"""
Cache invalidation signals.
Connect these to model post_save/post_delete to clear cache via CacheInvalidator.
Uses CacheKeyGenerator patterns and RedisService.
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def get_cache_invalidator():
    """Lazy-load cache service and invalidator."""
    from api.cache.manager import cache_manager
    from api.cache.services.CacheInvalidator import CacheInvalidator
    cache_service = cache_manager.get_cache("default")
    return CacheInvalidator(cache_service)


def invalidate_by_pattern(pattern: str) -> int:
    """
    Invalidate all cache keys matching pattern.
    Pattern should include namespace if keys are stored with it.
    """
    try:
        from api.cache.manager import cache_manager
        from api.cache.keys.CacheKeyGenerator import CacheKeyGenerator
        
        cache_service = cache_manager.get_cache("default")
        # Prepend namespace to match stored keys
        ns = CacheKeyGenerator().namespace
        full_pattern = f"{ns}:*{pattern}*" if ns else f"*{pattern}*"
        
        keys = cache_service.keys(full_pattern)
        if keys:
            return cache_service.delete_many(keys)
        return 0
    except Exception as e:
        logger.warning(f"Pattern invalidation failed: {e}")
        return 0


def invalidate_model_cache(instance, operation: str, key_template: str = None, **kwargs):
    """
    Invalidate cache for a model instance.
    Uses CacheInvalidator and also performs direct pattern-based invalidation
    with namespace for Redis compatibility.
    
    Args:
        instance: Model instance
        operation: Operation name (user_update, task_delete, etc.)
        key_template: Optional key template, e.g. 'user:{user_id}'
    """
    try:
        invalidator = get_cache_invalidator()
        
        # Build key from template or fallback
        if key_template:
            key = key_template
            for attr in ['user_id', 'task_id', 'offer_id', 'pk', 'id']:
                val = getattr(instance, attr, None)
                if val is not None:
                    key = key.replace(f"{{{attr}}}", str(val))
        else:
            key = f"{instance.__class__.__name__.lower()}:{instance.pk}"
        
        invalidator.invalidate(key, operation, **kwargs)
        
        # Direct pattern invalidation with namespace (Redis keys include earnify: prefix)
        from api.cache.manager import cache_manager
        from api.cache.keys.CacheKeyGenerator import CacheKeyGenerator
        cache_service = cache_manager.get_cache("default")
        ns = CacheKeyGenerator().namespace
        pattern = f"{ns}:{key}:*" if ns else f"{key}:*"
        keys = cache_service.keys(pattern)
        if keys:
            cache_service.delete_many(keys)
    except Exception as e:
        logger.warning(f"Model cache invalidation failed: {e}")


# ============ User / Wallet ============

@receiver(post_save)
def invalidate_user_cache_on_save(sender, instance, created, **kwargs):
    """Invalidate user-related cache when User or UserProfile changes."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    if sender == User:
        invalidator = get_cache_invalidator()
        op = 'user_create' if created else 'user_update'
        invalidator.invalidate(f"user:{instance.id}", op, user_id=instance.id)


@receiver(post_save)
def invalidate_wallet_cache_on_save(sender, instance, created, **kwargs):
    """Invalidate wallet/balance cache when Wallet changes."""
    try:
        from api.wallet.models import Wallet
        if sender == Wallet and hasattr(instance, 'user_id'):
            invalidator = get_cache_invalidator()
            invalidator.invalidate(f"user:{instance.user_id}", 'wallet_update', user_id=instance.user_id)
    except ImportError:
        pass


# ============ Task ============

@receiver([post_save, post_delete])
def invalidate_task_cache(sender, instance, **kwargs):
    """Invalidate task-related cache on Task/MasterTask changes."""
    try:
        from api.tasks.models import MasterTask, TaskCompletion
        if sender == MasterTask:
            op = 'task_create' if kwargs.get('created', False) else 'task_update'
            invalidator = get_cache_invalidator()
            invalidator.invalidate(f"task:{instance.id}", op, task_id=instance.id)
        elif sender == TaskCompletion:
            invalidator = get_cache_invalidator()
            user_id = getattr(instance, 'user_id', None)
            if user_id:
                invalidator.invalidate(f"user:{user_id}", 'task_update', user_id=user_id)
    except ImportError:
        pass


# ============ Offer ============

@receiver([post_save, post_delete])
def invalidate_offer_cache(sender, instance, **kwargs):
    """Invalidate offer-related cache on offer changes."""
    try:
        from api.offerwall.models import Offer
        if sender == Offer:
            op = 'offer_create' if kwargs.get('created', False) else 'offer_update'
            invalidator = get_cache_invalidator()
            invalidator.invalidate(f"offer:{instance.id}", op, offer_id=instance.id)
    except ImportError:
        pass


# ============ Withdrawal / Transaction ============

@receiver([post_save, post_delete])
def invalidate_withdrawal_cache(sender, instance, **kwargs):
    """Invalidate withdrawal-related cache."""
    try:
        from api.wallet.models import WithdrawalRequest
        if sender == WithdrawalRequest:
            op = 'withdrawal_create' if kwargs.get('created', False) else 'withdrawal_update'
            invalidator = get_cache_invalidator()
            user_id = getattr(instance, 'user_id', None)
            if user_id:
                invalidator.invalidate(f"user:{user_id}", op, user_id=user_id)
            invalidator.invalidate(f"withdrawal:{instance.id}", op)
    except (ImportError, AttributeError):
        pass


def connect_cache_signals():
    """Call from AppConfig.ready() to ensure signals are connected."""
    # Signals are connected via @receiver decorators; this is for explicit opt-in if needed
    pass
