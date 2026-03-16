from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import RateLimitConfig, UserRateLimitProfile, RateLimitLog
from .services import RateLimitService
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(post_save, sender=User)
def create_user_rate_limit_profile(sender, instance, created, **kwargs):
    """Create rate limit profile when new user is created"""
    if created:
        try:
            UserRateLimitProfile.objects.create(user=instance)
            logger.info(f"Rate limit profile created for user: {instance.username}")
        except Exception as e:
            logger.error(f"Failed to create rate limit profile for {instance.username}: {e}")


@receiver(post_save, sender=RateLimitConfig)
def clear_rate_limit_cache(sender, instance, **kwargs):
    """Clear rate limit cache when config is updated"""
    try:
        rate_limit_service = RateLimitService()
        
        # Clear Redis cache for this config
        if instance.rate_limit_type == 'user' and instance.user:
            identifier = f"user:{instance.user.id}"
            rate_limit_service.redis_limiter.reset_rate_limit(identifier, instance)
        
        logger.info(f"Rate limit cache cleared for config: {instance.name}")
        
    except Exception as e:
        logger.error(f"Failed to clear rate limit cache: {e}")


@receiver(pre_delete, sender=RateLimitConfig)
def cleanup_rate_limit_config(sender, instance, **kwargs):
    """Cleanup before deleting rate limit config"""
    try:
        # Archive logs before deletion
        logs_count = RateLimitLog.objects.filter(config=instance).count()
        logger.info(f"Deleting rate limit config: {instance.name}, affecting {logs_count} logs")
        
    except Exception as e:
        logger.error(f"Failed to cleanup rate limit config: {e}")


@receiver(post_save, sender=RateLimitLog)
def update_user_statistics(sender, instance, created, **kwargs):
    """Update user statistics when new log is created"""
    if created and instance.user:
        try:
            profile, _ = UserRateLimitProfile.objects.get_or_create(user=instance.user)
            
            # Update last request time
            profile.last_request_at = timezone.now()
            
            # Update counts based on status
            if instance.status == 'blocked':
                profile.blocked_requests += 1
            
            profile.save()
            
        except Exception as e:
            logger.error(f"Failed to update user statistics: {e}")


# Premium subscription signals
@receiver(post_save, sender=UserRateLimitProfile)
def handle_premium_status_change(sender, instance, created, **kwargs):
    """Handle premium status changes"""
    if not created:
        # Check if premium status changed
        try:
            old_instance = UserRateLimitProfile.objects.get(id=instance.id)
            if old_instance.is_premium != instance.is_premium:
                if instance.is_premium:
                    logger.info(f"User {instance.user.username} upgraded to premium")
                    # Apply premium rate limits
                    self._apply_premium_limits(instance.user)
                else:
                    logger.info(f"User {instance.user.username} downgraded from premium")
                    # Remove premium rate limits
                    self._remove_premium_limits(instance.user)
        except UserRateLimitProfile.DoesNotExist:
            pass


def _apply_premium_limits(user):
    """Apply premium rate limits to user"""
    try:
        # Create or update premium config for user
        config, created = RateLimitConfig.objects.get_or_create(
            name=f"premium_{user.username}",
            rate_limit_type='user',
            user=user,
            defaults={
                'requests_per_unit': 500,
                'time_unit': 'hour',
                'time_value': 1,
                'is_active': True
            }
        )
        
        if not created:
            config.requests_per_unit = 500
            config.save()
        
        logger.info(f"Premium limits applied for user: {user.username}")
        
    except Exception as e:
        logger.error(f"Failed to apply premium limits: {e}")


def _remove_premium_limits(user):
    """Remove premium rate limits from user"""
    try:
        # Deactivate premium config
        configs = RateLimitConfig.objects.filter(
            name__startswith=f"premium_{user.username}",
            rate_limit_type='user',
            user=user
        )
        
        for config in configs:
            config.is_active = False
            config.save()
        
        logger.info(f"Premium limits removed for user: {user.username}")
        
    except Exception as e:
        logger.error(f"Failed to remove premium limits: {e}")