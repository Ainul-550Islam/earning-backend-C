"""
Rate Limit Tasks - Scheduled and background tasks for rate limiting system.

This module contains scheduled tasks for maintaining the rate limiting system,
including daily resets, cleanup, reporting, and monitoring functions.
"""
from django.db import models

import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.core.cache import cache

from api.rate_limit.models import (
    RateLimitConfig, RateLimitLog, UserRateLimitProfile, 
    AbuseReport, IPBlockList, RateLimitInsight, RateLimitException
)
from api.rate_limit.services import (
    RateLimitService, IPBlockService, AbuseDetectionService, 
    RateLimitInsightService
)

logger = logging.getLogger(__name__)


def reset_rate_limit_counters():
    """
    Reset daily rate limit counters at midnight.
    
    This function should be scheduled to run daily at midnight to reset
    user rate limit counters and prepare for the new day.
    """
    logger.info("Starting daily rate limit counter reset...")
    
    reset_count = 0
    error_count = 0
    
    try:
        with transaction.atomic():
            # Reset user rate limit profiles
            profiles = UserRateLimitProfile.objects.all()
            
            for profile in profiles:
                try:
                    # Reset daily counters
                    profile.daily_usage = 0
                    profile.hourly_usage = 0  # Also reset hourly for fresh start
                    profile.current_usage = 0
                    
                    # Update health score based on yesterday's performance
                    profile.update_health_score()
                    
                    # Check suspicion score and reset if needed
                    if profile.suspicion_score > 70:
                        profile.suspicion_score = max(0, profile.suspicion_score - 20)
                    
                    profile.save()
                    reset_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to reset profile for user {profile.user.id}: {e}")
                    error_count += 1
            
            # Clear daily Redis keys
            rate_limit_service = RateLimitService()
            
            # Clear user-specific daily keys
            for profile in profiles:
                try:
                    # Clear daily rate limit keys from Redis
                    user_daily_keys = [
                        f"rate_limit:user:{profile.user.id}:day:*",
                        f"rate_limit:user:{profile.user.id}:hour:*",
                    ]
                    
                    for key_pattern in user_daily_keys:
                        try:
                            # Get Redis client and delete keys matching pattern
                            redis_client = cache.client.get_client()
                            cursor = '0'
                            
                            while cursor != 0:
                                cursor, keys = redis_client.scan(
                                    cursor=cursor, 
                                    match=key_pattern, 
                                    count=100
                                )
                                if keys:
                                    redis_client.delete(*keys)
                                    
                        except Exception as e:
                            logger.warning(f"Failed to clear Redis keys for pattern {key_pattern}: {e}")
                            
                except Exception as e:
                    logger.error(f"Failed to clear Redis keys for user {profile.user.id}: {e}")
            
            # Reset rate limit config daily statistics
            configs = RateLimitConfig.objects.all()
            
            for config in configs:
                try:
                    # Reset daily hit and block counts
                    config.hit_count = 0
                    config.block_count = 0
                    config.save()
                    
                except Exception as e:
                    logger.error(f"Failed to reset config {config.id}: {e}")
                    error_count += 1
            
            logger.info(f"Successfully reset {reset_count} user profiles")
            
    except Exception as e:
        logger.error(f"Critical error in rate limit counter reset: {e}")
        error_count += 1
    
    # Log completion
    if error_count > 0:
        logger.warning(f"Rate limit counter reset completed with {error_count} errors")
    else:
        logger.info("Rate limit counter reset completed successfully")
    
    return {
        'reset_count': reset_count,
        'error_count': error_count,
        'timestamp': timezone.now().isoformat()
    }


def cleanup_old_logs(days_to_keep=30):
    """
    Clean up old rate limit logs to maintain database performance.
    
    Args:
        days_to_keep: Number of days to keep logs (default: 30)
        
    Returns:
        Dictionary with cleanup statistics
    """
    logger.info(f"Starting cleanup of rate limit logs older than {days_to_keep} days...")
    
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    
    stats = {
        'rate_limit_logs_deleted': 0,
        'abuse_reports_cleaned': 0,
        'ip_blocks_expired': 0,
        'insights_archived': 0,
        'errors': 0
    }
    
    try:
        with transaction.atomic():
            # Clean up old rate limit logs
            old_logs = RateLimitLog.objects.filter(timestamp__lt=cutoff_date)
            log_count = old_logs.count()
            
            if log_count > 0:
                # Delete in batches to avoid memory issues
                batch_size = 1000
                deleted_count = 0
                
                for i in range(0, log_count, batch_size):
                    batch = old_logs[i:i + batch_size]
                    batch.delete()
                    deleted_count += batch.count()
                
                stats['rate_limit_logs_deleted'] = deleted_count
                logger.info(f"Deleted {deleted_count} old rate limit logs")
            
            # Clean up resolved abuse reports
            resolved_reports = AbuseReport.objects.filter(
                is_investigated=True,
                last_seen__lt=cutoff_date
            )
            report_count = resolved_reports.count()
            
            if report_count > 0:
                resolved_reports.delete()
                stats['abuse_reports_cleaned'] = report_count
                logger.info(f"Cleaned up {report_count} resolved abuse reports")
            
            # Deactivate expired IP blocks
            expired_blocks = IPBlockList.objects.filter(
                is_active=True,
                permanent=False,
                expires_at__lt=timezone.now()
            )
            block_count = expired_blocks.count()
            
            if block_count > 0:
                for block in expired_blocks:
                    block.is_active = False
                    block.save()
                    
                    # Remove from cache
                    cache_key = f"ip_block:{block.ip_address or block.subnet}"
                    cache.delete(cache_key)
                
                stats['ip_blocks_expired'] = block_count
                logger.info(f"Deactivated {block_count} expired IP blocks")
            
            # Archive old insights (keep last 90 days, archive older)
            insight_cutoff = timezone.now() - timedelta(days=90)
            old_insights = RateLimitInsight.objects.filter(
                date__lt=insight_cutoff
            )
            insight_count = old_insights.count()
            
            if insight_count > 0:
                # Archive insights by moving them to a summary or deleting
                # For now, we'll delete old insights to save space
                old_insights.delete()
                stats['insights_archived'] = insight_count
                logger.info(f"Archived {insight_count} old rate limit insights")
            
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        stats['errors'] += 1
    
    logger.info(f"Cleanup completed: {stats}")
    return stats


def generate_rate_limit_report():
    """
    Generate weekly abuse and rate limiting report.
    
    Returns:
        Dictionary with report data and statistics
    """
    logger.info("Starting weekly rate limit report generation...")
    
    # Calculate date ranges
    end_date = timezone.now()
    start_date = end_date - timedelta(days=7)
    
    report_data = {
        'period': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat(),
            'days': 7
        },
        'summary': {},
        'top_abusers': [],
        'top_blocked_ips': [],
        'trending_abuse': [],
        'recommendations': []
    }
    
    try:
        # Generate summary statistics
        total_requests = RateLimitLog.objects.filter(
            timestamp__gte=start_date,
            timestamp__lte=end_date
        ).count()
        
        blocked_requests = RateLimitLog.objects.filter(
            timestamp__gte=start_date,
            timestamp__lte=end_date,
            status='blocked'
        ).count()
        
        abuse_reports = AbuseReport.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        ).count()
        
        active_blocks = IPBlockList.objects.filter(
            is_active=True,
            created_at__gte=start_date,
            created_at__lte=end_date
        ).count()
        
        report_data['summary'] = {
            'total_requests': total_requests,
            'blocked_requests': blocked_requests,
            'block_rate': (blocked_requests / total_requests * 100) if total_requests > 0 else 0,
            'abuse_reports': abuse_reports,
            'active_blocks': active_blocks,
            'unique_users': RateLimitLog.objects.filter(
                timestamp__gte=start_date,
                timestamp__lte=end_date
            ).values('user').distinct().count(),
            'unique_ips': RateLimitLog.objects.filter(
                timestamp__gte=start_date,
                timestamp__lte=end_date
            ).values('ip_address').distinct().count(),
        }
        
        # Find top abusers by IP
        top_abusers = RateLimitLog.objects.filter(
            timestamp__gte=start_date,
            timestamp__lte=end_date
        ).values('ip_address').annotate(
            request_count=models.Count('id'),
            blocked_count=models.Count('id', filter=models.Q(status='blocked'))
        ).order_by('-blocked_count')[:10]
        
        report_data['top_abusers'] = list(top_abusers)
        
        # Find top blocked IPs
        top_blocked_ips = IPBlockList.objects.filter(
            is_active=True,
            created_at__gte=start_date
        ).values('ip_address', 'reason').annotate(
            block_count=models.Count('id')
        ).order_by('-block_count')[:10]
        
        report_data['top_blocked_ips'] = list(top_blocked_ips)
        
        # Find trending abuse types
        trending_abuse = AbuseReport.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        ).values('abuse_type').annotate(
            count=models.Count('id')
        ).order_by('-count')[:5]
        
        report_data['trending_abuse'] = list(trending_abuse)
        
        # Generate recommendations
        recommendations = []
        
        if report_data['summary']['block_rate'] > 20:
            recommendations.append({
                'type': 'warning',
                'message': f"High block rate ({report_data['summary']['block_rate']:.1f}%) detected. Consider reviewing rate limit configurations."
            })
        
        if report_data['summary']['abuse_reports'] > 100:
            recommendations.append({
                'type': 'alert',
                'message': f"High number of abuse reports ({report_data['summary']['abuse_reports']}). Immediate investigation recommended."
            })
        
        if report_data['summary']['active_blocks'] > 50:
            recommendations.append({
                'type': 'info',
                'message': f"High number of active IP blocks ({report_data['summary']['active_blocks']}). Consider automated blocking policies."
            })
        
        report_data['recommendations'] = recommendations
        
        # Send email report if configured
        if hasattr(settings, 'RATE_LIMIT_REPORT_EMAIL') and settings.RATE_LIMIT_REPORT_EMAIL:
            try:
                send_email_report(report_data)
            except Exception as e:
                logger.error(f"Failed to send email report: {e}")
        
        logger.info("Weekly rate limit report generated successfully")
        
    except Exception as e:
        logger.error(f"Error generating rate limit report: {e}")
        report_data['error'] = str(e)
    
    return report_data


def sync_configs_to_redis():
    """
    Reload rate limit configurations from database to Redis cache.
    
    This function ensures Redis cache is synchronized with the latest
    rate limit configurations from the database.
    """
    logger.info("Starting rate limit config synchronization to Redis...")
    
    stats = {
        'configs_synced': 0,
        'exceptions_synced': 0,
        'ip_blocks_synced': 0,
        'errors': 0,
        'cache_keys_cleared': 0
    }
    
    try:
        rate_limit_service = RateLimitService()
        ip_block_service = IPBlockService()
        
        # Clear existing rate limit cache
        try:
            redis_client = cache.client.get_client()
            cursor = '0'
            
            while cursor != 0:
                cursor, keys = redis_client.scan(
                    cursor=cursor, 
                    match='rate_limit:*', 
                    count=1000
                )
                if keys:
                    redis_client.delete(*keys)
                    stats['cache_keys_cleared'] += len(keys)
                    
        except Exception as e:
            logger.warning(f"Failed to clear existing cache: {e}")
        
        # Sync active rate limit configs
        active_configs = RateLimitConfig.objects.filter(is_active=True)
        
        for config in active_configs:
            try:
                # Pre-load config into Redis cache
                cache_key = f"rate_limit_config:{config.id}"
                cache.set(cache_key, {
                    'id': config.id,
                    'name': config.name,
                    'rate_limit_type': config.rate_limit_type,
                    'requests_per_unit': config.requests_per_unit,
                    'time_unit': config.time_unit,
                    'time_value': config.time_value,
                    'is_active': config.is_active,
                    'user_id': config.user.id if config.user else None,
                    'ip_address': config.ip_address,
                    'endpoint': config.endpoint,
                    'task_type': config.task_type,
                    'offer_wall': config.offer_wall,
                    'whitelist': config.whitelist,
                    'blacklist': config.blacklist,
                    'bypass_keys': config.bypass_keys,
                }, timeout=3600)  # 1 hour cache
                
                stats['configs_synced'] += 1
                
            except Exception as e:
                logger.error(f"Failed to sync config {config.id}: {e}")
                stats['errors'] += 1
        
        # Sync active IP blocks
        active_blocks = IPBlockList.objects.filter(is_active=True)
        
        for block in active_blocks:
            try:
                cache_key = f"ip_block:{block.ip_address or block.subnet}"
                cache.set(cache_key, {
                    'id': block.id,
                    'block_type': block.block_type,
                    'reason': block.reason,
                    'is_active': block.is_active,
                    'expires_at': block.expires_at.isoformat() if block.expires_at else None,
                    'permanent': block.permanent,
                    'ip_address': block.ip_address,
                    'ip_range_start': block.ip_range_start,
                    'ip_range_end': block.ip_range_end,
                    'subnet': block.subnet,
                }, timeout=3600)
                
                stats['ip_blocks_synced'] += 1
                
            except Exception as e:
                logger.error(f"Failed to sync IP block {block.id}: {e}")
                stats['errors'] += 1
        
        # Sync active rate limit exceptions
        active_exceptions = RateLimitException.objects.filter(is_active=True)
        
        for exception in active_exceptions:
            try:
                target_key = exception.user.id if exception.user else (
                    exception.ip_address or exception.endpoint_pattern
                )
                cache_key = f"rate_limit_exception:{target_key}"
                cache.set(cache_key, {
                    'id': exception.id,
                    'exception_type': exception.exception_type,
                    'multiplier': exception.multiplier,
                    'max_requests': exception.max_requests,
                    'is_active': exception.is_active,
                    'expires_at': exception.expires_at.isoformat() if exception.expires_at else None,
                    'permanent': exception.permanent,
                    'user_id': exception.user.id if exception.user else None,
                    'ip_address': exception.ip_address,
                    'endpoint_pattern': exception.endpoint_pattern,
                }, timeout=3600)
                
                stats['exceptions_synced'] += 1
                
            except Exception as e:
                logger.error(f"Failed to sync exception {exception.id}: {e}")
                stats['errors'] += 1
        
        logger.info(f"Config sync completed: {stats}")
        
    except Exception as e:
        logger.error(f"Critical error in config sync: {e}")
        stats['errors'] += 1
    
    return stats


def alert_high_abuse(threshold_ip=100, threshold_user=50):
    """
    Alert on sustained high abuse patterns.
    
    Args:
        threshold_ip: Alert if IP has more than this many abuse reports (default: 100)
        threshold_user: Alert if user has more than this many abuse reports (default: 50)
        
    Returns:
        Dictionary with alert information
    """
    logger.info("Starting high abuse alert check...")
    
    alerts = {
        'ip_alerts': [],
        'user_alerts': [],
        'global_alerts': [],
        'timestamp': timezone.now().isoformat()
    }
    
    try:
        # Check for high-abuse IPs
        high_abuse_ips = AbuseReport.objects.values('ip_address').annotate(
            report_count=models.Count('id'),
            blocked_count=models.Count('id', filter=models.Q(is_blocked=True))
        ).filter(
            report_count__gte=threshold_ip,
            created_at__gte=timezone.now() - timedelta(days=7)
        ).order_by('-report_count')
        
        for ip_data in high_abuse_ips:
            ip_address = ip_data['ip_address']
            report_count = ip_data['report_count']
            blocked_count = ip_data['blocked_count']
            
            # Get detailed information
            recent_reports = AbuseReport.objects.filter(
                ip_address=ip_address,
                created_at__gte=timezone.now() - timedelta(days=7)
            ).order_by('-created_at')[:5]
            
            alert = {
                'ip_address': ip_address,
                'report_count': report_count,
                'blocked_count': blocked_count,
                'severity': 'critical' if report_count > 200 else 'high',
                'recent_reports': [
                    {
                        'id': report.id,
                        'abuse_type': report.abuse_type,
                        'severity': report.severity,
                        'created_at': report.created_at.isoformat(),
                        'endpoint': report.endpoint
                    }
                    for report in recent_reports
                ],
                'recommendations': []
            }
            
            # Add recommendations
            if report_count > 200:
                alert['recommendations'].append('Consider permanent IP block')
            if blocked_count < report_count * 0.5:
                alert['recommendations'].append('Many reports not blocked - review detection rules')
            
            alerts['ip_alerts'].append(alert)
        
        # Check for high-abuse users
        high_abuse_users = AbuseReport.objects.values('user').annotate(
            report_count=models.Count('id'),
            blocked_count=models.Count('id', filter=models.Q(is_blocked=True))
        ).filter(
            user__isnull=False,
            report_count__gte=threshold_user,
            created_at__gte=timezone.now() - timedelta(days=7)
        ).order_by('-report_count')
        
        for user_data in high_abuse_users:
            user_id = user_data['user']
            report_count = user_data['report_count']
            blocked_count = user_data['blocked_count']
            
            # Get user details
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(id=user_id)
                
                recent_reports = AbuseReport.objects.filter(
                    user=user,
                    created_at__gte=timezone.now() - timedelta(days=7)
                ).order_by('-created_at')[:5]
                
                alert = {
                    'user_id': user_id,
                    'username': user.username,
                    'email': user.email,
                    'report_count': report_count,
                    'blocked_count': blocked_count,
                    'severity': 'critical' if report_count > 100 else 'high',
                    'recent_reports': [
                        {
                            'id': report.id,
                            'abuse_type': report.abuse_type,
                            'severity': report.severity,
                            'created_at': report.created_at.isoformat(),
                            'endpoint': report.endpoint
                        }
                        for report in recent_reports
                    ],
                    'recommendations': []
                }
                
                # Add recommendations
                if report_count > 100:
                    alert['recommendations'].append('Consider account suspension')
                if user.is_active and blocked_count < report_count * 0.3:
                    alert['recommendations'].append('User still active despite abuse - review')
                
                alerts['user_alerts'].append(alert)
                
            except User.DoesNotExist:
                logger.warning(f"User {user_id} not found for abuse alert")
        
        # Check for global abuse patterns
        total_reports_last_7d = AbuseReport.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        total_reports_last_1d = AbuseReport.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=1)
        ).count()
        
        # Alert on sudden spikes
        if total_reports_last_1d > total_reports_last_7d / 7 * 3:  # 3x daily average
            alerts['global_alerts'].append({
                'type': 'spike',
                'message': f"Abuse report spike detected: {total_reports_last_1d} reports in last 24h",
                'severity': 'high',
                'data': {
                    'last_24h': total_reports_last_1d,
                    'daily_average': total_reports_last_7d / 7,
                    'spike_factor': total_reports_last_1d / (total_reports_last_7d / 7)
                }
            })
        
        # Alert on high volume
        if total_reports_last_7d > 1000:
            alerts['global_alerts'].append({
                'type': 'high_volume',
                'message': f"High abuse volume: {total_reports_last_7d} reports in last 7 days",
                'severity': 'medium' if total_reports_last_7d < 2000 else 'high',
                'data': {
                    'total_reports': total_reports_last_7d,
                    'daily_average': total_reports_last_7d / 7
                }
            })
        
        # Send alerts if configured
        if alerts['ip_alerts'] or alerts['user_alerts'] or alerts['global_alerts']:
            try:
                send_abuse_alerts(alerts)
            except Exception as e:
                logger.error(f"Failed to send abuse alerts: {e}")
        
        logger.info(f"High abuse alert check completed: {len(alerts['ip_alerts'])} IP alerts, {len(alerts['user_alerts'])} user alerts, {len(alerts['global_alerts'])} global alerts")
        
    except Exception as e:
        logger.error(f"Error in high abuse alert check: {e}")
        alerts['error'] = str(e)
    
    return alerts


def send_email_report(report_data):
    """
    Send weekly rate limit report via email.
    
    Args:
        report_data: Dictionary containing report data
    """
    subject = f"Weekly Rate Limit Report - {timezone.now().strftime('%Y-%m-%d')}"
    
    # Build email content
    message = f"""
Rate Limit Weekly Report
========================

Period: {report_data['period']['start'][:10]} to {report_data['period']['end'][:10]}

SUMMARY:
--------
Total Requests: {report_data['summary']['total_requests']:,}
Blocked Requests: {report_data['summary']['blocked_requests']:,}
Block Rate: {report_data['summary']['block_rate']:.2f}%
Abuse Reports: {report_data['summary']['abuse_reports']:,}
Active IP Blocks: {report_data['summary']['active_blocks']:,}
Unique Users: {report_data['summary']['unique_users']:,}
Unique IPs: {report_data['summary']['unique_ips']:,}

TOP ABUSERS BY IP:
------------------
"""
    
    for i, abuser in enumerate(report_data['top_abusers'][:5], 1):
        message += f"{i}. {abuser['ip_address']} - {abuser['blocked_count']} blocked requests\n"
    
    message += "\nTRENDING ABUSE TYPES:\n"
    message += "---------------------\n"
    
    for abuse in report_data['trending_abuse']:
        message += f"{abuse['abuse_type']}: {abuse['count']} reports\n"
    
    message += "\nRECOMMENDATIONS:\n"
    message += "----------------\n"
    
    for rec in report_data['recommendations']:
        message += f"[{rec['type'].upper()}] {rec['message']}\n"
    
    # Send email
    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
        recipient_list=[settings.RATE_LIMIT_REPORT_EMAIL],
        fail_silently=False
    )


def send_abuse_alerts(alerts):
    """
    Send abuse alerts via email.
    
    Args:
        alerts: Dictionary containing alert data
    """
    if not hasattr(settings, 'RATE_LIMIT_ALERT_EMAIL') or not settings.RATE_LIMIT_ALERT_EMAIL:
        return
    
    subject = f"Rate Limit Abuse Alert - {timezone.now().strftime('%Y-%m-%d %H:%M')}"
    
    message = f"""
High Abuse Alert
===============

Timestamp: {alerts['timestamp']}

IP ALERTS ({len(alerts['ip_alerts'])}):
"""
    
    for alert in alerts['ip_alerts'][:3]:  # Limit to top 3
        message += f"""
IP: {alert['ip_address']}
Reports: {alert['report_count']} (Blocked: {alert['blocked_count']})
Severity: {alert['severity'].upper()}
Recommendations: {', '.join(alert['recommendations'])}
"""
    
    if alerts['user_alerts']:
        message += f"\nUSER ALERTS ({len(alerts['user_alerts'])}):\n"
        for alert in alerts['user_alerts'][:3]:
            message += f"""
User: {alert['username']} ({alert['email']})
Reports: {alert['report_count']} (Blocked: {alert['blocked_count']})
Severity: {alert['severity'].upper()}
Recommendations: {', '.join(alert['recommendations'])}
"""
    
    if alerts['global_alerts']:
        message += f"\nGLOBAL ALERTS ({len(alerts['global_alerts'])}):\n"
        for alert in alerts['global_alerts']:
            message += f"[{alert['type'].upper()}] {alert['message']}\n"
    
    # Send email
    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
        recipient_list=[settings.RATE_LIMIT_ALERT_EMAIL],
        fail_silently=False
    )


# Import Count model for aggregation
from django.db.models import Count
