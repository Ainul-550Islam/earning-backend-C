# api/rate_limit/receivers.py
"""
Signal receivers for rate limit module.

Handles Django signals for automated rate limit operations.
"""

import logging
from django.db.models.signals import post_save, pre_delete, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache

from api.rate_limit.models import (
    RateLimitConfig, UserRateLimitProfile, RateLimitLog, 
    AbuseReport, IPBlockList, RateLimitInsight, RateLimitException
)
from api.rate_limit.services import RateLimitService
from api.rate_limit.services.AbuseDetectionService import AbuseDetectionService
from api.rate_limit.services.IPBlockService import IPBlockService

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(post_save, sender=User)
def user_created_receiver(sender, instance, created, **kwargs):
    """
    Handle user creation - create rate limit profile and set initial limits.
    """
    if created:
        try:
            # Create user rate limit profile
            profile, created = UserRateLimitProfile.objects.get_or_create(
                user=instance,
                defaults={
                    'api_health_score': 100,
                    'suspicion_score': 0,
                    'custom_daily_limit': 1000,
                    'custom_hourly_limit': 100,
                }
            )
            
            if created:
                logger.info(f"Created rate limit profile for user: {instance.username}")
            
            # Create default rate limit config for new user
            RateLimitConfig.objects.get_or_create(
                user=instance,
                rate_limit_type='user',
                defaults={
                    'name': f'default_user_{instance.username}',
                    'requests_per_unit': 60,
                    'time_unit': 'minute',
                    'time_value': 1,
                    'is_active': True,
                }
            )
            
            logger.info(f"Created default rate limit config for user: {instance.username}")
            
        except Exception as e:
            logger.error(f"Failed to setup rate limit for user {instance.username}: {e}")


@receiver(post_save, sender=RateLimitConfig)
def rate_limit_config_updated(sender, instance, **kwargs):
    """
    Handle rate limit config updates - clear cache and update limits.
    """
    try:
        # Clear related cache entries
        cache_keys = []
        
        if instance.user:
            cache_keys.append(f"rate_limit:user_{instance.user.id}")
        
        if instance.ip_address:
            cache_keys.append(f"rate_limit:ip_{instance.ip_address}")
        
        if instance.endpoint:
            cache_keys.append(f"rate_limit:endpoint_{instance.endpoint}")
        
        # Clear cache
        for key in cache_keys:
            cache.delete(key)
        
        # Update hit count
        instance.hit_count += 1
        instance.save(update_fields=['hit_count'])
        
        logger.info(f"Rate limit config updated: {instance.name}")
        
    except Exception as e:
        logger.error(f"Failed to handle rate limit config update: {e}")


@receiver(pre_delete, sender=RateLimitConfig)
def rate_limit_config_deleting(sender, instance, **kwargs):
    """
    Handle rate limit config deletion - archive logs and cleanup.
    """
    try:
        # Count affected logs
        log_count = RateLimitLog.objects.filter(config=instance).count()
        
        # Archive important logs before deletion
        if log_count > 0:
            logger.info(f"Archiving {log_count} logs for config: {instance.name}")
            
            # In a real implementation, you might move logs to an archive table
            # For now, we'll just log the count
        
        # Clear related cache
        cache_keys = []
        if instance.user:
            cache_keys.append(f"rate_limit:user_{instance.user.id}")
        if instance.ip_address:
            cache_keys.append(f"rate_limit:ip_{instance.ip_address}")
        if instance.endpoint:
            cache_keys.append(f"rate_limit:endpoint_{instance.endpoint}")
        
        for key in cache_keys:
            cache.delete(key)
        
        logger.info(f"Rate limit config deleted: {instance.name}")
        
    except Exception as e:
        logger.error(f"Failed to handle rate limit config deletion: {e}")


@receiver(post_save, sender=RateLimitLog)
def rate_limit_log_created(sender, instance, created, **kwargs):
    """
    Handle rate limit log creation - update statistics and detect abuse.
    """
    if created:
        try:
            # Update user profile statistics
            if instance.user:
                profile, _ = UserRateLimitProfile.objects.get_or_create(
                    user=instance.user,
                    defaults={
                        'api_health_score': 100,
                        'suspicion_score': 0,
                    }
                )
                
                profile.total_requests += 1
                if instance.status == 'blocked':
                    profile.blocked_requests += 1
                
                profile.last_request_at = instance.timestamp
                profile.save(update_fields=['total_requests', 'blocked_requests', 'last_request_at'])
            
            # Check for abuse patterns
            if instance.status == 'blocked' or instance.suspicion_score > 50:
                abuse_service = AbuseDetectionService()
                abuse_service.analyze_request(instance)
            
            # Update config statistics
            if instance.config:
                instance.config.hit_count += 1
                if instance.status == 'blocked':
                    instance.config.block_count += 1
                instance.config.save(update_fields=['hit_count', 'block_count'])
            
        except Exception as e:
            logger.error(f"Failed to handle rate limit log creation: {e}")


@receiver(post_save, sender=AbuseReport)
def abuse_report_created(sender, instance, created, **kwargs):
    """
    Handle abuse report creation - trigger investigation and auto-block if needed.
    """
    if created:
        try:
            logger.info(f"New abuse report created: {instance.id} - {instance.abuse_type}")
            
            # Auto-block IP if multiple reports exist
            report_count = AbuseReport.objects.filter(
                ip_address=instance.ip_address,
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).count()
            
            if report_count >= 3:  # Auto-block after 3 reports in 24 hours
                ip_block_service = IPBlockService()
                ip_block_service.block_ip(
                    ip_address=instance.ip_address,
                    block_type='single',
                    block_reason='auto_detection',
                    expires_at=timezone.now() + timedelta(days=7)
                )
                
                logger.warning(f"Auto-blocked IP {instance.ip_address} due to multiple abuse reports")
            
            # Trigger abuse analysis
            abuse_service = AbuseDetectionService()
            abuse_service.investigate_abuse_report(instance)
            
        except Exception as e:
            logger.error(f"Failed to handle abuse report creation: {e}")


@receiver(post_save, sender=IPBlockList)
def ip_block_created(sender, instance, created, **kwargs):
    """
    Handle IP block creation - clear cache and notify.
    """
    if created:
        try:
            # Clear all rate limit cache for this IP
            cache.delete(f"rate_limit:ip_{instance.ip_address}")
            
            # Log the block
            logger.warning(f"IP blocked: {instance.ip_address} - Reason: {instance.block_reason}")
            
            # Send notification (in a real implementation, you might send email, Slack, etc.)
            if instance.block_reason in ['abuse', 'security', 'auto_detection']:
                logger.critical(f"Critical IP block created: {instance.ip_address}")
            
        except Exception as e:
            logger.error(f"Failed to handle IP block creation: {e}")


@receiver(post_save, sender=RateLimitException)
def rate_limit_exception_created(sender, instance, created, **kwargs):
    """
    Handle rate limit exception creation - clear cache and log.
    """
    if created:
        try:
            # Clear relevant cache
            if instance.user:
                cache.delete(f"rate_limit:user_{instance.user.id}")
            
            if instance.ip_address:
                cache.delete(f"rate_limit:ip_{instance.ip_address}")
            
            logger.info(f"Rate limit exception created: {instance.exception_type} for {instance.user or instance.ip_address}")
            
        except Exception as e:
            logger.error(f"Failed to handle rate limit exception creation: {e}")


@receiver(post_delete, sender=IPBlockList)
def ip_block_removed(sender, instance, **kwargs):
    """
    Handle IP block removal - clear cache and log.
    """
    try:
        # Clear cache for this IP
        cache.delete(f"rate_limit:ip_{instance.ip_address}")
        
        logger.info(f"IP block removed: {instance.ip_address}")
        
    except Exception as e:
        logger.error(f"Failed to handle IP block removal: {e}")


@receiver(post_delete, sender=RateLimitException)
def rate_limit_exception_removed(sender, instance, **kwargs):
    """
    Handle rate limit exception removal - clear cache and log.
    """
    try:
        # Clear relevant cache
        if instance.user:
            cache.delete(f"rate_limit:user_{instance.user.id}")
        
        if instance.ip_address:
            cache.delete(f"rate_limit:ip_{instance.ip_address}")
        
        logger.info(f"Rate limit exception removed: {instance.exception_type}")
        
    except Exception as e:
        logger.error(f"Failed to handle rate limit exception removal: {e}")


# Custom signal handlers for rate limit events
def rate_limit_exceeded_handler(sender, **kwargs):
    """
    Custom handler for rate limit exceeded events.
    """
    try:
        request = kwargs.get('request')
        config = kwargs.get('config')
        user = kwargs.get('user')
        
        if user:
            # Update user suspicion score
            profile, _ = UserRateLimitProfile.objects.get_or_create(
                user=user,
                defaults={'suspicion_score': 0}
            )
            
            profile.suspicion_score = min(100, profile.suspicion_score + 5)
            profile.save(update_fields=['suspicion_score'])
            
            # Check if user should be temporarily blocked
            if profile.suspicion_score > 80:
                from api.rate_limit.services.IPBlockService import IPBlockService
                ip_block_service = IPBlockService()
                
                # Get user's IP
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    ip = x_forwarded_for.split(',')[0]
                else:
                    ip = request.META.get('REMOTE_ADDR')
                
                if ip:
                    ip_block_service.block_ip(
                        ip_address=ip,
                        block_type='single',
                        block_reason='auto_detection',
                        expires_at=timezone.now() + timedelta(hours=1)
                    )
        
        logger.warning(f"Rate limit exceeded for {user or 'anonymous'} on {config.name if config else 'unknown'}")
        
    except Exception as e:
        logger.error(f"Failed to handle rate limit exceeded event: {e}")


def abuse_detected_handler(sender, **kwargs):
    """
    Custom handler for abuse detection events.
    """
    try:
        abuse_type = kwargs.get('abuse_type')
        ip_address = kwargs.get('ip_address')
        user = kwargs.get('user')
        severity = kwargs.get('severity', 'medium')
        
        # Create abuse report
        abuse_report = AbuseReport.objects.create(
            user=user,
            ip_address=ip_address,
            abuse_type=abuse_type,
            severity=severity,
            description=f"Auto-detected abuse: {abuse_type}",
            is_investigated=False,
        )
        
        logger.critical(f"Abuse detected: {abuse_type} from {ip_address} (user: {user})")
        
        # Trigger immediate action for high severity
        if severity in ['high', 'critical']:
            from api.rate_limit.services.IPBlockService import IPBlockService
            ip_block_service = IPBlockService()
            
            ip_block_service.block_ip(
                ip_address=ip_address,
                block_type='single',
                block_reason='auto_detection',
                expires_at=timezone.now() + timedelta(days=1)
            )
        
    except Exception as e:
        logger.error(f"Failed to handle abuse detection event: {e}")


def ip_block_triggered_handler(sender, **kwargs):
    """
    Custom handler for IP block triggered events.
    """
    try:
        ip_address = kwargs.get('ip_address')
        block_reason = kwargs.get('block_reason')
        request = kwargs.get('request')
        
        # Log the block attempt
        logger.critical(f"IP block triggered: {ip_address} - Reason: {block_reason}")
        
        # Create abuse report if it's abuse-related
        if block_reason in ['abuse', 'security', 'auto_detection']:
            user = getattr(request, 'user', None) if request else None
            
            AbuseReport.objects.get_or_create(
                user=user,
                ip_address=ip_address,
                abuse_type='malicious' if block_reason == 'security' else 'spam',
                defaults={
                    'severity': 'high',
                    'description': f"IP blocked due to: {block_reason}",
                    'is_investigated': False,
                }
            )
        
    except Exception as e:
        logger.error(f"Failed to handle IP block triggered event: {e}")


# Register custom signal handlers
def register_custom_handlers():
    """
    Register custom signal handlers for rate limit events.
    """
    try:
        # Import signals module to register handlers
        from api.rate_limit import signals
        
        # Connect custom handlers
        signals.rate_limit_exceeded.connect(rate_limit_exceeded_handler)
        signals.abuse_detected.connect(abuse_detected_handler)
        signals.ip_block_triggered.connect(ip_block_triggered_handler)
        
        logger.info("Custom rate limit signal handlers registered")
        
    except Exception as e:
        logger.error(f"Failed to register custom signal handlers: {e}")


# Auto-register handlers when module is imported
try:
    register_custom_handlers()
except Exception as e:
    logger.error(f"Failed to auto-register signal handlers: {e}")
