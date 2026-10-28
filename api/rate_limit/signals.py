from django.db.models.signals import post_save, pre_save, pre_delete, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from api.rate_limit.models import RateLimitConfig, UserRateLimitProfile, RateLimitLog, AbuseReport, IPBlockList, RateLimitInsight
from api.rate_limit.services import RateLimitService
from api.rate_limit.services.AbuseDetectionService import AbuseDetectionService
from api.rate_limit.services.IPBlockService import IPBlockService
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(post_save, sender=User)
def create_user_rate_limit_profile(sender, instance, created, **kwargs):
    """Create rate limit profile when new user is created"""
    if created:
        try:
            UserRateLimitProfile.objects.get_or_create(user=instance)
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


# User statistics are now handled centrally in RateLimitService._update_user_stats()
# to avoid double counting. This signal is removed to prevent duplicate updates.


# Premium subscription signals
@receiver(pre_save, sender=UserRateLimitProfile)
def handle_premium_status_change(sender, instance, **kwargs):
    """Handle premium status changes"""
    # Check if this is an existing instance (not creation)
    if instance.pk:
        try:
            # Get the current database values before save
            old_instance = UserRateLimitProfile.objects.get(pk=instance.pk)
            old_premium_status = old_instance.is_premium
            new_premium_status = instance.is_premium
            
            if old_premium_status != new_premium_status:
                if new_premium_status:
                    logger.info(f"User {instance.user.username} upgraded to premium")
                    # Apply premium rate limits after save
                    # Use post_save to ensure the instance is saved first
                    instance._premium_upgraded = True
                else:
                    logger.info(f"User {instance.user.username} downgraded from premium")
                    # Remove premium rate limits after save
                    # Use post_save to ensure the instance is saved first
                    instance._premium_downgraded = True
                    
        except UserRateLimitProfile.DoesNotExist:
            # This is a new instance, no status change to handle
            pass

@receiver(post_save, sender=UserRateLimitProfile)
def apply_premium_changes_after_save(sender, instance, created, **kwargs):
    """Apply premium rate limit changes after the instance is saved"""
    if not created:
        # Check if premium status change flags were set
        if hasattr(instance, '_premium_upgraded') and instance._premium_upgraded:
            _apply_premium_limits(instance.user)
            # Clean up the flag
            delattr(instance, '_premium_upgraded')
            
        elif hasattr(instance, '_premium_downgraded') and instance._premium_downgraded:
            _remove_premium_limits(instance.user)
            # Clean up the flag
            delattr(instance, '_premium_downgraded')


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


# Auto-blocking signals for abuse detection
@receiver(post_save, sender=AbuseReport)
def handle_abuse_report_auto_block(sender, instance, created, **kwargs):
    """Handle automatic blocking based on abuse reports."""
    if created:
        try:
            # Check if abuse report should trigger auto-blocking
            if instance.should_block():
                ip_block_service = IPBlockService()
                
                # Check if IP is already blocked
                is_blocked, _ = ip_block_service.is_ip_blocked(instance.ip_address)
                
                if not is_blocked:
                    # Auto-block the IP
                    block = ip_block_service.block_ip(
                        ip_address=instance.ip_address,
                        reason='automatic',
                        description=f"Auto-blocked due to {instance.abuse_type} abuse (Severity: {instance.severity})",
                        duration_days=7 if instance.severity < 4 else 30,
                        blocked_by=instance.user
                    )
                    
                    # Update abuse report to reflect blocking
                    instance.is_blocked = True
                    instance.save(update_fields=['is_blocked'])
                    
                    logger.warning(f"Auto-blocked IP {instance.ip_address} due to abuse report {instance.id}")
                else:
                    logger.info(f"IP {instance.ip_address} already blocked, updating abuse report")
                    instance.is_blocked = True
                    instance.save(update_fields=['is_blocked'])
            
            # Update abuse counts
            instance.update_counts()
            
        except Exception as e:
            logger.error(f"Failed to handle abuse report auto-block: {e}")


@receiver(post_save, sender=IPBlockList)
def handle_ip_block_statistics(sender, instance, created, **kwargs):
    """Update statistics when IP block is created."""
    if created:
        try:
            # Update block count
            instance.block_count = 1
            instance.last_blocked_at = timezone.now()
            instance.save(update_fields=['block_count', 'last_blocked_at'])
            
            # Log the blocking event
            logger.info(f"IP block created: {instance} by {instance.blocked_by}")
            
            # If this is an automatic block, trigger abuse detection analysis
            if instance.reason == 'automatic':
                abuse_service = AbuseDetectionService()
                patterns = abuse_service.detect_abuse_patterns(
                    ip_address=instance.ip_address,
                    time_window=3600  # Last hour
                )
                
                logger.info(f"Abuse patterns for blocked IP {instance.ip_address}: {patterns}")
                
        except Exception as e:
            logger.error(f"Failed to handle IP block statistics: {e}")


@receiver(post_save, sender=RateLimitInsight)
def handle_rate_limit_insight_alerts(sender, instance, created, **kwargs):
    """Handle alerts and recommendations based on rate limit insights."""
    if created:
        try:
            # Check for high risk scores that need attention
            if hasattr(instance, 'risk_score') and instance.risk_score > 70:
                logger.warning(f"High risk score detected: {instance.risk_score} for {instance.date}")
                
                # Could trigger additional monitoring or alerts here
                # For example: send notification to admin, create emergency blocks, etc.
            
            # Log insight generation
            logger.info(f"Rate limit insight generated for {instance.date}")
            
        except Exception as e:
            logger.error(f"Failed to handle rate limit insight alerts: {e}")


@receiver(pre_delete, sender=IPBlockList)
def handle_ip_block_cleanup(sender, instance, **kwargs):
    """Handle cleanup before deleting IP block."""
    try:
        # Log the deletion
        logger.info(f"IP block deleted: {instance}")
        
        # Update related abuse reports if needed
        if instance.ip_address:
            AbuseReport.objects.filter(
                ip_address=instance.ip_address,
                is_blocked=True
            ).update(is_blocked=False)
        
    except Exception as e:
        logger.error(f"Failed to handle IP block cleanup: {e}")


# High-frequency request detection signal
@receiver(post_save, sender=RateLimitLog)
def detect_high_frequency_requests(sender, instance, created, **kwargs):
    """Detect high-frequency request patterns that may indicate abuse."""
    if created and instance.status == 'allowed':
        try:
            # Check for rapid requests from same IP
            recent_logs = RateLimitLog.objects.filter(
                ip_address=instance.ip_address,
                timestamp__gte=timezone.now() - timedelta(minutes=5)
            ).count()
            
            # If more than 50 requests in 5 minutes, trigger abuse detection
            if recent_logs > 50:
                abuse_service = AbuseDetectionService()
                patterns = abuse_service.detect_abuse_patterns(
                    ip_address=instance.ip_address,
                    user=instance.user,
                    endpoint=instance.endpoint,
                    time_window=300  # 5 minutes
                )
                
                # If high risk detected, create abuse report
                if patterns['risk_score'] > 60:
                    abuse_service.create_abuse_report(
                        ip_address=instance.ip_address,
                        user=instance.user,
                        endpoint=instance.endpoint,
                        abuse_type=patterns['abuse_types'][0] if patterns['abuse_types'] else 'other',
                        severity=min(4, patterns['risk_score'] // 20 + 1),
                        metadata={
                            'detection_method': 'high_frequency',
                            'patterns': patterns,
                            'request_count': recent_logs
                        }
                    )
                    
                    logger.warning(f"High-frequency abuse detected from {instance.ip_address}: {recent_logs} requests in 5 minutes")
        
        except Exception as e:
            logger.error(f"Failed to detect high-frequency requests: {e}")

# -----------------------------------------------------------------------
# WebSocket broadcast signals
# These fire on model saves and broadcast to connected WS clients.
# -----------------------------------------------------------------------
def _broadcast_to_group(group_name: str, event_type: str, data: dict):
    """Fire-and-forget channel layer group_send from a sync context."""
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            group_name,
            {'type': event_type, 'data': data},
        )
    except Exception as e:
        logger.error(f"_broadcast_to_group error: {e}")


@receiver(post_save, sender=AbuseReport)
def broadcast_abuse_report_signal(sender, instance, created, **kwargs):
    if not created:
        return
    _broadcast_to_group(
        'rate_limit_events',
        'broadcast_abuse_report',
        {
            'id': instance.pk,
            'reported_ip': instance.reported_ip,
            'reason': instance.reason,
        },
    )


@receiver(post_save, sender=IPBlockList)
def broadcast_ip_block_signal(sender, instance, created, **kwargs):
    if not created:
        return
    _broadcast_to_group(
        'rate_limit_events',
        'broadcast_ip_block',
        {
            'id': instance.pk,
            'ip_address': instance.ip_address,
            'reason': instance.reason,
        },
    )


@receiver(post_save, sender=RateLimitLog)
def broadcast_rate_limit_event_signal(sender, instance, created, **kwargs):
    if not created:
        return
    _broadcast_to_group(
        'rate_limit_events',
        'broadcast_rate_limit_event',
        {
            'id': instance.pk,
            'endpoint': instance.endpoint,
            'is_allowed': instance.is_allowed,
        },
    )
