# api/rate_limit/tasks_cap.py
"""
Celery task definitions for rate limit module.

Defines background tasks for rate limiting operations.
"""
from django.db.models import Count
from django.db.models import Q

import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction
from celery import shared_task
from celery.signals import task_prerun, task_postrun, task_failure

from api.rate_limit.models import (
    RateLimitConfig, RateLimitLog, UserRateLimitProfile, 
    AbuseReport, IPBlockList, RateLimitInsight, RateLimitException
)
from api.rate_limit.services import RateLimitService
from api.rate_limit.services.AbuseDetectionService import AbuseDetectionService
from api.rate_limit.services.IPBlockService import IPBlockService
from api.rate_limit.services.RateLimitInsightService import RateLimitInsightService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def cleanup_expired_rate_limits(self):
    """
    Clean up expired rate limit configurations and exceptions.
    """
    try:
        logger.info("Starting cleanup of expired rate limits")
        
        # Clean up expired exceptions
        expired_exceptions = RateLimitException.objects.filter(
            is_active=True,
            expires_at__lt=timezone.now(),
            permanent=False
        )
        
        exception_count = expired_exceptions.count()
        expired_exceptions.update(is_active=False)
        
        # Clean up expired IP blocks
        expired_blocks = IPBlockList.objects.filter(
            is_active=True,
            expires_at__lt=timezone.now(),
            permanent=False
        )
        
        block_count = expired_blocks.count()
        expired_blocks.update(is_active=False)
        
        # Clear cache for expired items
        for exception in expired_exceptions:
            if exception.user:
                cache.delete(f"rate_limit:user_{exception.user.id}")
            if exception.ip_address:
                cache.delete(f"rate_limit:ip_{exception.ip_address}")
        
        for block in expired_blocks:
            cache.delete(f"rate_limit:ip_{block.ip_address}")
        
        logger.info(f"Cleaned up {exception_count} expired exceptions and {block_count} expired blocks")
        
        return {
            'exceptions_cleaned': exception_count,
            'blocks_cleaned': block_count,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error("Cleanup task failed: %s", str(e), exc_info=True)
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_rate_limit_insights(self, date=None):
    """
    Generate daily rate limit insights and analytics.
    """
    try:
        if date is None:
            date = timezone.now().date()
        
        logger.info(f"Generating rate limit insights for {date}")
        
        insight_service = RateLimitInsightService()
        insight = insight_service.generate_daily_insight(date)
        
        logger.info(f"Generated insight for {date}: {insight.id}")
        
        return {
            'insight_id': insight.id,
            'date': date.isoformat(),
            'total_requests': insight.total_requests,
            'blocked_requests': insight.blocked_requests,
            'unique_ips': insight.unique_ips,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error("Insight generation failed: %s", str(e), exc_info=True)
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def analyze_abuse_patterns(self, hours=24):
    """
    Analyze abuse patterns and create auto-blocks if necessary.
    """
    try:
        logger.info(f"Starting abuse pattern analysis for last {hours} hours")
        
        abuse_service = AbuseDetectionService()
        
        # Get recent logs for analysis
        since_time = timezone.now() - timedelta(hours=hours)
        recent_logs = RateLimitLog.objects.filter(
            timestamp__gte=since_time,
            status='blocked'
        )
        
        # Analyze patterns
        patterns_detected = abuse_service.analyze_patterns(recent_logs)
        
        # Auto-block suspicious IPs
        auto_blocked = 0
        for pattern in patterns_detected:
            if pattern['severity'] in ['high', 'critical']:
                ip_block_service = IPBlockService()
                
                for ip_address in pattern['ip_addresses']:
                    block = ip_block_service.block_ip(
                        ip_address=ip_address,
                        block_type='single',
                        block_reason='auto_detection',
                        expires_at=timezone.now() + timedelta(days=7)
                    )
                    
                    if block:
                        auto_blocked += 1
        
        logger.info(f"Abuse analysis complete: {len(patterns_detected)} patterns, {auto_blocked} IPs blocked")
        
        return {
            'patterns_detected': len(patterns_detected),
            'auto_blocked_ips': auto_blocked,
            'analysis_period_hours': hours,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error("Abuse pattern analysis failed: %s", str(e), exc_info=True)
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def update_user_health_scores(self):
    """
    Update health scores for all users based on their rate limit behavior.
    """
    try:
        logger.info("Starting user health score updates")
        
        # Get all user profiles
        profiles = UserRateLimitProfile.objects.all()
        
        updated_count = 0
        for profile in profiles:
            try:
                # Update health score
                profile.update_health_score()
                
                # Check suspicion
                profile.check_suspicion()
                
                updated_count += 1
                
            except Exception as e:
                logger.error("Failed to update health score for user %s: %s", profile.user.id, str(e), exc_info=True)
        
        logger.info(f"Updated health scores for {updated_count} users")
        
        return {
            'users_updated': updated_count,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error("Health score update failed: %s", str(e), exc_info=True)
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def reset_daily_rate_limits(self):
    """
    Reset daily rate limit counters for all users.
    """
    try:
        logger.info("Resetting daily rate limits")
        
        # Reset user profiles
        updated = UserRateLimitProfile.objects.update(
            daily_usage=0,
            current_usage=0
        )
        
        # Clear daily cache keys
        cache_keys = cache.keys("rate_limit:*:day:*")
        cache.delete_many(cache_keys)
        
        logger.info(f"Reset daily limits for {updated} users")
        
        return {
            'users_reset': updated,
            'cache_keys_cleared': len(cache_keys),
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error("Daily reset failed: %s", str(e), exc_info=True)
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def reset_hourly_rate_limits(self):
    """
    Reset hourly rate limit counters for all users.
    """
    try:
        logger.info("Resetting hourly rate limits")
        
        # Reset user profiles
        updated = UserRateLimitProfile.objects.update(
            hourly_usage=0
        )
        
        # Clear hourly cache keys
        cache_keys = cache.keys("rate_limit:*:hour:*")
        cache.delete_many(cache_keys)
        
        logger.info(f"Reset hourly limits for {updated} users")
        
        return {
            'users_reset': updated,
            'cache_keys_cleared': len(cache_keys),
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error("Hourly reset failed: %s", str(e), exc_info=True)
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def archive_old_logs(self, days=30):
    """
    Archive old rate limit logs to keep database performance optimal.
    """
    try:
        logger.info(f"Archiving logs older than {days} days")
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Count logs to be archived
        log_count = RateLimitLog.objects.filter(timestamp__lt=cutoff_date).count()
        
        if log_count > 0:
            # In a real implementation, you would move logs to an archive table
            # For now, we'll just delete old logs
            deleted_count = RateLimitLog.objects.filter(timestamp__lt=cutoff_date).delete()[0]
            
            logger.info(f"Archived/deleted {deleted_count} old logs")
        else:
            logger.info("No old logs to archive")
        
        return {
            'logs_archived': log_count,
            'cutoff_date': cutoff_date.isoformat(),
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error("Log archiving failed: %s", str(e), exc_info=True)
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_system_health(self):
    """
    Check overall rate limiting system health and send alerts if needed.
    """
    try:
        logger.info("Checking system health")
        
        # Get health metrics
        health_data = RateLimitService.check_global_health()
        
        # Send alerts if health is poor
        if health_data['health_status'] in ['critical', 'warning']:
            logger.warning(f"System health alert: {health_data['health_status']} - Score: {health_data['health_score']}")
            
            # In a real implementation, you would send notifications
            # Email, Slack, SMS, etc.
        
        # Update system metrics
        cache.set('rate_limit_system_health', health_data, timeout=3600)
        
        return health_data
        
    except Exception as e:
        logger.error("System health check failed: %s", str(e), exc_info=True)
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def optimize_rate_limit_configs(self):
    """
    Optimize rate limit configurations based on usage patterns.
    """
    try:
        logger.info("Optimizing rate limit configurations")
        
        # Get active configs with high block rates
        high_block_configs = RateLimitConfig.objects.filter(
            is_active=True,
            hit_count__gt=100
        ).annotate(
            block_rate=Count('ratelimitlog', filter=Q(ratelimitlog__status='blocked')) * 100.0 / Count('ratelimitlog')
        ).filter(block_rate__gt=20)  # More than 20% block rate
        
        optimized_count = 0
        for config in high_block_configs:
            try:
                # Suggest higher limits for configs with high block rates
                if config.requests_per_unit < 1000:
                    new_limit = int(config.requests_per_unit * 1.5)
                    
                    # Create a suggestion (in a real implementation, you might notify admins)
                    logger.info(f"Suggestion for {config.name}: Increase limit from {config.requests_per_unit} to {new_limit}")
                    
                    optimized_count += 1
                
            except Exception as e:
                logger.error("Failed to optimize config %s: %s", config.id, str(e), exc_info=True)
        
        logger.info(f"Optimization suggestions generated for {optimized_count} configurations")
        
        return {
            'configs_analyzed': high_block_configs.count(),
            'optimizations_suggested': optimized_count,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error("Config optimization failed: %s", str(e), exc_info=True)
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def bulk_reset_user_limits(self, user_ids):
    """
    Reset rate limits for multiple users.
    """
    try:
        logger.info(f"Bulk resetting rate limits for {len(user_ids)} users")
        
        reset_count = 0
        for user_id in user_ids:
            try:
                # Reset user profile
                profile = UserRateLimitProfile.objects.get(user_id=user_id)
                profile.daily_usage = 0
                profile.hourly_usage = 0
                profile.current_usage = 0
                profile.save(update_fields=['daily_usage', 'hourly_usage', 'current_usage'])
                
                # Clear cache
                cache.delete(f"rate_limit:user_{user_id}")
                
                reset_count += 1
                
            except UserRateLimitProfile.DoesNotExist:
                logger.warning(f"User profile not found for user {user_id}")
            except Exception as e:
                logger.error("Failed to reset user %s: %s", user_id, str(e), exc_info=True)
        
        logger.info(f"Reset limits for {reset_count} users")
        
        return {
            'users_requested': len(user_ids),
            'users_reset': reset_count,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Bulk reset failed: {str(e)}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def export_rate_limit_data(self, start_date, end_date, export_format='csv'):
    """
    Export rate limit data for analysis.
    """
    try:
        logger.info(f"Exporting rate limit data from {start_date} to {end_date}")
        
        # Get logs for date range
        logs = RateLimitLog.objects.filter(
            timestamp__gte=start_date,
            timestamp__lte=end_date
        ).select_related('user', 'config')
        
        # Generate export data
        export_data = []
        for log in logs:
            export_data.append({
                'timestamp': log.timestamp.isoformat(),
                'user': log.user.username if log.user else 'Anonymous',
                'ip_address': log.ip_address,
                'endpoint': log.endpoint,
                'method': log.request_method,
                'status': log.status,
                'config': log.config.name if log.config else None,
                'suspicion_score': log.suspicion_score,
            })
        
        # In a real implementation, you would create actual files
        # For now, we'll just return the data
        logger.info(f"Exported {len(export_data)} log entries")
        
        return {
            'export_format': export_format,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'records_exported': len(export_data),
            'data': export_data[:100],  # Return first 100 records as sample
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Data export failed: {str(e)}")
        raise self.retry(exc=e)


# Task signal handlers
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """
    Handle task pre-run signals for logging.
    """
    logger.info(f"Starting task: {task.name} (ID: {task_id})")


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **kwds):
    """
    Handle task post-run signals for logging.
    """
    logger.info(f"Completed task: {task.name} (ID: {task_id}) - State: {state}")


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
    """
    Handle task failure signals for logging.
    """
    logger.error(f"Task failed: {sender.name} (ID: {task_id}) - Exception: {exception}")
